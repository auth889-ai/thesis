#!/usr/bin/env python3
"""Run the P0 vertical slice. Usage: python scripts/run_vertical_slice.py [--quick]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dhakaflow.services.vertical_slice import SliceConfig, run_vertical_slice

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="dhaka_r1")
    ap.add_argument("--origin", default="-188458229#0")     # selected: speed>=8m/s, diverse alternatives exist
    ap.add_argument("--destination", default="-326284058#3")
    ap.add_argument("--vehicles", type=int, default=200)
    ap.add_argument("--alternatives", type=int, default=3)
    ap.add_argument("--sim-end", type=float, default=1200.0)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42])
    ap.add_argument("--out", default="artifacts/p0_vertical_slice")
    ap.add_argument("--quick", action="store_true", help="tiny run for wiring checks")
    a = ap.parse_args()
    if a.quick:
        a.vehicles, a.sim_end, a.alternatives = 40, 300.0, 2
    cfg = SliceConfig(city_id=a.city, origin_edge=a.origin, destination_edge=a.destination,
                      n_alternatives=a.alternatives, n_vehicles=a.vehicles,
                      sim_end_s=a.sim_end, seeds=tuple(a.seeds),
                      explicit_splits=((0.55, 0.25, 0.20),) if a.alternatives >= 3 else (),
                      out_dir=Path(a.out))
    r = run_vertical_slice(cfg)
    print(json.dumps({k: r[k] for k in ("stage","city","od_pair","alternatives","selection","runtime_s")}, indent=2))
    print("artifact:", r["artifact"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
