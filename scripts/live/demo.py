"""make demo: the presentation's live parts, one after another, each started when the presenter presses Enter (step F, 2026-10-11).
Every part is a real run computed now; nothing is replayed. `make present` (the timed 7-step run) is unchanged.

    python scripts/live/demo.py [--only v2x,veins] [--list]

Parts, in the order of the talk:
  1 v2x       make run-v2x ARGS="--gui-colours"          sumo-gui: ambulance green, alerted cars yellow, live counter; THESIS CHECK at the end
  2 veins     make gui-veins                            OMNeT++ Qtenv next to sumo-gui: 802.11p frames animated (Veins's numbers, a second view)
  3 signals   make run-signals                          two sumo-gui windows: fixed time against Q-learning; THESIS CHECK
  4 twin      /app/lab/live-twin                        the browser: Start the twin, click a crash and an ambulance, switch on "Steer traffic with the forecast"
  5 mesh      make gui-mesh                             The ONE's own window: press Play; phones meet, messages spread (legend in the terminal)
  6 collide   make run-sos-collide                      a real collision in SUMO, detected by SUMO; crashed cars red, warned yellow, rerouted blue
  7 aid       make aid-gui                              sumo-gui: the trained model watches the loops; incident red, detections in the label
  8 model-lab /app/lab/model-lab + the terminal          one forecast computed now, checked against RQ1's saved window
  9 map       /                                         the map app: Hospitals → "Live reach: tap the map"; a trip → "Use this phone's crash sensor"
At any prompt: Enter runs the part, s skips it, q quits. The app server is started if it is not up (port 8011).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts/live"))
import present  # noqa: E402  (its server start and LOCAL address)
import run_v2x  # noqa: E402  (its saved() reads the study's metrics.json for the settings `make run-v2x` uses)

PY = sys.executable
V2X_SEED = 11                                                  # run_v2x's default --seed; the saved run that part 1 reproduces


def v2x_saved_text() -> str:
    """The watch text's numbers, read from the study's saved runs (results/emergency/dhaka/rq2/runs*/.../metrics.json, key
    ambulance.travel_time_s) for exactly the settings `make run-v2x` uses by default; never typed in (hardcode audit, 2026-10-11)."""
    demand, scale = run_v2x.LEVELS["dhaka"]
    s0, s1 = run_v2x.saved("no_alert", None, 0.0, V2X_SEED, demand, scale), run_v2x.saved("alert_preemption", "its_g5", 1.0, V2X_SEED, demand, scale)
    if not (s0 and s1):
        return "the study has no saved run with these settings; the result is new (not a thesis number)"
    return f"REPRODUCED exactly (seed {V2X_SEED}, {s0['ambulance']['travel_time_s']:g} s -> {s1['ambulance']['travel_time_s']:g} s)"


PARTS = [
    ("v2x", "1 · Ambulance V2X alert (RQ3) with --gui-colours", ["make", "run-v2x", 'ARGS=--gui-colours --speed 8'],
     "Watch sumo-gui: the ambulance (green) and the cars that heard it (yellow) within 100 m making way; the label counts alerted / rerouted / delay.\n"
     f"  At the end the terminal prints THESIS CHECK: {v2x_saved_text()}."),
    ("veins", "2 · The same scenario in Veins (OMNeT++ Qtenv), a second view", ["make", "gui-veins"],
     "Press RUN (F5) in the OMNeT++ window: lines between cars are 802.11p frames in the air; sumo-gui shows the same traffic. Its numbers are Veins's, not the thesis's."),
    ("signals", "3 · Smart signals: fixed time against Q-learning (RQ3)", ["make", "run-signals", "ARGS=--speed 14"],
     "Two windows side by side; the labels count cars halting at the corridor's junctions; the table at the end, then THESIS CHECK for both sides."),
    ("twin", "4 · Live twin with live forecasting, and steering (the browser)", None,
     "Press Start the twin; after the warm-up click a road to place a crash, click the avenue to start an ambulance; switch on \"Steer traffic with the forecast\" (rerouted cars turn blue).\n  Below the map: the three forecasters' errors as they are scored."),
    ("mesh", "5 · Phone-to-phone mesh in The ONE's own window (RQ4, a second view)", ["make", "gui-mesh"],
     "Press Play: blue squares are the 17 phones, green circles their 10 m range, black lines connections, red lines a message copy passing."),
    ("collide", "6 · A real collision in SUMO, then the car-to-car SOS", ["make", "run-sos-collide", "ARGS=--speed 8 --after 300"],
     "One car drives into the car ahead; SUMO detects the contact (red); the warning spreads (yellow) and warned cars reroute (blue)."),
    ("aid", "7 · Incident detection by the trained model, live in SUMO", ["make", "aid-gui", "ARGS=--seed 12"],
     "The label counts detections, warned and rerouted; a stopped car is red. At Dhaka's density the model rarely fires: that is the finding (features/aid/README.md)."),
    ("model-lab", "8 · Traffic prediction: the Model Lab (RQ1)", [PY, "-m", "core.ml.forecasting.layer.lab", "--sensor", "5"],
     "The page opens; the same forecast is computed in the terminal and checked against RQ1's saved window (REPRODUCED)."),
    ("map", "9 · The map app: live hospital reach and the phone's crash sensor", None,
     "Hospitals chip -> switch on \"Live reach: tap the map\" -> tap a point: the nearest hospitals' 10/20/30-minute areas, computed now by Valhalla.\n  Plan a trip, Start -> \"Use this phone's crash sensor\" (on a phone over HTTPS): live g; a jolt starts the TEST countdown; nothing is sent."),
]
URLS = {"twin": "app/lab/live-twin", "model-lab": "app/lab/model-lab", "map": ""}


def ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma-separated part keys")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    parts = [p for p in PARTS if not a.only or p[0] in a.only.split(",")]
    if a.list:
        for k, title, cmd, _ in parts:
            print(f"{k:10s} {title:62s} {' '.join(cmd) if cmd else 'browser: ' + present.LOCAL + URLS[k]}")
        return 0
    srv = present.start_server(REPO / "evidence/live_runs/demo_server.log")
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "LOCAL_URL": present.LOCAL}
    print(f"\nDEMO: {len(parts)} parts, each a live run. The app is at {present.LOCAL}. Enter = run, s = skip, q = quit.\n")
    try:
        for k, title, cmd, watch in parts:
            print(f"\n{'=' * 78}\n{title}\n{'=' * 78}\n  What to watch: {watch}")
            ans = ask("  Enter to start, s to skip, q to quit > ")
            if ans == "q":
                break
            if ans == "s":
                continue
            if k in URLS:
                webbrowser.open(present.LOCAL + URLS[k])
            if cmd:
                subprocess.run(cmd, cwd=REPO, env=env)
            if k in URLS and not cmd:
                ask("  Enter when this part is over > ")
    finally:
        if srv:
            srv.terminate()
    print("\nDEMO ended.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
