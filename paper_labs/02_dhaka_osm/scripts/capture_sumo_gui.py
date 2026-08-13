#!/usr/bin/env python3
"""Capture sumo_gui_dhaka.png — a real sumo-gui frame of the running R1 scenario.

Lightweight local visual inspection (allowed on Mac with XQuartz): loads the
validated network + synthetic routes, advances to mid-simulation so vehicles
are visible, and saves a screenshot through TraCI's gui API.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "lab02_v2"
PNG = OUT / "figures" / "sumo_gui_dhaka.png"


def main() -> int:
    import traci

    net = OUT / "network" / "dhaka_r1.net.xml"
    routes = OUT / "demand" / "routes_seed42.rou.xml"
    traci.start(["sumo-gui", "-n", str(net), "--route-files", str(routes),
                 "--seed", "42", "--start", "--quit-on-end",
                 "--window-size", "1400,1200", "--delay", "0"])
    try:
        view = traci.gui.getIDList()[0]
        traci.gui.setSchema(view, "real world")
        # advance until a healthy number of vehicles is on the network
        while traci.simulation.getTime() < 900:
            traci.simulationStep()
        traci.gui.setZoom(view, 100)
        traci.gui.screenshot(view, str(PNG))
        traci.simulationStep()          # flush the screenshot
        time.sleep(1.0)
    finally:
        traci.close()
    ok = PNG.exists() and PNG.stat().st_size > 10_000
    print(f"screenshot: {PNG} ({'ok' if ok else 'MISSING'})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
