"""make run-twin (step E, 2026-10-11): the live twin in the browser. Starts the app server if it is not up (port 8011, as make present),
opens /app/lab/live-twin and prints what to do; the twin itself runs on the server, computed now, labelled SIMULATION.

    python scripts/live/run_twin.py [--no-browser]
"""
from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/live"))
import present  # noqa: E402

WHAT = """LIVE TWIN (SIMULATION, computed now on this machine; docs/EXPLAIN.md):
  1. Press "Start the twin": the seed comes from the clock and is shown; 15 simulated minutes warm up at full speed.
  2. Click "places a crash" and tap a road with cars: the nearest car stops (red) and blocks its lane.
  3. Click "starts an ambulance there" and tap the avenue: the ambulance (white) drives to the hospital; alerted cars turn orange
     and make way (rule v2); the counter shows messages sent / delivered, cars alerted, signals green, time so far.
  4. Move "Traffic demand"; the forecasters' errors fill the chart below the map 15 simulated minutes after the first predictions.
  5. Switch on "Steer traffic with the forecast": rerouted cars turn blue (the measured effect is in docs/EXPLAIN.md: none reliable).
  The ambulance here drives without SUMO's bluelight device (the thesis runs keep it); the info line says so."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    log = REPO / "evidence/live_runs/run_twin_server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    srv = present.start_server(log)
    url = present.LOCAL + "app/lab/live-twin"
    print(WHAT, flush=True)
    print(f"\n  {url}   (Ctrl-C here ends the server this command started)", flush=True)
    if not a.no_browser:
        webbrowser.open(url)
    try:
        while srv is not None:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        if srv:
            srv.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
