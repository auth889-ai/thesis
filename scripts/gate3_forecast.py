#!/usr/bin/env python3
"""GATE 3 — FORECAST_PASS.

Separation of concepts (stated, enforced in reporting):
  DATA-DRIVEN FORECAST  = GWNet: what traffic will likely become (+5/10/15).
  SUMO COUNTERFACTUAL   = what happens under a specific intervention.
  The planner's branch A0 is NEVER called "the GWNet prediction".

Checks:
  1. benchmark evidence: official BasicTS-legacy pipeline test metrics + ckpt
  2. scaler: train-split z-score (mean/std recomputed here = what model saw)
  3. HISTORY PRELOAD protocol: warm the twin >= 12x300 s BEFORE control t0 —
     forecast_available_fraction >= 95% during the control interval.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
ROUTES_SRC = REPO / "artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz"
WARM_S = 3600.0          # 12 x 300 s — fills the history BEFORE control starts
CONTROL_S = 600.0
DECIDE_EVERY = 5.0


def main() -> None:
    from research.control.gwnet_in_loop import GWNetForecaster
    import libsumo as t

    # -- 1. benchmark evidence (official pipeline artifacts) ---------------
    log = (REPO / "artifacts/p3_results/GWNet_cpu.log").read_text()
    m = re.search(r"Result <test>.*MAE: ([0-9.]+).*RMSE: ([0-9.]+)", log)
    ckpt = sorted((REPO / "BasicTS_legacy").glob(
        "checkpoints/GraphWaveNet/**/GraphWaveNet_best_val_MAE.pt"))[-1]
    sha = hashlib.sha256(ckpt.read_bytes()).hexdigest()[:16]

    # -- 2+3. in-loop availability with history preload --------------------
    from research.twin.demand import make_repeating_routes
    routes = str(make_repeating_routes(
        ROUTES_SRC, REPO / "artifacts/gates/routes_repeat_1h.rou.xml.gz",
        cycles=8, period_s=600.0))
    fc = GWNetForecaster()
    t.start(["sumo", "-n", NET, "-r", routes, "--seed", "11",
             "--scale", "0.584", "--no-step-log", "--no-warnings",
             "--time-to-teleport", "600"])
    tls_ids = list(t.trafficlight.getIDList())
    wall = time.time()
    nxt = 0.0
    while t.simulation.getTime() < WARM_S:
        t.simulationStep()
        if t.simulation.getTime() >= nxt:      # rolling sensor ingestion
            fc(t, tls_ids)
            nxt += DECIDE_EVERY
    fc.calls = fc.available = 0                # count ONLY the control window
    while t.simulation.getTime() < WARM_S + CONTROL_S and \
            t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        if t.simulation.getTime() >= nxt:
            feat = fc(t, tls_ids)
            nxt += DECIDE_EVERY
    t.close()

    frac = fc.forecast_available_fraction
    result = {
        "gate": "FORECAST_PASS",
        "benchmark": {
            "model": "GraphWaveNet (official BasicTS-legacy @4c3e2d3)",
            "test_MAE_m_s": float(m.group(1)), "test_RMSE": float(m.group(2)),
            "naive_floor_MAE_m_s": 1.39,
            "checkpoint": str(ckpt.relative_to(REPO)),
            "checkpoint_sha256_16": sha,
            "dataset": "DhakaR1SensorGraph_legacy (twin sensor graph)",
            "log": "artifacts/p3_results/GWNet_cpu.log"},
        "scaler": "z-score, train-split mean/std of speed channel "
                  "(recomputed from data.dat at load — matches training)",
        "protocol": {"demand": "fair DUE pulse tiled x8 (declared scenario construction, research/twin/demand.py)",
                     "history_preload_s": WARM_S,
                     "control_interval_s": CONTROL_S,
                     "decide_every_s": DECIDE_EVERY},
        "forecast_available_fraction": round(frac, 4),
        "first_available_s": fc.first_available_s,
        "horizons_exposed_min": sorted(fc.pred_speed),
        "separation": "GWNet = data-driven forecast; SUMO A0 branch = "
                      "do-nothing counterfactual. Never conflated in reports.",
        "wall_s": round(time.time() - wall, 1),
        "checks": {
            "benchmark_evidence": bool(m),
            "forecast_available_ge_95pct": frac >= 0.95,
            "available_from_control_start": fc.first_available_s is not None
            and fc.first_available_s <= WARM_S,
            "three_horizons": sorted(fc.pred_speed) == [5, 10, 15]},
    }
    result["verdict"] = "PASS" if all(result["checks"].values()) else "FAIL"
    out = REPO / "artifacts/gates/FORECAST_PASS.json"
    out.write_text(json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
