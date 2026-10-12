"""Max-Pressure signal control on the corridor's junctions, with optional emergency-vehicle priority (step S, 2026-10-11).

Max-Pressure is Varaiya (2013), 10.1016/j.trc.2013.08.014: at each decision, serve the phase whose green movements carry the largest
pressure, sum over the movements of (queue upstream - queue downstream), with a minimum and maximum green and the program's own yellow.
The controller is our `core/simulation/signals/signal_baselines.MaxPressureController`, written for the signals gate; the two open
implementations surveyed for this step (third_party/SOURCES.md): LibSignal `agent/maxpressure.py` (no licence file: read, not copied)
and RESCO `resco_benchmark/agents/static/maxpressure.py` (GPL-3.0: read, not copied) compute the same quantity with lane vehicle
counts and a minimum phase time; ours uses halting vehicles (the queue), as Varaiya defines it.

EV priority (ours): while the ambulance is driving and within `ahead_m` (the V2X alert's own reach, so the arms are comparable) of a
controlled junction on its route, that junction prefers the green phase that serves the ambulance's approach edge; the switch still
goes through min green and the program's yellow (program-safe), and the preference is dropped once the ambulance has passed.
No V2X message is involved: this is the controller seeing the ambulance (as a detector or a transponder would), not the alert.

    PYTHONPATH=.:backend python -m core.simulation.ambulance.mp_signals --arm maxpressure|maxpressure_ev --seed 11 [--scale 0.78 --demand dhaka_density]

Metrics in the form of service.run_one (observe=True): the ambulance's travel time, RQ3's measures, every other vehicle's hours
and mean time loss. Runs go under evidence/, never into results/ (the saved thesis results are untouched).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.common.paths import REPO
from core.simulation.signals.signal_baselines import MaxPressureController

CITY = "dhaka"
ARMS = ("maxpressure", "maxpressure_ev")
OUT = REPO / "evidence/signals/controllers/runs"


class MaxPressureEV(MaxPressureController):
    """Max-Pressure whose `choose` returns a preferred phase while an emergency vehicle approaches that junction."""

    def __init__(self, t, tls_ids):
        super().__init__(t, tls_ids)
        self.priority: dict[str, int] = {}
        self.requests = 0

    def green_phase_for(self, tls: str, in_edge: str) -> int | None:
        """The green phase serving the most links that enter from `in_edge` (a full green 'G' counts twice a permissive 'g')."""
        d = self.tls[tls]
        best, score = None, 0
        for i in d["greens"]:
            st = d["phases"][i].state
            sc = sum((2 if st[k] == "G" else 1) for k, lk in enumerate(d["links"]) if lk and k < len(st) and st[k] in "Gg" and lk[0][0].rsplit("_", 1)[0] == in_edge)
            if sc > score:
                best, score = i, sc
        return best

    def prefer(self, tls: str, in_edge: str) -> None:
        if tls in self.priority:
            return
        ph = self.green_phase_for(tls, in_edge)
        if ph is not None:
            self.priority[tls] = ph
            self.requests += 1

    def release(self, tls: str) -> None:
        self.priority.pop(tls, None)

    def choose(self, tls) -> int:
        return self.priority[tls] if tls in self.priority else super().choose(tls)


def make_hook(arm: str, tls_ids: list[str], scen: dict, extra_hook=None):
    """The per-step hook for service.run_one: steps the controller; with EV priority, watches the ambulance's distance to each signal."""
    from core.simulation.ambulance import service
    st: dict = {}

    def hook(conn, t, run):
        if "ctrl" not in st:
            st["ctrl"] = MaxPressureEV(conn, tls_ids) if arm == "maxpressure_ev" else MaxPressureController(conn, tls_ids)
            st["lengths"] = [conn.lane.getLength(f"{e}_0") for e in scen["edges"]]
            st["ahead_m"] = run.cfg["alert"]["ahead_m"]
            st["passed"] = set()
        ctrl = st["ctrl"]
        ctrl.step(t)
        if arm == "maxpressure_ev":
            if run.state == "driving" and service.AMBULANCE in conn.vehicle.getIDList():
                road = conn.vehicle.getRoadID(service.AMBULANCE)
                if road in scen["edges"]:
                    idx = scen["edges"].index(road)
                    pos = conn.vehicle.getLanePosition(service.AMBULANCE)
                    for s in scen["signals"]:
                        if s["tls"] not in tls_ids:
                            continue
                        if s["route_index"] < idx:
                            if s["tls"] not in st["passed"]:
                                ctrl.release(s["tls"]); st["passed"].add(s["tls"])
                            continue
                        dist = (st["lengths"][idx] - pos) + sum(st["lengths"][idx + 1:s["route_index"] + 1])
                        if dist <= st["ahead_m"]:
                            ctrl.prefer(s["tls"], s["in_edge"])
            elif run.state == "arrived":
                for s in scen["signals"]:
                    ctrl.release(s["tls"])
        run.mp = {"controller": arm, "signals_controlled": tls_ids, "ev_priority_requests": getattr(ctrl, "requests", 0)}
        if extra_hook:
            extra_hook(conn, t, run)
    return hook


def run(scale: float, seed: int, arm: str, root: Path = OUT, demand: str = "dhaka_density", hook=None, sumo_binary: str = "sumo", gui_options: tuple = ()) -> dict:
    from core.simulation.ambulance import rl_signals, service
    assert arm in ARMS, arm
    scen = service.scenario(CITY, demand)
    tls_ids = rl_signals._in_net(rl_signals.corridor_signals(scen, str(scen["net"])), scen["net"])   # the same junctions the Q-learning arm controls
    holder: dict = {}

    def keep(conn, t, run):
        holder["mp"] = getattr(run, "mp", None)
    m = service.run_one(CITY, "no_alert", None, 0.0, seed, demand, root=root, scale=scale, observe=True, tag=arm, hook=make_hook(arm, tls_ids, scen, lambda c, t, r: (hook(c, t, r) if hook else None, keep(c, t, r))),
                        sumo_binary=sumo_binary, gui_options=gui_options)
    m.update(holder.get("mp") or {"controller": arm, "signals_controlled": tls_ids})
    out = root / CITY / demand / (f"no_alert_s{seed}" + (f"_x{scale:g}" if scale != 1.0 else "") + f"_{arm}")
    if (out / "metrics.json").exists():
        (out / "metrics.json").write_text(json.dumps(m, indent=1))
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=ARMS, default="maxpressure")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--scale", type=float, default=0.78)
    ap.add_argument("--demand", default="dhaka_density")
    a = ap.parse_args()
    m = run(a.scale, a.seed, a.arm, demand=a.demand)
    print(json.dumps({k: m.get(k) for k in ("state", "ambulance", "others", "controller", "signals_controlled", "ev_priority_requests", "wall_s")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
