"""make run-signals: fixed-time signals against sumo-rl Q-learning on the same Dhaka corridor junctions and seed, two SUMO windows side by side.

    python scripts/live/run_signals.py [--level dhaka|x0.5|x1|x2|x3|x4] [--seed 11] [--speed 8] [--no-gui]

Both runs are computed now, in parallel, by the RQ3 code: left, SUMO's own signal programs (service.run_one, the no-alert ambulance);
right, the frozen Q-tables sumo-rl learnt for this traffic level (rl_signals.run, greedy, unchanged). Each window shows how many
vehicles stand at the corridor's controlled junctions. Each run plays the study's full hour (the measures need it): watched at --speed
around the ambulance's trip, the rest at full speed. At the end: ambulance travel time, queue at the signals, time blocked, vehicle
hours, and, where the study saved runs with the same level and seed, the check that they are equal.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

OUT = REPO / "evidence/live_runs/signals"
RQ2 = REPO / "results/emergency/dhaka/rq2/runs/dhaka"
RL_PY = Path.home() / ".dhakaflow/venvs/sumo-rl-np1/bin/python"
LEVELS = {"dhaka": ("dhaka_density", 0.78), "x0.5": ("generated", 0.5), "x1": ("generated", 1.0), "x2": ("generated", 2.0),
          "x3": ("generated", 3.0), "x4": ("generated", 4.0)}
KEYS = ("travel_time_s", "queue_at_signals", "blocked_s", "total_vehicle_hours")


def say(*lines: str) -> None:
    print("\n".join(lines), flush=True)


def measures(m: dict) -> dict:
    """The compared numbers of one run's metrics. Pure."""
    return {"travel_time_s": m["ambulance"]["travel_time_s"], "queue_at_signals": m["why"]["queue_at_signals"], "blocked_s": m["why"]["blocked_s"],
            "queue_peaks": m["why"]["queue_peaks"], "total_vehicle_hours": (m.get("others") or {}).get("total_vehicle_hours"),
            "mean_time_loss_s": (m.get("others") or {}).get("mean_time_loss_s"), "ev_priority_requests": m.get("ev_priority_requests")}


def saved(side: str, seed: int, demand: str, scale: float) -> dict | None:
    name = ("no_alert" if side == "fixed" else "rl_signals") + f"_s{seed}" + (f"_x{scale:g}" if scale != 1.0 else "")
    f = RQ2 / demand / name / "metrics.json"
    return measures(json.loads(f.read_text())) if f.exists() else None


def display(label: str, speed: float, watch_from: float, gui: bool, frames: Path | None = None):
    """Display only: a label with the vehicles halting at the corridor's controlled junctions; paced while the ambulance is on its way.
    `frames`: the web app's live run (core/simulation/live_jobs) reads one JSON line a second from this file instead of a window."""
    st: dict = {}

    def hook(conn, t, run):
        if not gui and frames is None:
            return
        if "lanes" not in st:
            from core.simulation.ambulance import rl_signals, service
            scen = service.scenario("dhaka", st_demand)
            tls = rl_signals._in_net(rl_signals.corridor_signals(scen, str(scen["net"])), scen["net"])
            st["lanes"] = sorted({l for ts in tls for l in conn.trafficlight.getControlledLanes(ts)})
            st["n"] = len(tls)
            if not gui:
                st["fh"] = frames.open("a")
        if not gui:
            halting = sum(conn.lane.getLastStepHaltingNumber(l) for l in st["lanes"])
            st["fh"].write(json.dumps({"t": int(t), "halting": halting, "junctions": st["n"], "ambulance": run.state}) + "\n"); st["fh"].flush()
            if watch_from <= t and run.state != "arrived":
                time.sleep(1.0 / speed)
            return
        if "hud" not in st:
            st["hud"] = True
            try:
                conn.gui.setSchema("View #0", "live")
            except Exception:                                    # noqa: BLE001 - the settings file may not define it
                pass
            x, y = conn.junction.getPosition(tls[len(tls) // 2]) if tls else (0, 0)
            conn.gui.setOffset("View #0", x, y); conn.gui.setZoom("View #0", 900)
            conn.poi.add("hud", x, y + 120, (0, 0, 0, 0))
        halting = sum(conn.lane.getLastStepHaltingNumber(l) for l in st["lanes"])
        amb = "ambulance driving" if run.state == "driving" else "ambulance arrived" if run.state == "arrived" else "ambulance not yet out"
        conn.poi.setParameter("hud", "label", f"{label}  |  t={int(t)} s  |  halting at the {st['n']} corridor junctions: {halting}  |  {amb}")
        if watch_from <= t and run.state != "arrived":
            time.sleep(1.0 / speed)
    st_demand = None

    def bind(demand: str):
        nonlocal st_demand
        st_demand = demand
        return hook
    return bind


def side_main(a) -> int:
    """One window: 'fixed' in this interpreter, 'rl' in the sumo-rl venv (NumPy < 2, as the study ran it)."""
    demand, scale = LEVELS[a.level]
    root = OUT / "runs"
    gui = not a.no_gui
    pos = "0,30" if a.side == "fixed" else "800,30"
    opts = ["--window-size", "800,860", "--window-pos", pos, "--delay", "0", "--gui-settings-file", str(OUT / "view.xml")]
    watch = 900 - 60
    if a.side == "fixed":
        from core.simulation.ambulance import service
        hook = display("FIXED-TIME (SUMO programs)", a.speed, watch, gui, a.frames)(demand)
        m = service.run_one("dhaka", "no_alert", None, 0.0, a.seed, demand, root=root, scale=scale, observe=True, hook=hook,
                            sumo_binary="sumo-gui" if gui else "sumo", gui_options=tuple(["--start", "--quit-on-end"] + opts) if gui else ())
    elif a.controller in ("maxpressure", "maxpressure_ev"):      # step S (2026-10-11): Max-Pressure in this interpreter, the same junctions as the RL arm
        from core.simulation.ambulance import mp_signals
        hook = display("MAX-PRESSURE (Varaiya 2013)" + (" + EV PRIORITY" if a.controller == "maxpressure_ev" else ""), a.speed, watch, gui, a.frames)(demand)
        m = mp_signals.run(scale, a.seed, a.controller, root=root, demand=demand, hook=hook, sumo_binary="sumo-gui" if gui else "sumo",
                           gui_options=tuple(["--start", "--quit-on-end"] + opts) if gui else ())
    else:
        from core.simulation.ambulance import rl_signals
        hook = display("Q-LEARNING (sumo-rl, frozen)", a.speed, watch, gui, a.frames)(demand)
        m = rl_signals.run(scale, a.seed, "rl_signals", 0.0, root=root, demand=demand, inspect=hook, gui=gui, gui_cmd=" ".join(opts))
    (OUT / f"last_{a.side}.json").write_text(json.dumps(measures(m) | {"state": m.get("state"), "wall_s": m.get("wall_s")}, indent=1) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--level", default="dhaka", choices=list(LEVELS))
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--speed", type=float, default=8.0)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--controller", choices=["rl", "maxpressure", "maxpressure_ev"], default="rl", help="the right window: sumo-rl Q-learning (default), Max-Pressure, or Max-Pressure + EV priority")
    ap.add_argument("--side", choices=["fixed", "rl"], help=argparse.SUPPRESS)
    ap.add_argument("--frames", type=Path, help=argparse.SUPPRESS)              # the web app's live run: one JSON line a second
    a = ap.parse_args(argv)
    if a.side:
        return side_main(a)
    demand, scale = LEVELS[a.level]
    right = {"rl": "sumo-rl's Q-learning signals (tables learnt for this level; frozen, no exploration)",
             "maxpressure": "Max-Pressure (Varaiya 2013; our controller, min green 10 s, max 60 s, the program's own yellow)",
             "maxpressure_ev": "Max-Pressure + EV priority (the junction ahead of the ambulance prefers its approach's green; no V2X message)"}[a.controller]
    say(f"LIVE RUN (RQ3 signals, Dhaka corridor, SIMULATION, level {a.level}, seed {a.seed}): the same traffic and ambulance twice, side by side:",
        f"  left SUMO's fixed-time signal programs, right {right}.",
        "SOFTWARE: Eclipse SUMO 1.27.1 + TraCI; sumo-rl (Alegre, MIT, pinned commit 86f0fc41) tabular Q-learning, independent per junction,",
        "  reward = change in waiting time; the ambulance and the measures are the RQ3 code. Traffic: generated, uncalibrated.", "")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "view.xml").write_text((REPO / "scripts/live/run_v2x.py").read_text().split('VIEW = """')[1].split('"""')[0])
    for f in ("last_fixed.json", "last_rl.json"):
        (OUT / f).unlink(missing_ok=True)
    base = [a.level and "--level", a.level, "--seed", str(a.seed), "--speed", str(a.speed), "--controller", a.controller] + (["--no-gui"] if a.no_gui else [])
    rl_py = str(RL_PY) if a.controller == "rl" else sys.executable
    import sumo                                                    # the study's own environment for the sumo-rl side (study.py, rl stage)
    env = os.environ | {"PYTHONPATH": f"{REPO}:{REPO / 'backend'}", "SUMO_HOME": os.path.dirname(sumo.__file__), "DHAKAFLOW_NO_OBSERVATORY": "1"}
    procs = [subprocess.Popen([sys.executable, __file__, *base, "--side", "fixed"], env=env),
             subprocess.Popen([rl_py, __file__, *base, "--side", "rl"], env=env)]
    say("Both windows run in parallel; the full simulated hour is played (watched at --speed around the ambulance's trip) ...")
    codes = [p.wait() for p in procs]
    if any(codes) or not all((OUT / f).exists() for f in ("last_fixed.json", "last_rl.json")):
        say(f"STOP: a run did not finish (exit codes {codes})."); return 1
    got = {s: json.loads((OUT / f"last_{s}.json").read_text()) for s in ("fixed", "rl")}
    rname = {"rl": "Q-learning", "maxpressure": "Max-Pressure", "maxpressure_ev": "MP + EV prio"}[a.controller]
    say("", f"RESULT of this run (level {a.level}, seed {a.seed}):", f"  {'':28}{'fixed-time':>14}{rname:>14}")
    for k, name in zip(KEYS + ("mean_time_loss_s",), ("ambulance travel time (s)", "queue at the signals (veh)", "ambulance blocked (s)", "all vehicles, hours", "mean time loss, others (s)")):
        say(f"  {name:28}{str(got['fixed'].get(k)):>14}{str(got['rl'].get(k)):>14}")
    if a.controller == "maxpressure_ev":
        say(f"  EV priority requests: {got['rl'].get('ev_priority_requests')}")
    checks = []
    for s in ("fixed", "rl"):
        w = saved(s, a.seed, demand, scale) if (s == "fixed" or a.controller == "rl") else None
        label_ = "fixed" if s == "fixed" else rname
        if w is None:
            say(f"  THESIS CHECK ({label_}): no saved study run with this level and seed" + ("; this result is new." if a.controller == "rl" else "; Max-Pressure is new (step S, 2026-10-11)."))
            continue
        same = all(w[k] == got[s][k] for k in KEYS)
        checks.append(same)
        say(f"  THESIS CHECK ({label_}): saved run {[w[k] for k in KEYS]} -> " + ("REPRODUCED exactly." if same else f"DIFFERENT: {[got[s][k] for k in KEYS]}"))
    (OUT / "last_run.json").write_text(json.dumps({"args": vars(a), "result": got, "checks": checks}, indent=1) + "\n")
    return 0 if all(checks) else 2


if __name__ == "__main__":
    sys.exit(main())
