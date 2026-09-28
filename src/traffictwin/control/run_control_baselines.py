#!/usr/bin/env python3
"""Control-gate baselines on the calibrated R1 twin: fixed-time vs Max-Pressure.

Fairness (Lab 01 rules): identical network, identical demand (the converged
E4 v200 route set — 3,000 trips, contention-verified), identical horizon;
only the controller differs. N simulation seeds per arm.

Controllers are the FROZEN Lab 01 implementations imported read-only
(BASELINE_IMPLEMENTATION classification). Timings are the
LAB01_VALIDATED_REFERENCE_PROFILE (min 10 s / max 45 s), declared synthetic-
profile values — not real Dhaka timings (none exist; IMPORTED_HEURISTIC
programs remain the fixed-time arm's plans).

    python3 run_control_baselines.py --arm fixed_time|max_pressure --seeds 1 2 3
Outputs per run: tripinfo-derived metrics JSON.
"""
from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "paper_labs" / "01_sumo_foundation" / "src"))

NET = REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz"
ROUTES = Path("/tmp/due_routes.rou.xml.gz")     # staged on the VM (E4 v200 DUE)
END_S = 10800


def run_arm(arm: str, seed: int, out_dir: Path) -> dict:
    import traci
    from sumolib import checkBinary

    trip_out = out_dir / f"tripinfo_{arm}_{seed}.xml"
    cmd = [checkBinary("sumo"), "-n", str(NET), "-r", str(ROUTES),
           "--seed", str(seed), "--end", str(END_S),
           "--tripinfo-output", str(trip_out),
           "--no-warnings", "--no-step-log", "--time-to-teleport", "300"]
    traci.start(cmd)

    controllers = []
    if arm == "max_pressure":
        from dhakaflow_lab01.controllers.base import ControllerConfig
        from dhakaflow_lab01.controllers.max_pressure import MaxPressureController
        for tls in traci.trafficlight.getIDList():
            cfg = ControllerConfig(tls_id=tls)     # LAB01 reference profile
            controllers.append(MaxPressureController(cfg))

    t = 0.0
    while traci.simulation.getMinExpectedNumber() > 0 and t < END_S:
        traci.simulationStep()
        t = traci.simulation.getTime()
        for c in controllers:
            c.step(traci, t)
    traci.close()

    # tripinfo metrics
    tree = ET.parse(trip_out)
    losses = [float(x.get("timeLoss")) for x in tree.getroot()]
    durs = [float(x.get("duration")) for x in tree.getroot()]
    return {"arm": arm, "seed": seed, "arrived": len(losses),
            "mean_time_loss_s": statistics.mean(losses),
            "mean_duration_s": statistics.mean(durs),
            "total_time_loss_s": sum(losses)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True,
                    choices=["fixed_time", "max_pressure"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", type=Path, default=Path("/tmp/control_baselines"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in args.seeds:
        r = run_arm(args.arm, s, args.out)
        print(json.dumps(r))
        rows.append(r)
    summary = {
        "arm": args.arm, "seeds": args.seeds,
        "network": "dhaka_r1 (frozen)", "demand": "E4 v200 DUE converged, fixed",
        "controller_provenance": ("LAB01 frozen implementation, read-only import"
                                  if args.arm == "max_pressure"
                                  else "SUMO IMPORTED_HEURISTIC programs"),
        "mean_time_loss_s": statistics.mean(r["mean_time_loss_s"] for r in rows),
        "per_seed": rows,
    }
    (args.out / f"summary_{args.arm}.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"SUMMARY": summary["mean_time_loss_s"]}, indent=2))


if __name__ == "__main__":
    main()
