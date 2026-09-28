#!/usr/bin/env python3
"""Sweep one knob of the chain and write a curve, not a number.

    python src/pipeline/routing/chain_sweep.py --grid compliance --seeds 11,12,13,14,15
    python src/pipeline/routing/chain_sweep.py --grid v2x        --seeds 11,12,13,14,15
    python src/pipeline/routing/chain_sweep.py --grid v2x --compliance 0.1,0.3,0.6   # the heatmap

Every point is a full run_chain() execution (three arms, all seeds), so every point carries its
own run_id and per-seed agreement. The output is the classic penetration-rate curve of the
rerouting literature, on this project's chain, with error bars from the seeds.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from traffictwin.protocols.chains import integrated_chain as ic     # noqa: E402

RESULTS = REPO / "results/routing"
COMPLIANCE = [0.0, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0]


def point(rec: dict) -> dict:
    """Per arm: mean and stdev of vehicle-hours over seeds, and % vs baseline paired per seed."""
    by = {}
    for r in rec["runs"]:
        by.setdefault(r["arm"], {})[r["seed"]] = r["metrics"]
    out = {}
    for arm, per_seed in by.items():
        vh = [m["total_vehicle_hours"] for m in per_seed.values()]
        pct = [((per_seed[s]["total_vehicle_hours"] - by["baseline"][s]["total_vehicle_hours"])
                / (by["baseline"][s]["total_vehicle_hours"] or 1) * 100)
               for s in per_seed if s in by.get("baseline", {})]
        out[arm] = {
            "vehicle_hours_mean": round(statistics.fmean(vh), 2),
            "vehicle_hours_sd": round(statistics.stdev(vh), 2) if len(vh) > 1 else 0.0,
            "vs_baseline_pct_mean": round(statistics.fmean(pct), 2) if pct else 0.0,
            "vs_baseline_pct_sd": round(statistics.stdev(pct), 2) if len(pct) > 1 else 0.0,
            "seeds_improved": sum(1 for x in pct if x < 0), "n_seeds": len(pct),
            "mean_queue_veh": round(statistics.fmean(m.get("mean_queue_veh") or 0
                                                     for m in per_seed.values()), 2),
            "teleports": round(statistics.fmean(m["teleports"] for m in per_seed.values()), 1),
        }
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--grid", choices=["compliance", "v2x"], required=True)
    p.add_argument("--seeds", default="11,12,13,14,15")
    p.add_argument("--horizon", type=int, default=1800)
    p.add_argument("--compliance", default=None,
                   help="compliance values; default = the standard curve for --grid compliance, "
                        "0.3 for --grid v2x")
    p.add_argument("--v2x", default=None, help="v2x conditions; default = all four")
    p.add_argument("--forecast-kind", default="model", choices=sorted(ic.FORECAST_KINDS))
    p.add_argument("--as-of", default="peak")
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()

    comp = ([float(x) for x in a.compliance.split(",")] if a.compliance
            else (COMPLIANCE if a.grid == "compliance" else [0.3]))
    v2x = a.v2x.split(",") if a.v2x else (sorted(ic.V2X) if a.grid == "v2x" else ["ideal"])
    out = a.out or RESULTS / f"sweep_{a.grid}.json"

    points = []
    for c in comp:
        for v in v2x:
            print(f"\n[sweep] compliance={c:.2f} v2x={v}", flush=True)
            rec = ic.run_chain(seeds=a.seeds, horizon=a.horizon, compliance=c, v2x=v,
                               as_of=a.as_of, forecast_kind=a.forecast_kind,
                               tag=f"sw_{a.grid}_c{int(c * 100):03d}_{v}")
            points.append({"compliance": c, "v2x": v, "delivery_fraction": rec["delivery_fraction"],
                           "run_id": rec["run_id"], "arms": point(rec)})
    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(), "grid": a.grid,
           "seeds": a.seeds, "horizon_s": a.horizon, "forecast_kind": a.forecast_kind,
           "forecast_model": None, "points": points,
           "label": "SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin",
           "command": f"python src/pipeline/routing/chain_sweep.py --grid {a.grid} --seeds {a.seeds}"}
    out.write_text(json.dumps(rec, indent=1, default=str))
    print(f"\n{'compliance':>10} {'v2x':>9} {'deliv':>6} | {'reactive %':>11} {'pred-aware %':>13} {'seeds':>6}")
    for pt in points:
        r, q = pt["arms"].get("reactive", {}), pt["arms"].get("prediction_aware", {})
        print(f"{pt['compliance']:>10.2f} {pt['v2x']:>9} {pt['delivery_fraction']:>6.3f} | "
              f"{r.get('vs_baseline_pct_mean', 0):>+7.2f}±{r.get('vs_baseline_pct_sd', 0):<4.2f} "
              f"{q.get('vs_baseline_pct_mean', 0):>+8.2f}±{q.get('vs_baseline_pct_sd', 0):<4.2f} "
              f"{q.get('seeds_improved', 0)}/{q.get('n_seeds', 0)}")
    print(f"[sweep] wrote {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
