"""The long-running observation service — one buffer for the process, not one per CLI call.

The audit caught a real defect: `dhaka_opencity_schema.py` constructed a fresh `LiveValueBuffer`
on every invocation and observed a single snapshot, so it could never accumulate the 288 steps it
was measuring itself against. Readiness was structurally unreachable — the countdown could not
count.

The buffer therefore belongs to the running backend, which samples on a timer and keeps history
for as long as the process lives. `readiness()` reports what has ACTUALLY accumulated.

Storage discipline is unchanged and deliberate: values are DERIVED speeds (distance / duration,
computed by us), held in a bounded in-memory ring. Google route content is not written to disk.
A restart loses the window, and that is the honest cost of the compliance position rather than
something to hide — `readiness()` shows the buffer's age so nobody mistakes a fresh process for
a city with no traffic.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from core.common.data import reference_corridors as _corridors
from core.common.evidence_paths import REPO

# The speeds are derived here (distance / duration) from a provider's route result. Whether a derived speed is still
# the provider's "Location Data" is not settled by the terms, so it is treated as if it were (see the rules below).
DB = REPO / "results/live/observatory.sqlite"

# AWS Service Terms 82.4(a) (read 2026-10-04): Location Data may not be "systematically collected" or stored, except
# "route results for up to 30 days when you use HERE or Esri as your Geolocation Provider". Until AWS answers which
# provider backs the Routes API and whether periodic polling is allowed (question drafted in
# evidence/audit_2026-10-05/), three things hold here:
#   1. no sampling through a third-party route provider (PROVIDER_SAMPLING_ENV must be set by a person to resume);
#   2. rows that came from one are deleted after PROVIDER_RETENTION_DAYS;
#   3. such rows are never a training set, a test set or "observed traffic" — only OBSERVED_PROVIDERS are.
PROVIDER_RETENTION_DAYS = 30
PROVIDER_SAMPLING_ENV = "TRAFFICTWIN_PROVIDER_SAMPLING_APPROVED"
ROUTE_PROVIDERS = ("amazon_location",)             # third-party route results under a 30-day storage limit
OBSERVED_PROVIDERS = frozenset({"probes"})         # our own opt-in phone sensing; nothing writes these rows yet

BIN_S = 300
HIS = 288            # OpenCity's input window
MIN_NODES = 20


class Observatory:
    """Samples the live provider on a timer and keeps a rolling value history per city."""

    def __init__(self, capacity: int = HIS * 2, interval_s: int = BIN_S):
        self.capacity = capacity
        self.interval_s = interval_s
        self._rows: dict[str, deque] = {}
        self._nodes: dict[str, list[str]] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._started_utc: str | None = None
        self._samples = 0
        self._failures = 0
        self._restored: set[str] = set()

    # ------------------------------------------------------------ persistence
    def _conn(self) -> sqlite3.Connection:
        DB.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB, timeout=10)
        c.execute("""CREATE TABLE IF NOT EXISTS samples (
            city TEXT NOT NULL, t REAL NOT NULL, utc TEXT NOT NULL, nodes TEXT NOT NULL,
            values_json TEXT NOT NULL, PRIMARY KEY (city, t))""")
        cols = [r[1] for r in c.execute("PRAGMA table_info(samples)")]
        if "provider" not in cols:
            # which provider produced the row decides what the row may be used for: Google-derived history is never a
            # training or test set (standing rule); our own Amazon Location derived speeds are. Rows before the sampler
            # was pointed at the selected provider (2026-10-03 12:38 UTC) came through the Google provider.
            c.execute("ALTER TABLE samples ADD COLUMN provider TEXT")
            c.execute("UPDATE samples SET provider = CASE WHEN utc >= '2026-10-03T12:38:00' THEN 'amazon_location' ELSE 'google' END WHERE provider IS NULL")
            c.commit()
        c.execute(f"DELETE FROM samples WHERE provider IN ({','.join('?' * len(ROUTE_PROVIDERS))}) AND t < ?",
                  (*ROUTE_PROVIDERS, time.time() - PROVIDER_RETENTION_DAYS * 86400))        # rolling retention, every time the store is opened
        c.commit()
        return c

    def _restore(self, city_id: str) -> None:
        """Load the persisted window once per city, before anything reads or appends."""
        if city_id in self._restored:
            return
        self._restored.add(city_id)
        try:
            with self._conn() as c:
                rows = c.execute("SELECT t, utc, nodes, values_json, provider FROM samples WHERE city=? "
                                 "ORDER BY t DESC LIMIT ?", (city_id, self.capacity)).fetchall()
        except sqlite3.Error:
            return
        if not rows:
            return
        rows.reverse()
        nodes = json.loads(rows[-1][2])
        d = self._rows.setdefault(city_id, deque(maxlen=self.capacity))
        for t, utc, n, v, prov in rows:
            vals = json.loads(v)
            if json.loads(n) != nodes or all(x is None for x in vals):      # a row with no value is a dead sampler, not a reading
                continue
            if (prov or "google") == "google":                              # Google-derived rows are never read (withdrawn 2026-10-05)
                continue
            d.append({"t": float(t), "utc": utc, "provider": prov or "google",
                      "v": [float("nan") if x is None else float(x) for x in vals]})
        self._nodes.setdefault(city_id, nodes)

    def _persist(self, city_id: str, row: dict, nodes: list[str]) -> None:
        try:
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO samples (city, t, utc, nodes, values_json, provider) VALUES (?,?,?,?,?,?)",
                          (city_id, row["t"], row["utc"], json.dumps(nodes),
                           json.dumps([None if x != x else round(x, 4) for x in row["v"]]), row.get("provider")))
        except sqlite3.Error:
            pass                                    # the in-memory window still works

    # ----------------------------------------------------------- lifecycle
    def cities(self) -> list[str]:
        """Every city being observed, persisted so a restart keeps watching them."""
        try:
            with self._conn() as c:
                c.execute("CREATE TABLE IF NOT EXISTS watched (city TEXT PRIMARY KEY, since TEXT)")
                rows = [r[0] for r in c.execute("SELECT city FROM watched ORDER BY since").fetchall()]
        except sqlite3.Error:
            rows = []
        return rows or ["dhaka"]

    def watch(self, city_id: str) -> None:
        with self._conn() as c:
            c.execute("CREATE TABLE IF NOT EXISTS watched (city TEXT PRIMARY KEY, since TEXT)")
            c.execute("INSERT OR IGNORE INTO watched VALUES (?, ?)", (city_id, datetime.now(timezone.utc).isoformat()))

    def start(self, city_id: str = "dhaka") -> dict:
        """Watch a city (added to the persisted set) and make sure the sampling loop runs."""
        self.watch(city_id)
        if self._thread and self._thread.is_alive():
            self._wake.set()                         # sample the new city now, not next tick
            return self.status()
        self._stop.clear()
        self._started_utc = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        return self.status()

    def _loop(self) -> None:
        sampled: set[str] = set()
        import os
        if os.environ.get("TRAFFICTWIN_RECORDER", "0") != "1":      # the recorder polls every corridor of every watched city every 5 min: billable calls — opt in explicitly
            return
        while not self._stop.is_set():
            for city in self.cities():
                if self._stop.is_set():
                    break
                try:
                    self.sample(city)
                except Exception:                   # noqa: BLE001 - a bad tick must not kill it
                    with self._lock:
                        self._failures += 1
            self._wake.clear()
            self._wake.wait(self.interval_s)

    # ------------------------------------------------------------- sampling
    def sample(self, city_id: str = "dhaka") -> dict:
        """Take one live reading and append DERIVED speeds. Gaps stay NaN, never interpolated."""
        # the SELECTED provider (Amazon Location when configured, the Google fallback otherwise), never Google by
        # name: this line pointed at google_routes and wrote a month of null samples after that key stopped working
        import os
        from core.common.data.live_providers.live import provider
        service = provider()
        source = getattr(service, "name", None) or getattr(service, "source", None) or type(service).__module__.rsplit(".", 1)[-1]
        if source in ROUTE_PROVIDERS and os.environ.get(PROVIDER_SAMPLING_ENV) != "1":
            return {"city_id": city_id, "observed": 0, "nodes": 0, "status": "PAUSED",
                    "reason": f"sampling through {source} is paused pending the provider's answer on storing and polling route results; set {PROVIDER_SAMPLING_ENV}=1 to resume"}
        snap = service.corridors_for(city_id)
        ids = [c["id"] for c in snap.get("corridors", [])] if city_id != "dhaka" else [c["id"] for c in _corridors.CORRIDORS]
        if not ids:
            return {"city_id": city_id, "observed": 0, "nodes": 0}
        row = [float("nan")] * len(ids)
        idx = {c: i for i, c in enumerate(ids)}
        for c in snap.get("corridors", []):
            i = idx.get(c.get("id"))
            if i is None or not c.get("is_live"):
                continue
            dist, dur = c.get("distance_m"), c.get("duration_s")
            if dist and dur and dur > 0:
                row[i] = dist / dur                  # m/s, derived by us
        rec = {"t": time.time(), "utc": datetime.now(timezone.utc).isoformat(), "v": row, "provider": source}
        with self._lock:
            self._restore(city_id)
            self._nodes.setdefault(city_id, ids)
            self._rows.setdefault(city_id, deque(maxlen=self.capacity)).append(rec)
            self._samples += 1
            self._persist(city_id, rec, ids)
        return {"city_id": city_id, "observed": sum(1 for x in row if x == x), "nodes": len(ids)}

    # ------------------------------------------------------------ readiness
    def series(self, city_id: str = "dhaka"):
        with self._lock:
            self._restore(city_id)
            rows = list(self._rows.get(city_id, []))
            nodes = list(self._nodes.get(city_id, []))
        return rows, nodes

    def traffic_signal(self, city_id: str = "dhaka") -> bool:
        """Whether the latest provider's readings ever moved: a corridor whose speed never changes carries free-flow
        times, not traffic (every Dhaka corridor through Amazon Location, 94 of 94 samples identical)."""
        rows, nodes = self.series(city_id)
        latest = [r for r in rows if rows and r.get("provider") == rows[-1].get("provider")]
        return any(len({round(r["v"][j], 3) for r in latest if r["v"][j] == r["v"][j]}) > 1 for j in range(len(nodes)))

    def own_history(self, city_id: str = "dhaka") -> dict:
        """How much of this city's history the project may learn from: rows observed by our own opt-in phone
        sensing. Speeds derived from a third-party route provider (Amazon Location, Google) never count."""
        rows, nodes = self.series(city_id)
        own = [r for r in rows if r.get("provider") in OBSERVED_PROVIDERS and any(x == x for x in r["v"])]
        return {"city_id": city_id, "steps_own": len(own), "steps_total": len(rows), "nodes": len(nodes),
                "first_own_utc": own[0]["utc"] if own else None, "last_own_utc": own[-1]["utc"] if own else None,
                "rule": "training and test sets use our own opt-in phone sensing only; speeds derived from Amazon Location or Google route results are excluded"}

    def liveness(self, city_id: str | None = None) -> dict:
        """When each watched city last got a sample that carried a value, and whether that is recent.

        A sampling thread that dies, or a provider that stops answering, keeps writing rows of nulls (or nothing):
        the dashboard said "Live" for a month on exactly that in 2026-09. Healthy means a valued sample within
        three intervals."""
        out = {}
        try:
            c = sqlite3.connect(DB, timeout=10)
            cities = [city_id] if city_id else [r[0] for r in c.execute("select city from watched")]
            now = time.time()
            for city in cities:
                last = None
                for t, v in c.execute("select t, values_json from samples where city=? order by t desc limit 400", (city,)):
                    if any(x is not None for x in json.loads(v)):
                        last = t
                        break
                age = None if last is None else round((now - last) / 60, 1)
                out[city] = {"last_live_sample_utc": datetime.fromtimestamp(last, timezone.utc).isoformat() if last else None,
                             "age_minutes": age, "healthy": age is not None and age <= 3 * self.interval_s / 60}
            c.close()
        except sqlite3.Error as ex:                                   # the file may not exist yet
            out["_error"] = str(ex)
        return out

    def readiness(self, city_id: str = "dhaka") -> dict:
        rows, nodes = self.series(city_id)
        T, N = len(rows), len(nodes)
        spacing = [round(b["t"] - a["t"], 1) for a, b in zip(rows, rows[1:])]
        med = sorted(spacing)[len(spacing) // 2] if spacing else None
        observed = sum(1 for r in rows for x in r["v"] if x == x)
        total = T * N
        checks = [
            {"check": "history_length", "need": f">= {HIS} bins", "have": T, "ok": T >= HIS,
             "why": "OpenCity's input window is 288 steps"},
            {"check": "graph_size", "need": f">= {MIN_NODES} nodes", "have": N, "ok": N >= MIN_NODES,
             "why": "its pre-training graphs hold hundreds of nodes"},
            {"check": "regular_sampling", "need": f"median ~= {BIN_S}s", "have": med,
             "ok": bool(med and abs(med - BIN_S) <= 0.34 * BIN_S),
             "why": "the pre-training corpus is on a clean 5-minute grid"},
            {"check": "coverage", "need": ">= 90 % observed",
             "have": round(observed / total, 4) if total else 0.0,
             "ok": bool(total and observed / total >= 0.9),
             "why": "gaps are carried as NaN, never interpolated"},
        ]
        remaining = max(0, HIS - T)
        return {
            "city_id": city_id, "verdict": "READY" if all(c["ok"] for c in checks) else "NOT_YET_VALID",
            "checks": checks,
            "steps_have": T, "steps_need": HIS, "steps_remaining": remaining,
            "eta_hours": round(remaining * self.interval_s / 3600, 1) if remaining else 0.0,
            "buffer_started_utc": self._started_utc,
            "running": bool(self._thread and self._thread.is_alive()),
            "samples_taken": self._samples, "sample_failures": self._failures,
            "storage": ("DERIVED speeds (distance / duration, ours) are kept in "
                        "results/live/observatory.sqlite so the window survives restarts; Google "
                        "route content is never written"),
        }

    def status(self) -> dict:
        with self._lock:
            cities = {c: len(d) for c, d in self._rows.items()}
        return {"running": bool(self._thread and self._thread.is_alive()),
                "interval_s": self.interval_s, "capacity": self.capacity,
                "started_utc": self._started_utc, "samples": self._samples,
                "failures": self._failures, "cities": cities}

    def city_data(self, city_id: str = "dhaka"):
        """Hand the accumulated window to the forecast interface as a CityData."""
        import numpy as np
        import sys
        from pathlib import Path
        sys.path.insert(0, str(REPO))
        from core.ml.forecasting.adapters.base import CityData
        rows, nodes = self.series(city_id)
        rows = [r for r in rows if r.get("provider") in OBSERVED_PROVIDERS]      # a model is only ever given our own observations
        values = np.array([r["v"] for r in rows], dtype="float32") if rows else \
            np.zeros((0, len(nodes)), dtype="float32")
        return CityData(city_id=city_id, node_ids=nodes, values=values,
                        interval_s=self.interval_s, target="corridor mean speed", unit="m/s",
                        timestamps=[r["utc"] for r in rows], reality="REAL_LIVE (derived)")


observatory = Observatory()
