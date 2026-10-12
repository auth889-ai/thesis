"""Addition B (2026-10-12): SUMO's own plotting tools, called unchanged on a finished run's outputs by scripts/routing/plot_run.py."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_plot_run_uses_sumos_tools_on_a_run_folder(tmp_path):
    run = REPO / "evidence/live_runs/demo_routing/pytest_latest/s201/predictive_corrected_v2x"
    if not (run / "edgedata.xml").exists():
        pytest.skip("no finished demo run on this machine")
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "MPLBACKEND": "Agg"}
    r = subprocess.run([sys.executable, str(REPO / "scripts/routing/plot_run.py"), str(run), "--out", str(tmp_path)], capture_output=True, text=True, env=env, timeout=600, cwd=REPO)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert list(tmp_path.glob("speed_map-*.png")) and (tmp_path / "running_vehicles.png").exists() and (tmp_path / "mean_speed.png").exists()
    assert "tools/visualization" in r.stdout                        # the scripts that ship with SUMO, not a copy
