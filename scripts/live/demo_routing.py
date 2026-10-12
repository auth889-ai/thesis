"""make demo-routing (2026-10-12): the RQ2 forecast-routing loop as a two-window demo, the loop unchanged.

    PYTHONPATH=.:backend python scripts/live/demo_routing.py [--seed 201] [--profile 4g] [--minutes 15] [--delay 120] [--no-gui]

Two sumo-gui windows from the SAME fork state and the SAME seed: LEFT = the loop's baseline arm (no server, no rerouting), RIGHT = the
predictive arm (Graph WaveNet + correction + decision rules) over the chosen radio profile (default 4g: the cellular server <-> car link).
Each window is scripts/live/gui_routing.py --demo in its own process (the loop's runner uses one TraCI connection per process); this script
only prepares the shared fork state once, starts the two, and prints the comparison from their result files:
  * cars: yellow connected, white not, green flash = status delivered, BLUE for the rest of the run = advised route applied, red flash = lost advice;
  * cellular base-station POI; RED short lines = a status being sent (one in 25 drawn), GREEN lines = an advice received, grey X = advice lost
    (the red/green message-line and blue-rerouted convention of Eclipse MOSAIC's and Veins' visualisers; nothing of theirs is run or copied);
  * priced edges coloured by corrected forecast speed / limit: green >= 70 %, orange 40-70 %, red < 40 %;
  * a matplotlib window per round: forecast vs corrected vs the real METR-LA speeds for the three busiest mapped sensors, with MAE;
  * narrated PHASE lines with live counts in this terminal.
Output: evidence/live_runs/demo_routing/<stamp>/ (both arms' run folders, gui_routing_run_<arm>.json, forecast_round_*.png, demo_routing.json).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
OUT = REPO / "evidence/live_runs/demo_routing"
GUI = REPO / "scripts/live/gui_routing.py"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=201)
    ap.add_argument("--profile", default="4g", choices=["ideal", "its-g5", "c-v2x", "4g"])
    ap.add_argument("--minutes", type=int, default=15)
    ap.add_argument("--delay", type=float, default=120.0, help="sumo-gui delay per step, ms: slow enough to watch")
    ap.add_argument("--connected-share", type=float, default=None)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    spec = importlib.util.spec_from_file_location("gui_routing", GUI); gr = importlib.util.module_from_spec(spec); spec.loader.exec_module(gr)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (a.out or (OUT / stamp)).resolve(); root.mkdir(parents=True, exist_ok=True)
    print(f"DEMO (RQ2 forecast routing, Los Angeles twin, SIMULATION): seed {a.seed}, profile {a.profile}, {a.minutes} min after the fork; preparing the demand draw and the ONE fork state both windows start from ...", flush=True)
    pre = gr.prepare(argparse.Namespace(seed=a.seed, profile=a.profile, minutes=a.minutes, connected_share=a.connected_share), root)
    P = pre["P"]
    print(f"  fork state {pre['fork'][1][:12]}… at {P['fork_t0_s']} s; {pre['dinfo']['vehicles']} vehicles; {int(P['penetration'] * 100)} % connected; profile {pre['reg'].get(a.profile, 'ideal link')}", flush=True)
    common = [sys.executable, str(GUI), "--seed", str(a.seed), "--minutes", str(a.minutes), "--delay", str(a.delay), "--out", str(root), "--demo", "--window-size", "860,900"]
    if a.connected_share is not None:
        common += ["--connected-share", str(a.connected_share)]
    if a.no_gui:
        common.append("--no-gui")
    left = common + ["--arm", "baseline", "--profile", a.profile, "--window-pos", "0,30", "--title", "LEFT · BASELINE: no server, no rerouting"]
    right = common + ["--arm", gr.ARM, "--profile", a.profile, "--window-pos", "880,30", "--title", f"RIGHT · PREDICTIVE + {a.profile}"]
    t0 = time.time()
    print("  starting LEFT (baseline) and RIGHT (predictive) ...", flush=True)
    pl = subprocess.Popen(left, cwd=REPO, stdout=open(root / "left.log", "w"), stderr=subprocess.STDOUT)
    pr = subprocess.Popen(right, cwd=REPO)                     # the predictive window's narration goes to this terminal
    rc_r = pr.wait(); rc_l = pl.wait()
    res = {}
    for arm in ("baseline", gr.ARM):
        f = root / f"gui_routing_run_{arm}.json"
        res[arm] = json.loads(f.read_text()) if f.exists() else None
    b, p = res["baseline"], res[gr.ARM]
    if b and p:
        mb, mp = b["metrics"], p["metrics"]
        print("", f"COMPARISON (same fork, same seed {a.seed}, {a.minutes} min): baseline {mb['total_vehicle_hours_incl_never_inserted']:.1f} vehicle-hours, arrived {mb['arrived']} | predictive + {a.profile}"
              f" {mp['total_vehicle_hours_incl_never_inserted']:.1f} vehicle-hours ({mp['total_vehicle_hours_incl_never_inserted'] - mb['total_vehicle_hours_incl_never_inserted']:+.1f}), arrived {mp['arrived']};"
              f" statuses {p['loop']['uplink_delivered']}/{p['loop']['uplink_tx']} delivered, advice {p['loop']['downlink_delivered']}/{p['loop']['downlink_tx']} delivered, reroutes applied {p['loop']['reroutes_applied']};"
              f" screen counters = loop log: {'SAME' if p['same'] else 'DIFFERENT'}", sep="\n", flush=True)
    (root / "demo_routing.json").write_text(json.dumps({"args": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()}, "exit": {"left": rc_l, "right": rc_r}, "baseline": b and b["metrics"],
                                                        "predictive": p and {"metrics": p["metrics"], "loop": p["loop"], "same": p["same"]}, "wall_s": round(time.time() - t0)}, indent=1, default=str))
    return 0 if (rc_l == 0 and rc_r == 0) else 2


if __name__ == "__main__":
    sys.exit(main())
