"""Part E (2026-10-12): scripts/live/gui_ambulance_loop.py shows rl_v2x_loop.py's run without changing it. Headless, seed 11, arm rl_v2i
(about 1-2 minutes in sumo-rl's venv): the run's own metrics equal the saved loop evidence for that seed and arm, message for message."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RL_PY = Path.home() / ".dhakaflow/venvs/sumo-rl-np1/bin/python"


def test_gui_ambulance_loop_headless_reproduces_the_saved_loop_run():
    if not RL_PY.exists():
        pytest.skip("sumo-rl venv not on this machine")
    saved = REPO / "evidence/ambulance_loop/runs/dhaka/dhaka_density/rl_v2i_its_g5_p100_s11_x0.78/metrics.json"
    if not saved.exists():
        pytest.skip("no saved loop run for seed 11")
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "DHAKAFLOW_NO_OBSERVATORY": "1"}
    r = subprocess.run([str(RL_PY), str(REPO / "scripts/live/gui_ambulance_loop.py"), "--no-gui", "--seed", "11", "--arm", "rl_v2i"], capture_output=True, text=True, env=env, timeout=900, cwd=REPO)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    runs = sorted((REPO / "evidence/live_runs/gui_ambulance_loop").glob("*/last_run.json"))
    rec = json.loads(runs[-1].read_text()); s = json.loads(saved.read_text())
    m = rec["metrics"]
    assert m["ambulance"]["travel_time_s"] == s["ambulance"]["travel_time_s"] and m["messages"] == s["messages"] and m["messages_per_junction"] == s["messages_per_junction"]
    assert [e["what"] for e in m["preemption_events"]] == [e["what"] for e in s["preemption_events"]]
    assert any(e["result"] == "delivered" for e in rec["events_to_junctions"])             # the printed events include the deliveries
    assert "gui-ambulance-loop:" in (REPO / "Makefile").read_text() and "gui_ambulance_loop" not in (REPO / "scripts/live/present.py").read_text()
