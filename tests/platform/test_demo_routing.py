"""make demo-routing (2026-10-12): both arms from the same fork, headless; the predictive window's counters equal the loop's own log and the
baseline arm never reroutes. About 3 minutes of SUMO (two 10-minute branches in parallel)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_demo_routing_headless_two_arms_same_fork():
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "DHAKAFLOW_NO_OBSERVATORY": "1", "MPLBACKEND": "Agg"}
    out = REPO / "evidence/live_runs/demo_routing" / "pytest_latest"
    r = subprocess.run([sys.executable, str(REPO / "scripts/live/demo_routing.py"), "--no-gui", "--minutes", "10", "--seed", "201", "--profile", "4g", "--out", str(out)],
                       capture_output=True, text=True, env=env, timeout=1800, cwd=REPO)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    d = json.loads((out / "demo_routing.json").read_text())
    b = json.loads((out / "gui_routing_run_baseline.json").read_text()); p = json.loads((out / "gui_routing_run_predictive_corrected_v2x.json").read_text())
    assert p["same"] and p["counters"]["rounds"] >= 2 and p["loop"]["reroutes_applied"] > 0 and p["counters"]["uplink_lost"] > 0      # 4g: 4 % loss shows
    assert b["loop"]["reroutes_applied"] == 0 and b["loop"]["uplink_tx"] == 0                                                     # the baseline has no server
    assert d["exit"] == {"left": 0, "right": 0} and b["metrics"]["arrived"] > 0 and p["metrics"]["arrived"] > 0
    assert all(r_["bands"]["green"] + r_["bands"]["orange"] + r_["bands"]["red"] > 0 for r_ in p["rounds"])
    assert "demo-routing:" in (REPO / "Makefile").read_text() and "demo_routing" not in (REPO / "scripts/live/present.py").read_text()
