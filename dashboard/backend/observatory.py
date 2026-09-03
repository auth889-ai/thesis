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

import threading
import time
from collections import deque
from datetime import datetime, timezone

import corridors as _corridors

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
        self._started_utc: str | None = None
        self._samples = 0
        self._failures = 0

    # ----------------------------------------------------------- lifecycle
    def start(self, city_id: str = "dhaka") -> dict:
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop.clear()
        self._started_utc = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._loop, args=(city_id,), daemon=True)
        self._thread.start()
        return self.status()

    def stop(self) -> dict:
        self._stop.set()
        return self.status()

    def _loop(self, city_id: str) -> None:
        while not self._stop.is_set():
            try:
                self.sample(city_id)
            except Exception:                       # noqa: BLE001 - a bad tick must not kill it
                with self._lock:
                    self._failures += 1
            self._stop.wait(self.interval_s)

    # ------------------------------------------------------------- sampling
    def sample(self, city_id: str = "dhaka") -> dict:
        """Take one live reading and append DERIVED speeds. Gaps stay NaN, never interpolated."""
        from live import service
        snap = service.corridors()
        ids = [c["id"] for c in _corridors.CORRIDORS]
        row = [float("nan")] * len(ids)
        idx = {c: i for i, c in enumerate(ids)}
        for c in snap.get("corridors", []):
            i = idx.get(c.get("id"))
            if i is None or not c.get("is_live"):
                continue
            dist, dur = c.get("distance_m"), c.get("duration_s")
            if dist and dur and dur > 0:
                row[i] = dist / dur                  # m/s, derived by us
        with self._lock:
            self._nodes.setdefault(city_id, ids)
            self._rows.setdefault(city_id, deque(maxlen=self.capacity)).append(
                {"t": time.time(), "utc": datetime.now(timezone.utc).isoformat(), "v": row})
            self._samples += 1
        return {"city_id": city_id, "observed": sum(1 for x in row if x == x), "nodes": len(ids)}

    # ------------------------------------------------------------ readiness
    def series(self, city_id: str = "dhaka"):
        with self._lock:
            rows = list(self._rows.get(city_id, []))
            nodes = list(self._nodes.get(city_id, []))
        return rows, nodes

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
            "storage": ("in-memory ring of DERIVED speeds; Google route content is never written "
                        "to disk, so a restart resets the window"),
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
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from pipeline.forecasting.adapters.base import CityData
        rows, nodes = self.series(city_id)
        values = np.array([r["v"] for r in rows], dtype="float32") if rows else \
            np.zeros((0, len(nodes)), dtype="float32")
        return CityData(city_id=city_id, node_ids=nodes, values=values,
                        interval_s=self.interval_s, target="corridor mean speed", unit="m/s",
                        timestamps=[r["utc"] for r in rows], reality="REAL_LIVE (derived)")


observatory = Observatory()
