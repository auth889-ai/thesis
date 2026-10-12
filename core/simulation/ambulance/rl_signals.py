"""RQ2 baseline: SUMO-RL's tabular Q-learning signal controllers (MIT, third_party/SOURCES.md "Ambulance alert, RQ2"), on the signals
within CORRIDOR_M of the ambulance's route; the other signals keep SUMO's programs. SUMO-RL is imported unchanged from its pinned
checkout; this adapter only subclasses SumoEnvironment so that our ambulance hook runs after each simulated second, and passes our
SUMO options through its `additional_sumo_cmd`. Runs in ~/.dhakaflow/venvs/sumo-rl-np1 (NumPy < 2: SUMO-RL's encode() needs it).

    python -m core.simulation.ambulance.rl_signals train --scale 2 --episodes 30        # Q-tables -> results/emergency/dhaka/rq2/rl/q_x2.pkl
    python -m core.simulation.ambulance.rl_signals run --scale 2 --seed 11 --arm rl_signals_alert --share 1.0
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO

CHECKOUT = Path.home() / ".dhakaflow/upstream/sumo-rl"
PINNED = "86f0fc41401eeca724b2e8878f5020dc6d70c9b4"
RQ2 = REPO / "results/emergency/dhaka/rq2"
CORRIDOR_M = 500.0
TRAIN_SEEDS = range(101, 1000)                                     # never the evaluation seeds (11...)
CITY, DEMAND = "dhaka", "generated"


def _sumo_rl():
    head = subprocess.run(["git", "-C", str(CHECKOUT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    if head != PINNED:
        raise RuntimeError(f"sumo-rl checkout is at {head}, not the pinned {PINNED}")
    if str(CHECKOUT) not in sys.path:
        sys.path.insert(0, str(CHECKOUT))
    import sumo_rl
    from sumo_rl.agents import QLAgent
    from sumo_rl.exploration import EpsilonGreedy
    return sumo_rl, QLAgent, EpsilonGreedy


def corridor_signals(scen: dict, net_path: str, radius: float = CORRIDOR_M) -> list[str]:
    """Traffic lights whose junction lies within `radius` of any point of the ambulance's route (sumolib geometry)."""
    import sumolib
    net = sumolib.net.readNet(net_path)
    pts = [p for e in scen["edges"] for p in net.getEdge(e).getShape()]
    out = []
    for tls in net.getTrafficLights():
        nodes = {c[0].getEdge().getToNode() for c in tls.getConnections()}
        if any(math.dist(n.getCoord(), p) <= radius for n in nodes for p in pts):
            out.append(tls.getID())
    return sorted(out)


def _extra(out: Path, scale: float, horizon: int, cfg: dict) -> str:
    add = out / "additional.xml"
    add.write_text('<additional>\n  <edgeData id="ed" file="edgedata.xml" freq="300" excludeEmpty="true"/>\n</additional>\n')
    return " ".join(["--additional-files", str(add), "--scale", str(scale), "--end", str(horizon), "--tripinfo-output", str(out / "tripinfo.xml"),
                     "--tripinfo-output.write-unfinished", "--statistic-output", str(out / "statistic.xml"), "--no-step-log",
                     "--ignore-route-errors", "--device.rerouting.probability", "0", "--lateral-resolution", str(cfg["sumo"]["lateral_resolution"])])


def _env(out: Path, scale: float, seed: int, ts_ids: list[str], hook=None, vtype: Path | None = None, demand: str = DEMAND, gui: bool = False, gui_cmd: str = ""):
    from core.simulation.ambulance import service
    sumo_rl, _, _ = _sumo_rl()
    cfg, scen = service.settings(), service.scenario(CITY, demand)

    class AmbulanceEnv(sumo_rl.SumoEnvironment):
        """SUMO-RL's environment; after each simulated second our hook (the ambulance, the alert, the measures) runs."""
        def _sumo_step(self):
            super()._sumo_step()
            if hook:
                hook(self.sumo, self.sim_step)

    routes = str(scen["routes"]) + (f",{vtype}" if vtype else "")
    env = AmbulanceEnv(net_file=str(scen["net"]), route_file=routes, num_seconds=cfg["horizon_s"], time_to_teleport=cfg["sumo"]["time_to_teleport_s"],
                       sumo_seed=seed, ts_ids=ts_ids, additional_sumo_cmd=_extra(out, scale, cfg["horizon_s"], cfg) + (" " + gui_cmd if gui_cmd else ""),
                       add_system_info=False, add_per_agent_info=False, sumo_warnings=False, use_gui=gui)
    return env, cfg, scen


def _in_net(ts_ids: list[str], net_path) -> list[str]:
    """Only the signals that exist in this network (the corridor keeps fewer)."""
    import sumolib
    have = {t.getID() for t in sumolib.net.readNet(str(net_path)).getTrafficLights()}
    return [t for t in ts_ids if t in have]


def train(scale: float, episodes: int = 30, demand: str = DEMAND) -> Path:
    """Independent Q-learning per corridor signal, background traffic only, SUMO-RL's example settings (alpha 0.1, gamma 0.99,
    epsilon 0.05 -> 0.005). One training seed per episode, none of them an evaluation seed. The Q-tables are kept."""
    from core.simulation.ambulance import service
    _, QLAgent, EpsilonGreedy = _sumo_rl()
    scen = service.scenario(CITY, demand)
    ts_ids = _in_net(corridor_signals(scen, str(scen["net"])), scen["net"])
    tag = f"x{scale:g}" if demand == DEMAND else f"{demand}_x{scale:g}"
    work = RQ2 / "rl" / f"train_{tag}"
    work.mkdir(parents=True, exist_ok=True)
    agents, log = None, []
    for ep in range(episodes):
        env, _, _ = _env(work, scale, TRAIN_SEEDS[ep], ts_ids, demand=demand)
        obs = env.reset()
        if agents is None:
            agents = {ts: QLAgent(starting_state=env.encode(obs[ts], ts), state_space=env.observation_space, action_space=env.action_space,
                                  alpha=0.1, gamma=0.99, exploration_strategy=EpsilonGreedy(initial_epsilon=0.05, min_epsilon=0.005, decay=1.0)) for ts in env.ts_ids}
        else:
            for ts in env.ts_ids:
                agents[ts].state = env.encode(obs[ts], ts)
        done, wait = {"__all__": False}, []
        while not done["__all__"]:
            s, r, done, _ = env.step(action={ts: agents[ts].act() for ts in agents})
            for ts in agents:
                agents[ts].learn(next_state=env.encode(s[ts], ts), reward=r[ts])
            wait.append(sum(env.sumo.lane.getWaitingTime(l) for ts in env.ts_ids for l in env.traffic_signals[ts].lanes))
        env.close()
        log.append({"episode": ep + 1, "seed": TRAIN_SEEDS[ep], "mean_corridor_waiting_s": round(sum(wait) / len(wait), 1)})
        print(f"train x{scale:g} episode {ep + 1}/{episodes}: corridor waiting {log[-1]['mean_corridor_waiting_s']}", flush=True)
    p = RQ2 / "rl" / f"q_{tag}.pkl"
    p.write_bytes(pickle.dumps({ts: a.q_table for ts, a in agents.items()}))
    (RQ2 / "rl" / f"train_{tag}.json").write_text(json.dumps({"scale": scale, "demand": demand, "signals": ts_ids, "episodes": log, "sumo_rl_commit": PINNED,
                                                                    "settings": {"alpha": 0.1, "gamma": 0.99, "epsilon": [0.05, 0.005], "delta_time": 5,
                                                                                 "yellow": 2, "min_green": 5, "max_green": 50, "reward": "diff-waiting-time"}}, indent=1))
    return p


def run(scale: float, seed: int, arm: str, share: float, technology: str = "its_g5", root: Path = RQ2 / "runs", demand: str = DEMAND, inspect=None,
        gui: bool = False, gui_cmd: str = "") -> dict:
    """One evaluation run with the frozen Q-tables of this density level (greedy: no exploration), the ambulance, and for
    rl_signals_alert the alert to equipped vehicles. Metrics in the same form as service.run_one, with RQ2's measures."""
    from core.simulation.ambulance import service
    from core.simulation.ambulance.measures import RouteObserver
    _, QLAgent, EpsilonGreedy = _sumo_rl()
    tag = f"x{scale:g}" if demand == DEMAND else f"{demand}_x{scale:g}"
    q = pickle.loads((RQ2 / "rl" / f"q_{tag}.pkl").read_bytes())
    alert = arm == "rl_signals_alert"
    name = f"{arm}{'_' + technology + f'_p{int(round(share * 100)):03d}' if alert else ''}_s{seed}_x{scale:g}"
    out = root / CITY / demand / name
    out.mkdir(parents=True, exist_ok=True)
    cfg = service.settings()
    vtype = service.write_vtype(out / "ambulance_type.rou.xml", cfg)
    state = {}

    def hook(conn, t):
        if "run" not in state:
            scen = service.scenario(CITY, demand)
            state["run"] = service.AmbulanceRun(conn, scen, "alert" if alert else "no_alert", technology if alert else None, share if alert else 0.0, seed, cfg)
            state["obs"] = RouteObserver(conn, scen, service.AMBULANCE)
        state["run"].step(t)
        state["obs"].step(t, state["run"].state == "driving", state["run"].alerted)
        if inspect:                                                # RQ2c: the per-second inspection log (research/ambulance_rq2/scripts/inspect_dhaka_slow.py)
            inspect(conn, t, state["run"])

    t0 = time.time()
    env, cfg, scen = _env(out, scale, seed, list(q), hook, vtype, demand, gui, gui_cmd)   # gui: the live run (scripts/live/run_signals.py), display only
    obs = env.reset()
    agents = {ts: QLAgent(starting_state=env.encode(obs[ts], ts), state_space=env.observation_space, action_space=env.action_space,
                          alpha=0.0, gamma=0.99, exploration_strategy=EpsilonGreedy(initial_epsilon=0.0, min_epsilon=0.0, decay=1.0)) for ts in env.ts_ids}
    for ts in agents:
        agents[ts].q_table = q[ts]
    done, crashed = {"__all__": False}, None
    try:
        while not done["__all__"]:
            s, r, done, _ = env.step(action={ts: agents[ts].act() for ts in agents})
            for ts in agents:                                       # alpha = 0: SUMO-RL's own learn() only moves to the next state and adds an
                agents[ts].learn(next_state=env.encode(s[ts], ts), reward=r[ts])   # unseen one with zero values; nothing learnt changes
    except Exception as e:                                         # noqa: BLE001 - SUMO exited (the bluelight crash): no result
        crashed = str(e)[:200]
    try:
        env.close()
    except Exception:                                              # noqa: BLE001
        pass
    head = {"city_id": CITY, "demand_id": demand, "arm": arm, "technology": technology if alert else None, "equipped_share": share if alert else 0.0, "seed": seed,
            "scale": scale, "signals": "sumo-rl Q-learning (frozen)", "signals_controlled": len(agents), "wall_s": round(time.time() - t0, 1),
            "run_utc": datetime.now(timezone.utc).isoformat(), **state["run"].summary(), "why": state["obs"].summary()}
    m = {**head, "state": "sumo_crashed", "crash": crashed, "ambulance": {"arrived": False, "travel_time_s": None}} if crashed else {**head, **service.trip_metrics(out, cfg["horizon_s"])}
    (out / "metrics.json").write_text(json.dumps(m, indent=1))
    for big in ("edgedata.xml",):
        (out / big).unlink(missing_ok=True)
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["train", "run", "signals"])
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--episodes", type=int, default=30)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--arm", default="rl_signals", choices=["rl_signals", "rl_signals_alert"])
    ap.add_argument("--share", type=float, default=1.0)
    ap.add_argument("--demand", default=DEMAND)
    ap.add_argument("--root", default=str(RQ2 / "runs"), help="where the run folder goes (RQ2c: results/emergency/dhaka/rq2/runs_v2)")
    a = ap.parse_args()
    if a.cmd == "train":
        print(train(a.scale, a.episodes, a.demand))
    elif a.cmd == "signals":
        from core.simulation.ambulance import service
        sc = service.scenario(CITY, DEMAND)
        print(corridor_signals(sc, str(sc["net"])))
    else:
        print(json.dumps({k: v for k, v in run(a.scale, a.seed, a.arm, a.share, root=Path(a.root), demand=a.demand).items() if k in ("state", "ambulance", "why", "wall_s")}, indent=1))
