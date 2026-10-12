"""make demo-ambulance: one ambulance trip on the Dhaka corridor, without and with the V2X alert, same seed, in SUMO's own window.

    python scripts/demo/ambulance.py [--record DIR] [--no-gui]

Runs the study's own code (core/simulation/ambulance/service.py run_one) with the study's settings (configs/ambulance.yaml:
make-way rule v2, ITS-G5, every car equipped, the Dhaka-level demand x0.78, seed 11). Colours are display only. At the end the
two travel times are compared with the saved study runs for the same seed (results/emergency/dhaka/rq2/).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.simulation.ambulance import service  # noqa: E402

CITY, DEMAND, SEED, SCALE, TECH, SHARE = "dhaka", "dhaka_density", 11, 0.78, "its_g5", 1.0
SAVED = REPO / "results/emergency/dhaka/rq2"
OUT = REPO / "evidence/demo/ambulance"
ORANGE = (255, 150, 0, 255)
VIEW = """<viewsettings>
  <scheme name="demo">
    <background backgroundColor="white" showGrid="0"/>
    <edges laneEdgeMode="0" laneShowBorders="1" showLinkDecals="1" showRails="1" hideConnectors="0"/>
    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="1" vehicle_exaggeration="2.5" showBlinker="1" vehicleColor="200,200,200"/>
    <junctions junctionMode="0" drawLinkTLIndex_show="0" drawLinkJunctionIndex_show="0" showLane2Lane="0"/>
  </scheme>
</viewsettings>
"""


class Arrived(Exception):
    pass


def say(*lines: str) -> None:
    print("\n".join(lines), flush=True)


def saved(arm: str, tech, share: float) -> float | None:
    root = SAVED / ("runs" if arm == "no_alert" else "runs_v2")
    f = root / CITY / DEMAND / (service.run_name(arm, tech, share, SEED) + f"_x{SCALE:g}") / "metrics.json"
    return json.loads(f.read_text())["ambulance"]["travel_time_s"] if f.exists() else None


def study_line() -> str:
    """The study's own result at Dhaka's density over all its seeds, from its summary (never typed in)."""
    p = json.loads((SAVED / "summary.json").read_text())["plain"]
    sig = (f"smarter (Q-learning) signals saved about {p['signals_s']} s" if p["signals_s"] >= 0 else f"smarter (Q-learning) signals made it about {-p['signals_s']} s later")
    return (f"  Over all {p['alert_runs']} paired seeds at Dhaka's density, the alert saved a median {p['alert_s']} s on a {p['trip_s']} s trip, "
            f"but {p['slower_runs']} of {p['alert_runs']} runs were slower than the siren alone;\n  {sig}. One seed is not the result.")


def ambulance_time(out: Path) -> float | None:
    for t in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
        if t.get("id") == service.AMBULANCE:
            return float(t.get("duration"))
    return None


def gui_hook(record: Path | None, depart_s: float):
    """Display only: follow the ambulance, slow down near its departure, colour cars while they make way, stop at arrival."""
    painted: set[str] = set()
    state = {"slow": False, "frame": 0}

    def hook(conn, t, run):
        if not state["slow"] and t >= depart_s - 20:
            state["slow"] = True
        if state["slow"] and not record:
            time.sleep(0.12)                                   # about 8 simulated seconds per real second, to watch
        if service.AMBULANCE in conn.vehicle.getIDList():
            if run.departed == t:
                conn.gui.trackVehicle("View #0", service.AMBULANCE)
                conn.gui.setZoom("View #0", 2500)
            now = set(run.makeway.before)
            for v in now - painted:
                conn.vehicle.setColor(v, ORANGE)
            for v in painted - now:
                if v in conn.vehicle.getIDList():
                    conn.vehicle.setColor(v, (200, 200, 200, 255))
            painted.clear(); painted.update(now)
        if record and state["slow"]:
            conn.gui.screenshot("View #0", str(record / f"f{state['frame']:05d}.png"))
            state["frame"] += 1
        if run.state == "arrived":
            raise Arrived(conn)
    return hook


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", type=Path, help="save one GUI frame per simulated second into this folder (for the video)")
    ap.add_argument("--no-gui", action="store_true")
    a = ap.parse_args()
    say("DEMO: an ambulance crosses the Dhaka corridor twice, same traffic (seed 11): first with no alert, then with the alert.",
        "  With the alert, cars within 100 m ahead get a V2X message and move aside (orange), and the junctions ahead turn green.",
        "SOFTWARE: Eclipse SUMO 1.27.1 (simulator and its bluelight settings), TraCI, our V2X delivery model (ITS-G5, ETSI EN 302 637-2).",
        "PAPERS: make-way settings from SUMO's MSDevice_Bluelight and docs 'Emergency'; signal pre-emption adapter from atsc-rl (upstream",
        "  reproduced); the 100 m alert distance is our own choice (no paper gives it). Demand: generated, at Dhaka's measured density.", "")
    cfg = service.settings()
    if cfg["alert"].get("makeway", {}).get("version") != 2:
        say("STOP: configs/ambulance.yaml is not make-way rule v2."); return 1
    root = OUT / "runs"
    say("1/2 Without alert (no window, about 30 s) ...")
    m0 = service.run_one(CITY, "no_alert", None, 0.0, SEED, DEMAND, root=root, scale=SCALE)
    t0 = m0["ambulance"]["travel_time_s"]
    say(f"    ambulance travel time without alert: {t0} s", "")
    say("2/2 With alert and green signals" + (" (no window)" if a.no_gui else ": SUMO window opens; ambulance = white with a green cross, orange = a car making way") + " ...")
    if a.record:
        a.record.mkdir(parents=True, exist_ok=True)
    (OUT / "view.xml").parent.mkdir(parents=True, exist_ok=True)
    (OUT / "view.xml").write_text(VIEW)
    out = root / CITY / DEMAND / (service.run_name("alert_preemption", TECH, SHARE, SEED) + f"_x{SCALE:g}")
    try:
        if a.no_gui:
            t1 = service.run_one(CITY, "alert_preemption", TECH, SHARE, SEED, DEMAND, root=root, scale=SCALE)["ambulance"]["travel_time_s"]
        else:
            service.run_one(CITY, "alert_preemption", TECH, SHARE, SEED, DEMAND, root=root, scale=SCALE, sumo_binary="sumo-gui",
                            gui_options=("--start", "--quit-on-end", "--window-size", "1600,1000", "--delay", "0", "--gui-settings-file", str(OUT / "view.xml")),
                            hook=gui_hook(a.record, cfg["ambulance"]["depart_s"]))
            t1 = None
    except Arrived:
        pass                                                   # run_one closed SUMO, which wrote the ambulance's trip
        t1 = None
    if t1 is None:
        t1 = ambulance_time(out)
    s0, s1 = saved("no_alert", None, 0.0), saved("alert_preemption", TECH, SHARE)
    pct = round(100 * (t0 - t1) / t0, 1) if t0 and t1 else None
    say("", "RESULT (Dhaka corridor, simulation, seed 11):",
        f"  without alert {t0} s, with alert and green signals {t1} s: {pct} % sooner." if pct is not None else "  the ambulance did not arrive in one run.",
        f"  saved study runs for seed 11: without {s0} s, with {s1} s -> " + ("same numbers." if (s0, s1) == (t0, t1) else "DIFFERENT, see above."),
        study_line(), "  (Research page, RQ3; results/emergency/dhaka/rq2/summary.json).")
    (OUT / "last_run.json").write_text(json.dumps({"seed": SEED, "scale": SCALE, "without_s": t0, "with_s": t1, "pct": pct,
                                                   "saved_without_s": s0, "saved_with_s": s1, "match": (s0, s1) == (t0, t1)}, indent=1) + "\n")
    return 0 if (s0, s1) == (t0, t1) else 2


if __name__ == "__main__":
    sys.exit(main())
