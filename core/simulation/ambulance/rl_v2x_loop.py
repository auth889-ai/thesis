"""One SUMO run with the machine-learning signals AND the V2X alert in the same loop (Part A, 2026-10-12; new file, nothing existing changes).

    make run-ambulance-loop                      # 5 seeds x 4 arms, ITS-G5 -> evidence/ambulance_loop/ (summary.json, SHA256SUMS)
    ~/.dhakaflow/venvs/sumo-rl-np1/bin/python core/simulation/ambulance/rl_v2x_loop.py --seeds 11 --arms rl_v2i --tech c_v2x

In one run, on the Dhaka corridor at the thesis's "Dhaka density" level (scale read from evidence/ambulance_rq2/dhaka_density/match.json):
  * the 3 corridor signals are driven by the FROZEN sumo-rl Q-learning agents of RQ3 (rl_signals.py; Q-tables results/emergency/dhaka/rq2/rl/),
    greedy, unchanged (SUMO-RL, MIT, pinned commit checked at run time);
  * the ambulance broadcasts with the existing V2X delivery model (core/networking/v2x/model.py: range, delivery ratio, latency, lifetime per
    technology) to the equipped cars ahead (make-way rule v2, unchanged) and to the junctions as RECEIVERS (V2I);
  * a junction pre-empts ONLY when a message is delivered to it by that model, through the copied adaptive-traffic-signal-rl emergency
    override UNCHANGED (core/simulation/signals/preemption/{emergency,phases}.py via sumo_adapter.SumoPreemption); while it holds the
    junction the Q-learning agent is paused for that junction; after the ambulance has passed, the override releases the junction and the
    agent takes it back (the junction's own programme is restored for the override, since SUMO-RL drives phases by state string).
  * Which junctions are addressed follows EMVLight (Su, Chen, Lu, Pan, "EMVLight: a decentralized reinforcement learning framework for
    efficient passage of emergency vehicles", AAAI 2022, arXiv:2109.05429): the PRIMARY junction (the one the ambulance is entering) and the
    SECONDARY junction (the next one on its route) are the ones informed; no code of EMVLight is used (none is released), the idea only.

Arms on the same seed and traffic: fixed (SUMO's fixed-time programmes, no alert), rl (Q-learning, no alert), rl_v2i (Q-learning + V2X
alert with V2I pre-emption), fixed_v2i (fixed time + the same alert; = the study's alert_preemption arm, run here through the same loop).
Printed per run: seed, technology, messages sent / delivered / lost / out of range at each junction, pre-emption start and end times,
the ambulance's travel time and everyone else's vehicle-hours. Every number is computed in the run; nothing is typed in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
import os  # noqa: E402
import shutil  # noqa: E402


def sumo_env() -> None:
    """sumo-rl insists on SUMO_HOME: the folder of the SUMO in PATH (…/sumo/bin/sumo -> …/sumo). Set only when a run starts, never at import
    (a test imports this module, and the rest of the suite must see the environment it had)."""
    if "SUMO_HOME" not in os.environ:
        exe = shutil.which("sumo")
        if exe:
            os.environ["SUMO_HOME"] = str(Path(exe).resolve().parent.parent)
    os.environ.setdefault("DHAKAFLOW_NO_OBSERVATORY", "1")

from core.simulation.ambulance import rl_signals, service  # noqa: E402

CITY, DEMAND = "dhaka", "dhaka_density"
MATCH = REPO / "evidence/ambulance_rq2/dhaka_density/match.json"
OUT = REPO / "evidence/ambulance_loop"
ARMS = ("fixed", "rl", "rl_v2i", "fixed_v2i")
EMVLIGHT = "Su et al., EMVLight, AAAI 2022, arXiv:2109.05429 (design idea only: primary = the junction being entered, secondary = the next one)"


def dhaka_scale(path: Path = MATCH) -> float:
    return float(json.loads(path.read_text())["chosen_scale"])


def primary_secondary(signals: list[dict], route_index: int) -> list[dict]:
    """EMVLight's two junctions: of the route's signals not yet passed, the first (primary) and the second (secondary)."""
    return [s for s in signals if s["route_index"] >= route_index][:2]


class LoopRun(service.AmbulanceRun):
    """The study's AmbulanceRun with (a) EMVLight's primary/secondary addressing and (b) per-junction message and pre-emption records.
    The alert, make-way and delivery code paths are the parent's, unchanged."""

    def __init__(self, conn, scen, arm, technology, share, seed, cfg=None):
        super().__init__(conn, scen, arm, technology, share, seed, cfg)
        self.all_signals = list(scen["signals"])
        self.tls_ids = {s["tls"] for s in self.all_signals}
        self.per_junction = {s["tls"]: {"sent": 0, "delivered": 0, "lost": 0, "out_of_range": 0} for s in self.all_signals}
        self.events: list[dict] = []                            # {"tls", "what": informed | takeover | released, "t"}
        self._held: set[str] = set()
        self.on_junction_delivered = None                       # called with the junction id the moment a message reaches it, before the override's request

    def _alert(self, t: float) -> None:
        _, index, _ = self._ahead()
        passed = [s for s in self.all_signals if s["route_index"] < index]
        self.scen = {**self.scen, "signals": passed + primary_secondary(self.all_signals, index)}
        try:
            super()._alert(t)
        finally:
            self.scen = {**self.scen, "signals": self.all_signals}

    def _send(self, sender, receiver, t: float) -> bool:
        before = dict(self.msgs)
        ok = super()._send(sender, receiver, t)
        if receiver.id in self.per_junction:
            for k in before:
                self.per_junction[receiver.id][k] += self.msgs[k] - before[k]
            if ok and self.on_junction_delivered:
                self.on_junction_delivered(receiver.id)
        return ok

    def step(self, t: float) -> None:
        informed_before = set(self.informed)
        held_before = set(self._held)
        super().step(t)
        if self.preemption is None:
            return
        for tls in set(self.informed) - informed_before:
            self.events.append({"tls": tls, "what": "informed", "t": t})
        now = set(self.informed) | set(self.preemption.fsms)
        for tls in set(self.preemption.fsms) - held_before:
            self.events.append({"tls": tls, "what": "takeover", "t": t})
        for tls in held_before - now:
            self.events.append({"tls": tls, "what": "released", "t": t})
        self._held = now

    def held(self) -> set[str]:
        """Junctions the override owns right now (informed, or holding): the Q-learning agent is paused for them."""
        return set(self._held)


def _loop_env(out: Path, scale: float, seed: int, ts_ids: list[str], rl: bool, hook, vtype: Path, scen: dict, cfg: dict):
    """SUMO-RL's environment: with `rl` the three signals are the agents' (their programmes rewritten by SUMO-RL, as in rl_signals.run);
    without, `fixed_ts` keeps SUMO's own programmes. A junction in `held` is left to the override: no action, no yellow bookkeeping."""
    sumo_rl, _, _ = rl_signals._sumo_rl()

    class HeldEnv(sumo_rl.SumoEnvironment):
        held: set[str] = set()
        programs: dict[str, str] = {}
        logics: dict = {}

        def _start_simulation(self):                           # the junctions' OWN programmes, read before SUMO-RL rewrites them (greens + its own yellows)
            super()._start_simulation()
            self.programs = {ts: self.sumo.trafficlight.getProgram(ts) for ts in self.ts_ids}
            self.logics = {ts: next(l for l in self.sumo.trafficlight.getAllProgramLogics(ts) if l.programID == self.programs[ts]) for ts in self.ts_ids}

        def _sumo_step(self):
            super()._sumo_step()
            hook(self.sumo, self.sim_step, self)

        def _apply_actions(self, actions):
            super()._apply_actions({ts: a for ts, a in actions.items() if ts not in self.held})

        def _run_steps(self):                                  # SUMO-RL's loop (MIT), with held junctions skipped
            time_to_act = False
            while not time_to_act:
                self._sumo_step()
                for ts in self.ts_ids:
                    if ts in self.held:
                        continue
                    self.traffic_signals[ts].update()
                    if self.traffic_signals[ts].time_to_act:
                        time_to_act = True

    env = HeldEnv(net_file=str(scen["net"]), route_file=f"{scen['routes']},{vtype}", num_seconds=cfg["horizon_s"], time_to_teleport=cfg["sumo"]["time_to_teleport_s"],
                  sumo_seed=seed, ts_ids=ts_ids, additional_sumo_cmd=rl_signals._extra(out, scale, cfg["horizon_s"], cfg), add_system_info=False,
                  add_per_agent_info=False, sumo_warnings=False, use_gui=False, fixed_ts=not rl)
    return env


def run(seed: int, arm: str, technology: str = "its_g5", share: float = 1.0, scale: float | None = None, root: Path = OUT / "runs") -> dict:
    if arm not in ARMS:
        raise ValueError(f"arm must be one of {ARMS}")
    scale = dhaka_scale() if scale is None else scale
    sumo_env()
    _, QLAgent, EpsilonGreedy = rl_signals._sumo_rl()
    rl, v2i = arm.startswith("rl"), arm.endswith("_v2i")
    q = pickle.loads((rl_signals.RQ2 / "rl" / f"q_{DEMAND}_x{scale:g}.pkl").read_bytes())
    ts_ids = list(q)
    out = root / CITY / DEMAND / f"{arm}{'_' + technology + f'_p{int(round(share * 100)):03d}' if v2i else ''}_s{seed}_x{scale:g}"
    out.mkdir(parents=True, exist_ok=True)
    cfg, scen = service.settings(), service.scenario(CITY, DEMAND)
    vtype = service.write_vtype(out / "ambulance_type.rou.xml", cfg)
    state: dict = {}

    def hook(conn, t, env):
        if "run" not in state:
            state["run"] = LoopRun(conn, scen, "alert_preemption" if v2i else "no_alert", technology if v2i else None, share if v2i else 0.0, seed, cfg)
        r = state["run"]
        if rl and v2i and r.on_junction_delivered is None:     # a junction the override is about to drive gets its own programme back first (SUMO-RL drives by state string)
            def restore(tls: str) -> None:
                if tls in env.logics:
                    conn.trafficlight.setProgramLogic(tls, env.logics[tls])
                    conn.trafficlight.setProgram(tls, env.programs[tls])
            r.on_junction_delivered = restore
        r.step(t)
        held = r.held() if rl else set()
        for tls in env.held - held:                            # released: the agent takes the junction back at the next step, from the state showing now
            ts = env.traffic_signals.get(tls)
            if ts is not None:
                ts.next_action_time = env.sim_step + 1
                ts.is_yellow = False
                ts.time_since_last_phase_change = ts.min_green + 1
        env.held = held

    t0 = time.time()
    env = _loop_env(out, scale, seed, ts_ids, rl, hook, vtype, scen, cfg)
    obs = env.reset()
    agents = {}
    if rl:
        agents = {ts: QLAgent(starting_state=env.encode(obs[ts], ts), state_space=env.observation_space, action_space=env.action_space,
                              alpha=0.0, gamma=0.99, exploration_strategy=EpsilonGreedy(initial_epsilon=0.0, min_epsilon=0.0, decay=1.0)) for ts in env.ts_ids}
        for ts in agents:
            agents[ts].q_table = q[ts]
    done, crashed = {"__all__": False}, None
    try:
        while not done["__all__"]:
            if rl:
                s, r, done, _ = env.step(action={ts: agents[ts].act() for ts in agents if ts not in env.held})
                for ts in agents:
                    if ts in env.held or ts not in s:          # held by the override, or not acting this step
                        continue
                    agents[ts].learn(next_state=env.encode(s[ts], ts), reward=r[ts])    # alpha = 0: nothing learnt changes (rl_signals.run)
            else:
                s, r, done, _ = env.step(action={})
    except Exception as e:                                     # noqa: BLE001 - SUMO exited (its bluelight crash): no result
        crashed = str(e)[:200]
    try:
        env.close()
    except Exception:                                          # noqa: BLE001
        pass
    r = state.get("run")
    head = {"city_id": CITY, "demand_id": DEMAND, "arm": arm, "signals": "sumo-rl Q-learning (frozen)" if rl else "SUMO fixed-time programmes", "signals_controlled": ts_ids,
            "v2i": v2i, "technology": technology if v2i else None, "equipped_share": share if v2i else 0.0, "seed": seed, "scale": scale, "design": EMVLIGHT if v2i else None,
            "wall_s": round(time.time() - t0, 1), "run_utc": datetime.now(timezone.utc).isoformat(),
            **(r.summary() if r else {}), "messages_per_junction": r.per_junction if r else {}, "preemption_events": r.events if r else []}
    m = {**head, "state": "sumo_crashed", "crash": crashed, "ambulance": {"arrived": False, "travel_time_s": None}, "others": None, "teleports": None} if crashed \
        else {**head, **service.trip_metrics(out, cfg["horizon_s"])}
    (out / "metrics.json").write_text(json.dumps(m, indent=1))
    (out / "edgedata.xml").unlink(missing_ok=True)
    return m


def say_run(m: dict, log) -> None:
    amb, oth = m.get("ambulance") or {}, m.get("others") or {}
    lines = [f"seed {m['seed']}  arm {m['arm']:9s}  tech {m['technology'] or '-':7s}  ambulance {amb.get('travel_time_s')} s  others {oth.get('total_vehicle_hours')} veh-h"
             f"  teleports {m.get('teleports')}  {'SUMO CRASHED: ' + str(m.get('crash'))[:60] if m.get('state') == 'sumo_crashed' else ''}"]
    for tls, c in (m.get("messages_per_junction") or {}).items():
        ev = {e["what"]: e["t"] for e in m.get("preemption_events", []) if e["tls"] == tls}
        lines.append(f"    junction {tls[:40]:40s} sent {c['sent']:3d} delivered {c['delivered']:3d} lost {c['lost']:3d} out of range {c['out_of_range']:3d}"
                     f"  informed {ev.get('informed')} s  takeover {ev.get('takeover')} s  released {ev.get('released')} s")
    for s in lines:
        print(s, flush=True); log.write(s + "\n"); log.flush()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, nargs="+", default=[11, 12, 13, 14, 15], help="seeds wanted complete; a seed SUMO crashes on is recorded and the next one tried")
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=ARMS)
    ap.add_argument("--tech", default="its_g5", choices=["its_g5", "c_v2x", "cellular_4g"])
    ap.add_argument("--share", type=float, default=1.0)
    ap.add_argument("--max-seeds", type=int, default=30)
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    log = open(OUT / "run.log", "a")
    scale = dhaka_scale()
    print(f"AMBULANCE LOOP {datetime.now(timezone.utc).isoformat()}: Dhaka corridor at scale {scale:g} (match.json), arms {a.arms}, {a.tech}, {int(a.share * 100)} % equipped, "
          f"{len(a.seeds)} complete seeds wanted from seed {a.seeds[0]}; {EMVLIGHT}", flush=True)
    rows, crashed, seed = [], [], a.seeds[0]
    while len(rows) < len(a.seeds) and seed < a.seeds[0] + a.max_seeds:
        row, ok = {"seed": seed}, True
        for arm in a.arms:
            m = run(seed, arm, a.tech, a.share, scale)
            say_run(m, log)
            if m.get("state") == "sumo_crashed":
                crashed.append({"seed": seed, "arm": arm, "crash": m.get("crash")}); ok = False
                break
            row[arm] = {"ambulance_s": m["ambulance"]["travel_time_s"], "arrived": m["ambulance"]["arrived"], "others_vehicle_hours": m["others"]["total_vehicle_hours"],
                        "teleports": m["teleports"], "messages": m.get("messages"), "messages_per_junction": m["messages_per_junction"], "preemption_events": m["preemption_events"]}
        if ok:
            rows.append(row)
        seed += 1

    def med(arm, key):
        v = [r[arm][key] for r in rows if arm in r and r[arm][key] is not None]
        return statistics.median(v) if v else None

    summary = {"generated_utc": datetime.now(timezone.utc).isoformat(), "label": "SIMULATION, Dhaka corridor at the thesis's Dhaka-density level", "scale": scale, "tech": a.tech, "share": a.share,
               "design": EMVLIGHT, "seeds_completed": [r["seed"] for r in rows], "seeds_crashed_in_sumo": crashed, "rows": rows,
               "median_ambulance_s": {arm: med(arm, "ambulance_s") for arm in a.arms}, "median_others_vehicle_hours": {arm: med(arm, "others_vehicle_hours") for arm in a.arms},
               "median_saving_s_vs_fixed": {arm: (statistics.median([r["fixed"]["ambulance_s"] - r[arm]["ambulance_s"] for r in rows if r["fixed"]["ambulance_s"] and r[arm]["ambulance_s"]])
                                                  if "fixed" in a.arms and arm != "fixed" and any(r["fixed"]["ambulance_s"] and r[arm]["ambulance_s"] for r in rows) else None) for arm in a.arms}}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    s = json.dumps({k: summary[k] for k in ("seeds_completed", "seeds_crashed_in_sumo", "median_ambulance_s", "median_others_vehicle_hours", "median_saving_s_vs_fixed")}, indent=1)
    print(s, flush=True); log.write(s + "\ndone\n"); log.close()
    files = ["summary.json", "run.log"] + sorted(str(p.relative_to(OUT)) for p in (OUT / "runs").rglob("metrics.json"))
    (OUT / "SHA256SUMS").write_text("".join(f"{hashlib.sha256((OUT / f).read_bytes()).hexdigest()}  {f}\n" for f in files))   # after the log's last line
    return 0


if __name__ == "__main__":
    sys.exit(main())
