"""Part D (2026-10-12): scripts/live/gui_routing.py drives RQ2's closed loop unchanged and only displays it. Headless, 15 simulated minutes
after the fork (about 3-4 minutes of SUMO): the screen counters are non-zero and equal the loop's own message log and reroute count."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_gui_routing_headless_counters_match_the_loops_own_log():
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "DHAKAFLOW_NO_OBSERVATORY": "1"}
    out = REPO / "evidence/live_runs/gui_routing" / "pytest_latest"                     # inside the repo: the loop records paths relative to it
    r = subprocess.run([sys.executable, str(REPO / "scripts/live/gui_routing.py"), "--no-gui", "--minutes", "15", "--seed", "201", "--out", str(out)],
                       capture_output=True, text=True, env=env, timeout=1500, cwd=REPO)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    rec = json.loads((out / "gui_routing_run.json").read_text())
    c, loop = rec["counters"], rec["loop"]
    assert rec["same"] and c["rounds"] >= 3 and c["uplink_delivered"] > 0 and c["downlink_tx"] > 0 and c["reroutes_applied"] > 0
    assert all(c[k] == loop[k] for k in loop)                       # what the screen showed is what the loop logged
    assert all(r_["forecast_mae_mph_15min"] is not None and r_["forecast_mae_mph_15min"] >= 0 for r_ in rec["rounds"])
    assert "gui-routing:" in (REPO / "Makefile").read_text() and "gui_routing" not in (REPO / "scripts/live/present.py").read_text()
