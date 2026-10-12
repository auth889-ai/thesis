"""The ambulance alert experiments: one ambulance trip on a city's twin, with and without an alert.

    PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --one                       # one run of each arm, timed
    PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --sweep --demand generated  # every configuration, on the light uncalibrated demand
    PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --sweep --demand calibrated # the same on the partly calibrated demand (hours)

Arms, all on the same network, demand, seed, hour and sublane setting:
  no_alert          the ambulance drives with SUMO's bluelight device only (vehicles within its 25 m react; it runs red lights)
  alert             the ambulance also sends an alert each second; an equipped vehicle ahead on its route that RECEIVES it
                    (the network model decides) makes way early (makeway.py)
  alert_preemption  as alert, and a signalised junction ahead that receives it gives the ambulance's approach green
                    (signals/preemption: the reused override and safety state machine)

Everything here is SIMULATED. No message leaves this process, nothing is dialled and no service is contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import statistics
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import yaml

from core.common.data import city_config
from core.simulation.ambulance.makeway import MakeWay
from core.common.interfaces.safety import SAFETY_PROFILES
from core.networking.v2x import model
from core.networking.v2x.model import Station
from core.common.paths import REPO
from core.simulation.signals.preemption.sumo_adapter import SumoPreemption
from core.simulation.twin import runtime as pr

CONFIG = Path(__file__).parent / "configs/ambulance.yaml"
RESULTS = REPO / "results/emergency"
EVIDENCE = REPO / "evidence/emergency"
AMBULANCE, VTYPE, ROUTE = "ambulance_alert", "ambulance_alert_type", "ambulance_alert_route"
ARMS = ("no_alert", "alert", "alert_preemption")
DEMANDS = ("generated", "calibrated", "dhaka_density")   # dhaka_density: RQ2b, the corridor net with DhaTraX's recorded counts (core.simulation.ambulance.corridor)      # the city's ordinary generated demand (uncalibrated), or the one fitted to recorded counts


class Refused(Exception):
    """A run that cannot be made honestly: the city has no trip or no network, or a technology has an unsourced parameter."""


@lru_cache(maxsize=2)
def settings(path: Path = CONFIG) -> dict:
    return yaml.safe_load(Path(path).read_text())


@lru_cache(maxsize=4)
def _net_of(path: str):
    """A SUMO network read once (sumolib), for routes chosen by edge id (the live demo's --from/--to)."""
    import sumolib
    return sumolib.net.readNet(path)


def route_on_net(net, from_edge: str, to_edge: str) -> list[str]:
    """The shortest path an emergency vehicle may drive between two edge ids, as edge ids; Refused when an id is unknown or no path exists."""
    try:
        a, b = net.getEdge(from_edge), net.getEdge(to_edge)
    except KeyError as exc:
        raise Refused(f"no such edge on this network: {exc}") from None
    path, _cost = net.getShortestPath(a, b, vClass="emergency")
    if not path or (a is not b and len(path) < 2):
        raise Refused(f"no route for an emergency vehicle from {from_edge} to {to_edge}")
    return [e.getID() for e in path]


def random_route(city_id: str, demand: str, seed: int, min_m: float = 1500.0, tries: int = 200) -> tuple[str, str]:
    """Two edge ids drawn by `seed` on the network the demand runs on (the corridor for dhaka_density, else the city's), kept only
    when an emergency vehicle has a route of at least `min_m` between them. The live demo's "random" start and end."""
    base = scenario(city_id, demand)
    net = _net_of(str(base["net"]))
    rng = random.Random(f"route|{seed}")
    edges = [e for e in net.getEdges() if e.allows("emergency") and e.getFunction() == "" and e.getLength() >= 20]
    for _ in range(tries):
        a, b = rng.choice(edges), rng.choice(edges)
        if a is b:
            continue
        try:
            path = route_on_net(net, a.getID(), b.getID())
        except Refused:
            continue
        if sum(net.getEdge(i).getLength() for i in path) >= min_m:
            return a.getID(), b.getID()
    raise Refused(f"no random route of at least {min_m:.0f} m found in {tries} draws (seed {seed})")


@lru_cache(maxsize=8)
def scenario(city_id: str, demand: str = "calibrated", route: tuple[str, str] | None = None) -> dict:
    """The ambulance's route on the city's own network, with the signalised junctions on it, and the demand it meets.
    `route=(from_edge, to_edge)` (live demo, 2026-10-12) replaces the city config's trip by a route between two edge ids on the same
    network; the default is the thesis trip, unchanged."""
    if demand not in DEMANDS:
        raise Refused(f"unknown demand {demand!r}; one of {DEMANDS}")
    from core.simulation.routing import city_router
    try:
        cfg = city_config.load(city_id)
    except KeyError:
        raise Refused(f"no data for this city: {city_id!r} has no config") from None
    if cfg.emergency is None:
        raise Refused("no data for this city: its config defines no ambulance trip")
    got = city_router.network(city_id)
    if got is None:
        raise Refused("no data for this city: no road network has been built for it")
    net, man = got
    e = cfg.emergency
    try:
        r = city_router.route(city_id, (e.origin.lat, e.origin.lon), (e.destination.lat, e.destination.lon))
    except city_router.Refused as exc:
        raise Refused(str(exc)) from None
    from core.simulation.twin.scenario_builder import scenario_dir
    generated, fitted = scenario_dir(city_id) / f"{city_id}.rou.xml", man.get("calibrated_to")
    if demand == "calibrated" and not fitted:
        raise Refused("no data for this city: its demand has not been fitted to any counts (python -m core.simulation.twin.calibration)")
    if demand == "generated" and not generated.exists():
        raise Refused("no data for this city: its generated demand file is missing (python -m core.simulation.twin.city_pipeline)")
    routes = REPO / man["files"]["routes"] if demand == "calibrated" else generated
    label = {"label": man["demand_reality"], "calibrated_to": fitted} if demand == "calibrated" else {"label": "SYNTHETIC_WHAT_IF", "calibrated_to": None}
    net_file = REPO / man["files"]["net"]
    if demand == "dhaka_density":
        from core.simulation.ambulance import corridor
        if not (corridor.NET.exists() and corridor.ROUTES.exists()):
            raise Refused("no data: the corridor has not been built (python -m core.simulation.ambulance.corridor build)")
        net_file, routes = corridor.NET, corridor.ROUTES
        label = {"label": "SYNTHETIC_RECORDED_COUNTS_CORRIDOR", "calibrated_to": "DhaTraX counts at INT and BM, 07:00-08:00, on a 300 m corridor around the route (core.simulation.ambulance.corridor)"}
    if route:                                                  # live demo: a route between two edge ids on the network this demand runs on
        net = _net_of(str(net_file))
        edges = route_on_net(net, route[0], route[1])
        length_m = round(sum(net.getEdge(i).getLength() for i in edges), 1)
        trip = {"origin": {"edge": route[0]}, "destination": {"edge": route[1]}, "source": "edge ids given to the live demo, not the city config's trip"}
    else:
        edges, length_m = [s["id"] for s in r["sections"]], r["length_m"]
        trip = {"origin": e.origin.model_dump(), "destination": e.destination.model_dump()}
    signals = []
    for i, eid in enumerate(edges[:-1]):
        tls = net.getEdge(eid).getTLS()
        if tls is not None:
            x, y = net.getEdge(eid).getToNode().getCoord()[:2]
            signals.append({"tls": tls.getID(), "in_edge": eid, "route_index": i, "x": x, "y": y})
    return {"city_id": city_id, "demand_id": demand, "net": net_file, "routes": routes, "edges": edges,
            "lengths": [net.getEdge(i).getLength() for i in edges], "length_m": length_m, "signals": signals,
            "demand": label, "route_given": list(route) if route else None,
            "trip": trip}


class AmbulanceRun:
    """The alert logic of one run, stepped once per simulated second by whoever owns the simulation."""

    def __init__(self, conn, scen: dict, arm: str, technology: str | None, share: float, seed: int, cfg: dict | None = None):
        if arm not in ARMS:
            raise Refused(f"unknown arm {arm!r}")
        self.conn, self.scen, self.arm, self.tech, self.share, self.cfg = conn, scen, arm, technology, share, cfg or settings()
        if arm != "no_alert":
            model.parameters(technology)                       # raises model.Refused, naming the unsourced parameter
        self.rng = random.Random(f"{seed}|{technology}|{share}|{arm}")
        mk = self.cfg["alert"].get("makeway") or {"version": 1}           # configs/ambulance.yaml; version 1 = the RQ2 rule with the circular-wait artefact
        self.makeway_version = mk.get("version", 1)
        self.makeway_m = self.cfg["alert"].get("makeway_m", mk.get("distance_m"))           # an explicit override (RQ2b variants) wins
        self.makeway = MakeWay(conn, keep_strategic=self.cfg["alert"].get("keep_strategic", mk.get("keep_strategic", False)))
        self.preemption = SumoPreemption(conn, SAFETY_PROFILES[self.cfg["safety_profile"]]) if arm == "alert_preemption" else None
        self.interval = model.parameters(technology)["interval_s"] if arm != "no_alert" else 1.0
        self.msgs = {"sent": 0, "delivered": 0, "lost": 0, "out_of_range": 0}
        self.alerted: set[str] = set()                         # every vehicle that was ever alerted
        self.informed: dict[str, float] = {}                   # junction -> when the alert reached it
        self.departed = self.arrived = None
        self.state = "waiting"
        self.vehicle_id = AMBULANCE

    def add(self) -> None:
        self.conn.route.add(ROUTE, self.scen["edges"])
        self.conn.vehicle.add(AMBULANCE, ROUTE, typeID=VTYPE, departLane="best", departSpeed="max")

    def step(self, t: float) -> None:
        if self.state == "waiting" and t >= self.cfg["ambulance"]["depart_s"]:
            self.add()
            self.state = "added"
        if self.state in ("waiting", "arrived"):
            if self.preemption:
                self.preemption.step(t)
            return
        if AMBULANCE in self.conn.simulation.getArrivedIDList():
            self.state, self.arrived = "arrived", t
            self._release_all()
            return
        if AMBULANCE not in self.conn.vehicle.getIDList():
            return                                             # not inserted yet (the origin lane is full)
        if self.departed is None:
            self.departed, self.state = t, "driving"
        if self.arm != "no_alert":
            self._alert(t)
        if self.preemption:
            self.preemption.step(t)

    # ------------------------------------------------------------------ the alert
    def _ahead(self) -> tuple[list[tuple[str, float]], int, float]:
        """[(edge, metres from the ambulance to the edge's start)] within the addressed stretch, the route index, and the position on the current edge."""
        v = self.conn.vehicle
        i = v.getRouteIndex(AMBULANCE)
        on_edge = not v.getRoadID(AMBULANCE).startswith(":")
        pos = v.getLanePosition(AMBULANCE) if on_edge else self.scen["lengths"][i]
        out, dist = [(self.scen["edges"][i], -pos)], self.scen["lengths"][i] - pos
        for j in range(i + 1, len(self.scen["edges"])):
            if dist > self.cfg["alert"]["ahead_m"]:
                break
            out.append((self.scen["edges"][j], dist))
            dist += self.scen["lengths"][j]
        return out, i, pos

    def _alert(self, t: float) -> None:
        v = self.conn.vehicle
        ahead, index, pos = self._ahead()
        ax, ay = v.getPosition(AMBULANCE)
        me = Station(AMBULANCE, ax, ay)
        in_front: set[str] = set()
        near, skip_jn = self.makeway_m, self.cfg["alert"].get("no_makeway_in_junctions", False)   # None = every alerted vehicle within ahead_m (v1)
        for k, (edge, start) in enumerate(ahead):
            for vid in self.conn.edge.getLastStepVehicleIDs(edge):
                if vid == AMBULANCE or (k == 0 and v.getLanePosition(vid) <= pos):
                    continue                                   # behind the ambulance on its own road
                if near is not None and start + v.getLanePosition(vid) > near:
                    continue                                   # variant: only vehicles this close ahead move aside (and are released beyond it)
                in_front.add(vid)
                if vid in self.makeway.before or not pr.equipped(vid, self.share):
                    continue
                x, y = v.getPosition(vid)
                if skip_jn and v.getRoadID(vid).startswith(":"):
                    continue
                if self._send(me, Station(vid, x, y), t) and self.makeway.alert(vid):
                    self.alerted.add(vid)
        for vid in list(self.makeway.before):
            if skip_jn and vid in v.getIDList() and v.getRoadID(vid).startswith(":"):
                self.makeway.release(vid, True)               # variant: nobody keeps the make-way settings inside a junction
            elif vid in in_front:
                self.makeway.keep_side(vid)
            else:                                              # the ambulance has passed it, or it left the route or the simulation
                self.makeway.release(vid, vid in v.getIDList())
        if self.preemption:
            reach = {edge: start for edge, start in ahead}
            for s in self.scen["signals"]:
                if s["route_index"] < index and s["tls"] in self.informed:
                    self.preemption.passed(s["tls"])
                    self.informed.pop(s["tls"])
                elif s["route_index"] >= index and s["in_edge"] in reach and s["tls"] not in self.informed:
                    if self._send(me, Station(s["tls"], s["x"], s["y"]), t):
                        lane = f"{s['in_edge']}_0"
                        self.preemption.request(s["tls"], lane, t)
                        self.informed[s["tls"]] = t

    def _send(self, sender: Station, receiver: Station, t: float) -> bool:
        d = model.deliver(sender, receiver, t, self.tech, self.rng)
        self.msgs["sent"] += 1
        self.msgs["delivered" if d.delivered else "out_of_range" if d.reason == model.OUT_OF_RANGE else "lost"] += 1
        return d.delivered                                     # the delay is far below one simulation step; it is applied within this step

    def _release_all(self) -> None:
        present = set(self.conn.vehicle.getIDList())
        for vid in list(self.makeway.before):
            self.makeway.release(vid, vid in present)
        if self.preemption:
            for tls in list(self.informed):
                self.preemption.passed(tls)
            self.informed.clear()

    def public(self) -> dict:
        """What a page may show of a running ambulance run. All of it is simulated."""
        return {"label": "SIMULATED", "arm": self.arm, "technology": self.tech, "equipped_share": self.share, "state": self.state,
                "depart_s": self.cfg["ambulance"]["depart_s"], "departed_s": self.departed, "arrived_s": self.arrived, "messages": dict(self.msgs),
                "vehicles_alerted": len(self.alerted), "making_way_now": len(self.makeway.before),
                "junctions_preempted_now": self.preemption.preempted() if self.preemption else [], "demand": self.scen["demand"], "vehicle_id": AMBULANCE}

    def summary(self) -> dict:
        return {"makeway": {"version": self.makeway_version, "distance_m": self.makeway_m, "keep_strategic": self.makeway.keep_strategic}, "state": self.state, "departed_s": self.departed, "arrived_s": self.arrived, "messages": dict(self.msgs), "vehicles_alerted": len(self.alerted),
                "junctions_preempted": sorted({r.junction_id for r in self.preemption.requests}) if self.preemption else []}


def write_vtype(path: Path, cfg: dict | None = None) -> Path:
    """The ambulance's vehicle type, written the way SUMO's documentation gives it (Simulation/Emergency)."""
    a = (cfg or settings())["ambulance"]["vtype"]
    path.write_text(f'<routes>\n  <vType id="{VTYPE}" vClass="{a["vClass"]}" speedFactor="{a["speedFactor"]}" guiShape="emergency">\n'
                    f'    <param key="has.bluelight.device" value="{"true" if a["bluelight"] else "false"}"/>\n  </vType>\n</routes>\n')
    return path


LIVE_DEPART_S = 60           # in the browser the ambulance leaves after a minute, not after the experiments' 15: a viewing choice, not a result


def live_request(city_id: str, arm: str, technology: str | None, share: float, demand: str = "generated", depart_s: int = LIVE_DEPART_S) -> dict:
    """Check a request for a live ambulance run and return the parameters the live twin needs. Raises Refused."""
    if arm not in ARMS:
        raise Refused(f"unknown arm {arm!r}; one of {ARMS}")
    if not 0.0 <= share <= 1.0:
        raise Refused("equipped_share must be between 0 and 1")
    scen = scenario(city_id, demand)
    if arm != "no_alert":
        try:
            model.parameters(technology)
        except model.Refused as exc:
            raise Refused(str(exc)) from None
    return {"network": city_id, "arm": "baseline", "levels": "", "scale": 1.0, "routes_file": str(scen["routes"]),
            "emergency": {"arm": arm, "technology": technology if arm != "no_alert" else None, "equipped_share": share if arm != "no_alert" else 0.0,
                          "demand": demand, "depart_s": int(depart_s)}}


def live_run(conn, city_id: str, req: dict, seed: int) -> AmbulanceRun:
    cfg = json.loads(json.dumps(settings()))
    cfg["ambulance"]["depart_s"] = req["depart_s"]
    return AmbulanceRun(conn, scenario(city_id, req["demand"]), req["arm"], req["technology"], req["equipped_share"], seed, cfg)


def run_name(arm: str, technology: str | None, share: float, seed: int) -> str:
    return f"{arm}_s{seed}" if arm == "no_alert" else f"{arm}_{technology}_p{int(round(share * 100)):03d}_s{seed}"


def trip_metrics(out: Path, horizon: float) -> dict:
    """The ambulance's own trip, and the cost to everyone else (the ambulance excluded)."""
    amb, loss, wait, dur, unfinished = None, [], [], [], 0
    for ti in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
        if ti.get("id") == AMBULANCE:
            amb = ti
            continue
        if float(ti.get("arrival", -1)) < 0:
            unfinished += 1
            dur.append(horizon - float(ti.get("depart")))
            continue
        dur.append(float(ti.get("duration")))
        loss.append(float(ti.get("timeLoss")))
        wait.append(float(ti.get("waitingTime")))
    st = ET.parse(out / "statistic.xml").getroot()
    arrived = amb is not None and float(amb.get("arrival", -1)) >= 0
    return {"ambulance": {"arrived": arrived, "travel_time_s": float(amb.get("duration")) if arrived else None, "time_loss_s": float(amb.get("timeLoss")) if arrived else None,
                          "waiting_s": float(amb.get("waitingTime")) if arrived else None, "depart_s": float(amb.get("depart")) if amb is not None else None},
            "others": {"vehicles": len(dur), "arrived": len(loss), "unfinished_at_horizon": unfinished, "total_vehicle_hours": round(sum(dur) / 3600, 3),
                       "mean_time_loss_s": round(statistics.fmean(loss), 2) if loss else None, "mean_waiting_s": round(statistics.fmean(wait), 2) if wait else None},
            "teleports": int(st.find("teleports").get("total"))}


def run_one(city_id: str, arm: str, technology: str | None, share: float, seed: int, demand: str = "calibrated", root: Path = RESULTS,
            scale: float = 1.0, observe: bool = False, alert_overrides: dict | None = None, tag: str = "", hook=None,
            sumo_binary: str = "sumo", gui_options: tuple = (), route: tuple[str, str] | None = None) -> dict:
    """One run. `scale` multiplies the demand (SUMO --scale; RQ2's density ladder); `observe` adds RQ2's measures (emergency/measures.py).
    `alert_overrides` (RQ2b's make-way variants), `tag` (appended to the run folder) and `hook(conn, t, run)` (called every step,
    for inspection) default to nothing. `sumo_binary="sumo-gui"` with `gui_options` (display only, e.g. --start) is the supervisor
    demo (scripts/demo/ambulance.py). The defaults are the original experiment, unchanged."""
    import traci
    cfg, scen = settings(), scenario(city_id, demand, tuple(route) if route else None)
    if route and not tag:                                      # a chosen route never lands in a saved study folder
        tag = "r" + hashlib.sha1("|".join(route).encode()).hexdigest()[:8]
    if alert_overrides:
        cfg = json.loads(json.dumps(cfg))
        cfg["alert"].update(alert_overrides)
    out = root / city_id / demand / (run_name(arm, technology, share, seed) + (f"_x{scale:g}" if scale != 1.0 else "") + (f"_{tag}" if tag else ""))
    out.mkdir(parents=True, exist_ok=True)
    extra = ["--lateral-resolution", str(cfg["sumo"]["lateral_resolution"]), *gui_options]
    vtype = write_vtype(out / "ambulance_type.rou.xml", cfg)
    ns = SimpleNamespace(sumo_binary=sumo_binary, net=scen["net"], routes=f"{scen['routes']},{vtype}", seed=seed, scale=scale, horizon=cfg["horizon_s"], edgedata_period=300,
                         time_to_teleport=cfg["sumo"]["time_to_teleport_s"], sumo_extra=extra)
    label, t0 = f"emergency-{out.name}-{time.time_ns()}", time.time()
    traci.start(pr.base_cmd(ns, out), port=pr.free_port(), label=label)
    conn = traci.getConnection(label)
    run, t, crashed = AmbulanceRun(conn, scen, arm, technology, share, seed, cfg), 0.0, None
    obs = None
    if observe:
        from core.simulation.ambulance.measures import RouteObserver
        obs = RouteObserver(conn, scen, AMBULANCE)
    try:
        while t < cfg["horizon_s"]:
            conn.simulationStep()
            t = conn.simulation.getTime()
            run.step(t)
            if obs:
                obs.step(t, run.state == "driving", run.alerted)
            if hook:
                hook(conn, t, run)
    except traci.exceptions.FatalTraCIError:                   # SUMO itself exited (a crash inside the simulator): the run has no result
        crashed = t
    finally:
        try:
            conn.close()
        except Exception:                                      # noqa: BLE001 - nothing left to close after a crash
            pass
    head = {"city_id": city_id, "demand_id": demand, "arm": arm, "technology": technology, "equipped_share": share, "seed": seed, "wall_s": round(time.time() - t0, 1),
            "run_utc": datetime.now(timezone.utc).isoformat(), "sumo_extra": extra, "demand": scen["demand"], "route_m": scen["length_m"],
            "signals_on_route": len(scen["signals"]), "scale": scale, **({"route_given": list(route)} if route else {}),
            **({"alert_overrides": alert_overrides} if alert_overrides else {}), **run.summary(), **({"why": obs.summary()} if obs else {})}
    if crashed is not None:
        metrics = {**head, "state": "sumo_crashed", "crashed_after_s": crashed, "ambulance": {"arrived": False, "travel_time_s": None}, "others": None, "teleports": None}
        (out / "metrics.json").write_text(json.dumps(metrics, indent=1))
        return metrics
    metrics = {**head, **trip_metrics(out, cfg["horizon_s"])}
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1))
    for big in ("edgedata.xml", "summary.xml"):                # not read by anything here; tripinfo and statistic are kept
        (out / big).unlink(missing_ok=True)
    return metrics


def configurations(cfg: dict | None = None) -> tuple[list[tuple], dict]:
    """(arm, technology, share) for every configuration that can run, and the technologies refused with the reason."""
    cfg = cfg or settings()
    refused = {t: missing for t in cfg["technologies"] if (missing := model.unsourced(t))}
    techs = [t for t in cfg["technologies"] if t not in refused]
    out = [("no_alert", None, 0.0)]
    out += [("alert", t, s) for t in techs for s in cfg["equipped_shares"] if s > 0]          # share 0 without preemption IS the baseline (a test checks it)
    out += [("alert_preemption", t, s) for t in techs for s in cfg["equipped_shares"]]
    return out, refused


PAIRS_WANTED = 5             # completed (configuration, baseline) pairs per configuration: the "several seeds" of every result
MAX_SEEDS = 60               # seeds tried before giving up on a configuration


def sweep(city_id: str, demand: str, root: Path = RESULTS, wanted: int = PAIRS_WANTED, max_seeds: int = MAX_SEEDS) -> dict:
    """Run until every configuration has `wanted` seeds on which both it and the no-alert baseline finished.

    SUMO's bluelight device makes SUMO 1.27.1 exit on some seeds (evidence/emergency/<city>/sumo_bluelight_crash.json).
    A crashed run has no result: it is kept on disk as `sumo_crashed`, counted, and the next seed is tried. A seed whose
    baseline crashed pairs with nothing and is skipped. A finished run found on disk is not repeated."""
    cfg = settings()
    confs, refused = configurations(cfg)
    pairs = {c: 0 for c in confs if c[0] != "no_alert"}
    def one(arm, tech, share, seed):
        f = root / city_id / demand / run_name(arm, tech, share, seed) / "metrics.json"
        m = json.loads(f.read_text()) if f.exists() else run_one(city_id, arm, tech, share, seed, demand, root)
        print(f"{demand} {run_name(arm, tech, share, seed)}: {m['state']}, ambulance {m['ambulance']['travel_time_s']} s, alerted {m['vehicles_alerted']}, wall {m['wall_s']} s", flush=True)
        return m["state"] == "arrived"
    tried = 0
    for seed in range(cfg["seeds"][0], cfg["seeds"][0] + max_seeds):
        need = [c for c, n in pairs.items() if n < wanted]
        if not need:
            break
        tried += 1
        if not one("no_alert", None, 0.0, seed):
            continue
        for c in need:
            pairs[c] += one(*c, seed)
    return {"seeds_tried": tried, "pairs": {run_name(*c, 0)[:-3]: n for c, n in pairs.items()}, "refused": refused}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--one", action="store_true", help="one run of each arm (first technology, every vehicle equipped, first seed)")
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--demand", choices=DEMANDS, default="calibrated")
    a = ap.parse_args()
    cfg = settings()
    confs, refused = configurations(cfg)
    for t, missing in refused.items():
        print(f"REFUSED {t}: no sourced value for {', '.join(missing)}")
    if a.one:
        tech = next(c[1] for c in confs if c[1])
        for arm in ARMS:
            m = run_one(a.city, arm, None if arm == "no_alert" else tech, 0.0 if arm == "no_alert" else 1.0, cfg["seeds"][0], a.demand)
            print(json.dumps({k: m[k] for k in ("arm", "technology", "equipped_share", "wall_s", "state", "messages", "vehicles_alerted", "junctions_preempted", "ambulance", "others", "teleports")}))
    if a.sweep:
        print(json.dumps(sweep(a.city, a.demand)))
        from core.simulation.ambulance import results
        for row in results.build(a.city, a.demand)["rows"]:
            print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
