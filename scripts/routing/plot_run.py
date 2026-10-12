"""SUMO's own plotting tools on a finished routing run (2026-10-12, owner's addition B): an edge-speed map and a time plot.

    PYTHONPATH=.:backend python scripts/routing/plot_run.py <run folder with edgedata.xml and summary.xml> [--net NET] [--out DIR]

Calls, unchanged, two scripts that ship with SUMO (EPL-2.0, $SUMO_HOME/tools/visualization): plot_net_dump.py (the network coloured and
widened by a measure from an edgeData dump: here mean speed per edge over the run's last 300 s interval) and plotXMLAttributes.py (an
attribute against time from an XML output: here the number of running vehicles and the mean speed from summary.xml). The run's own
edgedata.xml comes from the loop's edgeData output (freq 300 s, core/simulation/twin/runtime.py base_cmd); nothing is added to the loop.
Output: <out>/speed_map-<interval begin>.png (one per edgeData interval), <out>/running_vehicles.png, <out>/mean_speed.png.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def sumo_home() -> Path:
    if os.environ.get("SUMO_HOME"):
        return Path(os.environ["SUMO_HOME"])
    import sumo
    return Path(os.path.dirname(sumo.__file__))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", type=Path, help="a run folder (…/s<seed>/<arm>) holding edgedata.xml and summary.xml")
    ap.add_argument("--net", type=Path, default=None, help="the network file; default: read from the run's PROTOCOL.json two levels up")
    ap.add_argument("--out", type=Path, default=None, help="default: the run folder")
    a = ap.parse_args(argv)
    run = a.run.resolve(); out = (a.out or run).resolve(); out.mkdir(parents=True, exist_ok=True)
    net = a.net
    if net is None:
        proto = run.parent.parent / "PROTOCOL.json"
        net = REPO / json.loads(proto.read_text())["network"]
    sh = sumo_home(); tools = sh / "tools" / "visualization"
    env = os.environ | {"SUMO_HOME": str(sh), "MPLBACKEND": "Agg"}
    cmds = {
        "speed_map.png": [sys.executable, str(tools / "plot_net_dump.py"), "-n", str(net), "-i", f"{run / 'edgedata.xml'},{run / 'edgedata.xml'}", "-m", "speed,speed",
                          "--min-width", "0.5", "--max-width", "3", "--colormap", "RdYlGn", "--color-bar-label", "mean speed (m/s), last interval", "--blind", "-o", str(out / "speed_map.png")],
        "running_vehicles.png": [sys.executable, str(tools / "plotXMLAttributes.py"), str(run / "summary.xml"), "-x", "time", "-y", "running", "--xelem", "step", "--yelem", "step", "--label", "running vehicles", "-o", str(out / "running_vehicles.png")],
        "mean_speed.png": [sys.executable, str(tools / "plotXMLAttributes.py"), str(run / "summary.xml"), "-x", "time", "-y", "meanSpeed", "--xelem", "step", "--yelem", "step", "--label", "mean speed (m/s)", "-o", str(out / "mean_speed.png")],
    }
    ok = True
    for name, cmd in cmds.items():
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=REPO)
        made = (out / name).exists() or any(out.glob(name.replace(".png", "-*.png")))      # plot_net_dump writes one file per dump interval: speed_map-<begin>.png
        ok &= made and r.returncode == 0
        print(f"  {name}: {'written' if made else 'NOT written'} (exit {r.returncode}) {r.stderr.strip().splitlines()[-1][:160] if r.returncode and r.stderr.strip() else ''}", flush=True)
    print(f"SUMO tools (EPL-2.0, {tools}) on {run.relative_to(REPO) if REPO in run.parents else run} -> {out}", flush=True)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
