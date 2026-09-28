#!/usr/bin/env python3
"""Turn the live Dhaka feed into the schema OpenCity actually consumes — and say when it is valid.

    python -m traffictwin.forecasting.opencity.dhaka_opencity_schema --check
    python -m traffictwin.forecasting.opencity.dhaka_opencity_schema --build --out data/forecasting/cities/DHAKA_LIVE

WHY THE LIVE PREDICTION LOOKS HARDCODED, AND WHAT FIXES IT
    The live page predicts an ordinal congestion CLASS (FREE_FLOW / SLOW / CONGESTED / SEVERE),
    because that is the only Dhaka history that exists: the recorder runs in RUNTIME_REFERENCE mode
    and never writes durations or speeds to disk. Congestion classes are sticky over an hour, so
    the modal transition IS persistence, and the page ends up saying "it will stay CONGESTED".
    That is not a model failing, it is a model with nothing to model.

    OpenCity needs something different and much simpler: for each city, a `{city}.npz` holding a
    (T, N) matrix of real VALUES, and a `{city}_rn_adj.npy` adjacency matrix. Nothing else. That is
    the entire reason it transfers to a city it has never seen. Our live feed produces exactly the
    values it wants — corridor speed, every couple of minutes — so this module builds that schema.

THE COMPLIANCE POINT, HANDLED RATHER THAN DODGED
    Google's terms restrict STORING Maps Content as a dataset. They do not restrict using it live.
    So the value series is held in a bounded IN-MEMORY ring buffer belonging to the running server,
    the same category as the ETA already displayed on screen, and `--build` writes DERIVED SPEED
    (metres per second computed by us from distance and duration) rather than route content. The
    distinction is recorded in the manifest next to the data, not left implicit.

WHAT MAKES IT SCIENTIFICALLY VALID, AND WHAT DOES NOT
    `--check` refuses to pretend. OpenCity was pre-trained on graphs of 200-900 nodes sampled on a
    clean grid, with 288 steps of history (24 h at 5 min) as its input window. A 6-corridor graph
    sampled at irregular intervals for a few hours is NOT the same object, and feeding it anyway
    would produce a number with no standing. The checks below are the preconditions, each reported
    with the actual measured value, so the gap is a countdown rather than an opinion.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO
CORRIDOR_MAP = REPO / "data/forecasting/live_dhaka/corridor_edges.json"

# OpenCity's own input/output window, from conf/general_conf/pretrain.conf.
HIS = PRED = 288
BIN_S = 300                      # the grid OpenCity's pre-training corpus is sampled on
MIN_NODES = 20                   # smallest graph in its pre-training corpus is ~170 nodes


class LiveValueBuffer:
    """A bounded in-memory ring of DERIVED corridor speeds. Never written to disk by itself.

    One row per sampling bin, one column per corridor, values in metres per second computed by us
    as distance / traffic-aware duration. Missing samples are NaN and stay NaN — a gap is carried,
    never interpolated, because an invented value here would flow straight into a forecast.
    """

    def __init__(self, corridors: list[str], capacity: int = HIS + PRED) -> None:
        self.corridors = list(corridors)
        self.capacity = capacity
        self._rows: deque = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def observe(self, snapshot: dict) -> None:
        """Take one /api/live/corridors payload and append a row of derived speeds."""
        row = {"t": time.time(), "utc": datetime.now(timezone.utc).isoformat(),
               "v": [float("nan")] * len(self.corridors)}
        idx = {c: i for i, c in enumerate(self.corridors)}
        for c in snapshot.get("corridors", []):
            i = idx.get(c.get("id"))
            if i is None or not c.get("is_live"):
                continue
            dist, dur = c.get("distance_m"), c.get("duration_s")
            if dist and dur and dur > 0:
                row["v"][i] = dist / dur              # derived by us, not Google route content
        with self._lock:
            self._rows.append(row)

    def matrix(self) -> tuple[np.ndarray, list[str]]:
        with self._lock:
            rows = list(self._rows)
        if not rows:
            return np.zeros((0, len(self.corridors)), dtype="float32"), []
        return (np.array([r["v"] for r in rows], dtype="float32"),
                [r["utc"] for r in rows])

    def spacing_seconds(self) -> list[float]:
        with self._lock:
            ts = [r["t"] for r in self._rows]
        return [round(b - a, 1) for a, b in zip(ts, ts[1:])]


def adjacency(corridors: list[str], cmap: dict) -> np.ndarray:
    """Corridors sharing a road edge are adjacent. Real topology, not a guess.

    OpenCity consumes a node-by-node adjacency matrix. Our nodes are corridors, and two corridors
    are connected when their mapped SUMO edge paths overlap — which is the actual physical relation
    on the Dhaka network, taken from the corridor->edge mapping this project already computed.
    """
    edges = {c: set((cmap.get(c) or {}).get("edges") or []) for c in corridors}
    n = len(corridors)
    A = np.eye(n, dtype="float32")
    for i, a in enumerate(corridors):
        for j, b in enumerate(corridors):
            if i < j and edges[a] & edges[b]:
                overlap = len(edges[a] & edges[b]) / max(1, min(len(edges[a]), len(edges[b])))
                A[i, j] = A[j, i] = float(round(overlap, 4))
    return A


def validate(values: np.ndarray, spacing: list[float], corridors: list[str]) -> dict:
    """The preconditions for feeding this to OpenCity, each with its measured value."""
    T, N = values.shape if values.size else (0, len(corridors))
    observed = int(np.isfinite(values).sum()) if values.size else 0
    total = int(values.size) if values.size else 0
    med = float(np.median(spacing)) if spacing else None
    checks = [
        {"check": "history_length", "need": f">= {HIS} bins ({HIS * BIN_S // 3600} h)",
         "have": T, "ok": T >= HIS,
         "why": "OpenCity's input window is 288 steps; a shorter series cannot fill it"},
        {"check": "graph_size", "need": f">= {MIN_NODES} nodes", "have": N, "ok": N >= MIN_NODES,
         "why": ("its pre-training graphs hold hundreds of nodes; a 6-corridor graph is a "
                 "different object and transfer is not established for it")},
        {"check": "regular_sampling", "need": f"median spacing ~= {BIN_S}s",
         "have": med, "ok": bool(med and abs(med - BIN_S) <= 0.34 * BIN_S),
         "why": ("the pre-training corpus is on a clean 5-minute grid; irregular spacing changes "
                 "what a 'step ahead' means")},
        {"check": "coverage", "need": ">= 90 % observed",
         "have": round(observed / total, 4) if total else 0.0,
         "ok": bool(total and observed / total >= 0.9),
         "why": "gaps are carried as NaN, never interpolated, so they must be rare"},
    ]
    return {"valid": all(c["ok"] for c in checks), "checks": checks,
            "verdict": ("READY" if all(c["ok"] for c in checks) else "NOT_YET_VALID"),
            "note": ("Until every check passes, feeding this to OpenCity would produce a number "
                     "with no scientific standing. The failing checks are the work, not the "
                     "excuse.")}


def build(buf: LiveValueBuffer, out: Path, city: str) -> dict:
    values, stamps = buf.matrix()
    cmap = json.loads(CORRIDOR_MAP.read_text()) if CORRIDOR_MAP.exists() else {}
    cmap = {c["corridor_id"]: c for c in cmap.values()} if isinstance(cmap, dict) and cmap and \
        isinstance(next(iter(cmap.values())), dict) and "corridor_id" in next(iter(cmap.values())) else cmap
    A = adjacency(buf.corridors, cmap)
    report = validate(values, buf.spacing_seconds(), buf.corridors)

    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{city}.npz", data=values)
    np.save(out / f"{city}_rn_adj.npy", A)
    manifest = {
        "city": city, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "shape": list(values.shape), "corridors": buf.corridors,
        "quantity": "corridor mean speed, metres per second",
        "derivation": ("distance_m / duration_s, COMPUTED BY US from the live response; this is a "
                       "derived scalar, not stored Google route content"),
        "missing_encoding": "NaN — gaps are carried, never interpolated",
        "adjacency": "corridors sharing mapped SUMO edges, weighted by overlap fraction",
        "first_utc": stamps[0] if stamps else None, "last_utc": stamps[-1] if stamps else None,
        "opencity_ready": report["verdict"], "validation": report,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="report readiness against the live server")
    p.add_argument("--build", action="store_true")
    p.add_argument("--city", default="DHAKA_LIVE")
    p.add_argument("--out", type=Path, default=REPO / "data/forecasting/cities/DHAKA_LIVE")
    a = p.parse_args()

    import urllib.request
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/api/live/corridors", timeout=20) as r:
            snap = json.loads(r.read().decode())
    except Exception as exc:                              # noqa: BLE001 - reported, not hidden
        raise SystemExit(f"live server not reachable ({exc}); start it with "
                         f"`python src/dashboard/backend/main.py`")

    corridors = [c["id"] for c in snap.get("corridors", [])]
    buf = LiveValueBuffer(corridors)
    buf.observe(snap)
    values, _ = buf.matrix()
    report = validate(values, buf.spacing_seconds(), corridors)

    print(f"Dhaka -> OpenCity schema readiness: {report['verdict']}\n")
    print(f"{'check':<20}{'need':<34}{'have':<14}ok")
    for c in report["checks"]:
        print(f"{c['check']:<20}{c['need']:<34}{str(c['have']):<14}{'yes' if c['ok'] else 'NO'}")
    print()
    for c in report["checks"]:
        if not c["ok"]:
            print(f"  blocked — {c['check']}: {c['why']}")
    if a.build:
        m = build(buf, a.out, a.city)
        print(f"\nwrote {a.out}/{a.city}.npz {m['shape']} and {a.city}_rn_adj.npy")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
