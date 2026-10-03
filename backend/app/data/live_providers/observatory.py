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

from app.data import reference_corridors as _corridors
from app.evidence_paths import REPO

# The derived speeds are OUR numbers (distance / duration, computed here), so they may be kept.
# Keeping them is what lets the 288-step window ever be reached: a buffer that dies with the
# process can never count past one uptime. Google route content is still never written.
DB = REPO / "results/live/observatory.sqlite"

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
        return c

    def _restore(self, city_id: str) -> None:
        """Load the persisted window once per city, before anything reads or appends."""
        if city_id in self._restored:
            return
        self._restored.add(city_id)
        try:
            with self._conn() as c:
                rows = c.execute("SELECT t, utc, nodes, values_json FROM samples WHERE city=? "
                                 "ORDER BY t DESC LIMIT ?", (city_id, self.capacity)).fetchall()
        except sqlite3.Error:
            return
        if not rows:
            return
        rows.reverse()
        nodes = json.loads(rows[-1][2])
        d = self._rows.setdefault(city_id, deque(maxlen=self.capacity))
        for t, utc, n, v in rows:
            if json.loads(n) == nodes:
                d.append({"t": float(t), "utc": utc, "v": [float("nan") if x is None else float(x)
                                                         for x in json.loads(v)]})
        self._nodes.setdefault(city_id, nodes)

    def _persist(self, city_id: str, row: dict, nodes: list[str]) -> None:
        try:
            with self._conn() as c:
                c.execute("INSERT OR IGNORE INTO samples VALUES (?,?,?,?,?)",
                          (city_id, row["t"], row["utc"], json.dumps(nodes),
                           json.dumps([None if x != x else round(x, 4) for x in row["v"]])))
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
        from app.data.live_providers.live import provider
        service = provider()
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
        rec = {"t": time.time(), "utc": datetime.now(timezone.utc).isoformat(), "v": row}
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
        from app.forecasting.adapters.base import CityData
        rows, nodes = self.series(city_id)
        values = np.array([r["v"] for r in rows], dtype="float32") if rows else \
            np.zeros((0, len(nodes)), dtype="float32")
        return CityData(city_id=city_id, node_ids=nodes, values=values,
                        interval_s=self.interval_s, target="corridor mean speed", unit="m/s",
                        timestamps=[r["utc"] for r in rows], reality="REAL_LIVE (derived)")


observatory = Observatory()
