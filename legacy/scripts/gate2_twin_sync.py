#!/usr/bin/env python3
"""GATE 2 — TWIN_SYNC_PASS: observed state configures the twin; compare at t0."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from research.twin.scenario_sync import synchronize  # noqa

state = json.loads((REPO / "artifacts/gates/REAL_STATE_PASS.json")
                   .read_text())["detail"]["B_congestion"]
registry = json.loads((REPO / "configs/cameras/registry.json").read_text())
camera = registry["cameras"]["070E28355CAM1RP2"]
out = REPO / "artifacts/gates"
rep = synchronize(state, camera, seed=11, out_dir=out / "twin_sync")
rep["gate"] = "TWIN_SYNC_PASS"
rep["verdict"] = "PASS" if all(rep["checks"].values()) else "FAIL"
(out / "TWIN_SYNC_PASS.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({k: rep[k] for k in
                  ("verdict", "checks", "observed", "sim_queue_at_t0",
                   "sim_arrival_rate_h", "target_rate_h", "geh_flow",
                   "demand_scale_consumed", "target_edge")}, indent=1))
sys.exit(0 if rep["verdict"] == "PASS" else 1)
