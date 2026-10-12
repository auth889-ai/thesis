"""One live twin: a SUMO simulation of the city's live_twin network that keeps running, controlled through TraCI, labelled SIMULATION.

- Seed: taken from the clock at each start and shown.
- Demand: the configured route file repeated hour after hour (demand.py) at the configured base scale; the viewer's slider multiplies it
  (TraCI simulation.setScale).
- Warm-up: WARMUP_MIN simulated minutes at full speed so the forecasters have history; then paced at `speed` simulated seconds per
  real second.
- Every simulated minute the detectors (detectors.py) give each road's speed to the three forecasters (core/ml/forecasting/live).
- Clicks: a crash stops the car nearest the point on that road (as scripts/live/run_sos_v2v.py stops its car: speed 0, no lane
  change); an ambulance starts on that road and drives to the hospital in the city config (or a second click), alerting cars through
  the thesis's V2X delivery model with make-way rule v2 and turning the route's signals green: the RQ2 AmbulanceRun, unchanged
  except its route id (one ambulance after another).
- Vehicles are streamed as sumo-web3d does: TraCI subscriptions, then per step only the creations, changed fields and removals
  (deltas.diff_dicts, copied from sumo-web3d).
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

from core.common.paths import REPO
from core.simulation.live_twin import demand, detectors
from core.simulation.live_twin.deltas import diff_dicts

WARMUP_MIN = 15
HOURS = 12                       # copies of the demand hour: a local twin runs up to 12 simulated hours
MAX_FRAMES = 600                 # step deltas kept for viewers that fall behind; older viewers get a full snapshot
NORMAL, MAKING_WAY, CRASHED, AMBULANCE_STATE, STEERED = 0, 1, 2, 3, 4
STEER_WITH = ("online", "chronos", "no_change", "current")    # "current": SUMO's own idea (rerouting on the edges' current travel times), no forecast
CRASH_PICK_M = 100.0
TECHS = ("its_g5", "c_v2x", "cellular_4g")


class Refused(Exception):
    """A request the twin cannot carry out; `key` and `params` let the page say it in the viewer's language."""
    def __init__(self, text: str, key: str = "", **params):
        super().__init__(text)
        self.key, self.params = key, params


class Session:
    def __init__(self, city_id: str, visitor: str, speed: float = 8.0, technology: str = "its_g5", hosted_wall_s: float | None = None,
                 sync_forecasts: bool = False, steer: dict | None = None, record_trips: bool = False,
                 chronos: bool = True):
        from core.common.data import city_config
        cfg = city_config.load(city_id)
        if cfg.live_twin is None:
            raise Refused("no data for this city: its config has no live twin", "noData")
        if technology not in TECHS:
            raise Refused(f"technology must be one of {TECHS}", "techUnknown")
        self.id = f"twin-{uuid.uuid4().hex[:10]}"
        self.city_id, self.visitor, self.cfg, self.lt = city_id, visitor, cfg, cfg.live_twin
        self.seed = int(time.time()) % 2**31
        self.speed, self.technology, self.factor = float(speed), technology, 1.0
        self.hosted_wall_s = hosted_wall_s
        self.sync_forecasts = sync_forecasts           # scripts and tests: wait for each Chronos call (the page never waits)
        # Steering (off unless asked: the page's toggle or a script). Following SUMO's device.rerouting: every simulated minute the
        # chosen forecaster's 15-minute prediction sets each detector road's travel time (traci.edge.adaptTraveltime) and an informed
        # share of vehicles reroute on those times (traci.vehicle.rerouteTraveltime).
        self.steer = self._check_steer(steer) if steer else None
        self.steered: set[str] = set()
        self.steer_stats = {"minutes": 0, "edges_set": 0, "reroutes": 0, "route_changed": 0}
        self.trips: dict | None = {"depart": {}, "done": []} if record_trips else None   # scripts only: (depart, arrival) per vehicle
        self.use_chronos = chronos                     # scripts: an arm that does not steer with Chronos may skip it (the page always runs it)
        self.status, self.message, self.message_key, self.message_params = "starting", "", "", {}
        self.t = 0.0
        self.started = time.time()
        self.last_seen = time.time()
        self.commands: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.vehicles: dict[str, dict] = {}
        self.frames: list[tuple[int, dict]] = []       # (index, step message)
        self.index = 0
        self.forecast: dict = {}
        self.events: list[dict] = []
        self.crashed: dict[str, dict] = {}
        self.amb = None
        self.amb_log: list[dict] = []
        self._sent_minute, self._sent_events = None, 0     # what the last step message carried (light messages omit unchanged parts)
        self.sent_live = False                         # the first live frame is a full snapshot (the warm-up sends no vehicle deltas)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name=self.id)
        self._roads()

    # ------------------------------------------------------------------ public
    def start(self) -> None:
        self.thread.start()

    def command(self, cmd: dict) -> None:
        self.last_seen = time.time()
        self.commands.put(cmd)

    def stop(self) -> None:
        self.stop_event.set()

    def hello(self) -> dict:
        return {"type": "hello", "label": "SIMULATION", "id": self.id, "city_id": self.city_id, "seed": self.seed, "status": self.status,
                "message": self.message, "demand": self.lt.demand_label, "base_scale": self.lt.demand_scale, "factor": self.factor,
                "speed": self.speed, "technology": self.technology, "warmup_min": WARMUP_MIN, "roads": self.road_geo,
                "hospital": getattr(self, "hospital", None), "bluelight": False}

    def since(self, index: int | None) -> tuple[int, list[dict]]:
        """Messages for a viewer that has seen up to `index` (None: a new viewer gets the full current state)."""
        self.last_seen = time.time()
        with self.lock:
            if index is not None and not self.frames:
                return index, []
            if index is None or index < self.frames[0][0] - 1:
                full = {"type": "full", "t": self.t, "vehicles": dict(self.vehicles), **self._status()}
                return self.index, [full]
            return self.index, [m for i, m in self.frames if i > index]

    def _status(self, light: bool = False) -> dict:
        """The twin's state. `light` (step messages): the forecast and the events only when they changed since the last message."""
        out = self._status_full()
        if light:
            if self.forecast.get("minute") == self._sent_minute:
                out.pop("forecast")
            if len(self.events) == self._sent_events:
                out.pop("events")
        self._sent_minute, self._sent_events = self.forecast.get("minute"), len(self.events)
        return out

    def _status_full(self) -> dict:
        return {"status": self.status, "message": self.message, "message_key": self.message_key, "message_params": self.message_params, "t": self.t, "seed": self.seed, "factor": self.factor,
                "technology": self.technology, "speed": self.speed, "counts": self._counts(), "forecast": self.forecast,
                "crashes": [{"id": k, **v} for k, v in self.crashed.items()], "events": self.events[-20:],
                "steer": {**self.steer, **self.steer_stats} if self.steer else None}

    def _counts(self) -> dict:
        a = self.amb
        if a is None:
            return {"ambulance": None, "last_ambulances": self.amb_log[-5:]}
        p = a.run.public()
        from core.networking.v2x import model
        rng = model.parameters(a.run.tech)["range_m"]
        return {"ambulance": {"state": p["state"], "technology": a.run.tech, "range_m": rng if math.isfinite(rng) else None, "messages": p["messages"], "cars_alerted": p["vehicles_alerted"],
                              "making_way_now": p["making_way_now"], "signals_green_now": len(p["junctions_preempted_now"]),
                              "time_so_far_s": round((a.run.arrived or self.t) - a.run.departed, 1) if a.run.departed is not None else None,
                              "from": a.origin, "to": a.dest}, "last_ambulances": self.amb_log[-5:]}

    # ------------------------------------------------------------------ the simulation
    def _roads(self) -> None:
        from core.simulation.live_jobs.runner import net as load_net
        self.net_path = REPO / self.lt.net
        if not self.net_path.exists():
            raise Refused("no data for this city: its live twin network has not been built", "noData")
        self.net = load_net(str(self.net_path))
        self.road_edges = detectors.roads(self.net, self.lt.detector_road_types, self.lt.detector_min_edge_m)
        self.limits = {e.getID(): e.getSpeed() * 3.6 for e in self.road_edges}
        self.road_geo = [{"id": e.getID(), "name": e.getName(), "limit_kmh": round(e.getSpeed() * 3.6),
                          "path": [[round(v, 6) for v in self.net.convertXY2LonLat(x, y)] for x, y in e.getShape()]} for e in self.road_edges]

    def _prepare(self) -> list[str]:
        from core.simulation.ambulance import service
        self.dir = Path(tempfile.mkdtemp(prefix=f"{self.id}-"))
        self.loops, self.loops_sha = detectors.write_additional(self.dir / "loops.add.xml", self.road_edges)
        routes = demand.repeated(REPO / self.lt.routes, self.dir / "twin.rou.xml", HOURS)
        self.amb_cfg = json.loads(json.dumps(service.settings()))      # a copy: the thesis runs' settings stay as they are
        # The live twin only (owner, 2026-10-10): the ambulance drives WITHOUT SUMO's bluelight device, whose recorded segmentation fault on
        # this network (evidence/emergency/dhaka/sumo_bluelight_crash.json) stopped live twins. It still gets green signals (SumoPreemption)
        # and cars still make way (rule v2); it no longer runs red lights by itself, and cars within 25 m no longer react to the device.
        self.amb_cfg["ambulance"]["vtype"]["bluelight"] = False
        vtype = service.write_vtype(self.dir / "ambulance_type.rou.xml", self.amb_cfg)
        e = self.cfg.emergency
        self.hospital = {"lon": e.destination.lon, "lat": e.destination.lat} if e else None
        s = self.amb_cfg["sumo"]
        return ["sumo", "--net-file", str(self.net_path), "--route-files", f"{routes},{vtype}", "--additional-files", str(self.dir / "loops.add.xml"),
                "--seed", str(self.seed), "--scale", str(self.lt.demand_scale), "--lateral-resolution", str(s["lateral_resolution"]),
                "--time-to-teleport", str(s["time_to_teleport_s"]), "--no-step-log", "--no-warnings", "--ignore-route-errors"]

    def _run(self) -> None:
        import traci
        from core.ml.forecasting.live.online import Forecasters
        from core.simulation.twin import runtime as pr
        conn = None
        try:
            cmd = self._prepare()
            self.fc = Forecasters(self.limits, use_chronos=self.use_chronos, sync=self.sync_forecasts)
            traci.start(cmd, port=pr.free_port(), label=self.id)
            conn = self.conn = traci.getConnection(self.id)
            self.status = "warming"
            self.say(f"warming up: {WARMUP_MIN} simulated minutes at full speed", "warming", min=WARMUP_MIN)
            self._publish_status()
            while not self.stop_event.is_set():
                live = self.t >= WARMUP_MIN * 60
                if live and self.status == "warming":
                    self.status = "running"
                    self.say("")
                tick = time.time()
                self._commands()
                conn.simulationStep()
                self.t = conn.simulation.getTime()
                for vid in conn.simulation.getDepartedIDList():
                    conn.vehicle.subscribe(vid, (traci.constants.VAR_POSITION, traci.constants.VAR_ANGLE, traci.constants.VAR_SPEED))
                    if self.trips is not None:
                        self.trips["depart"][vid] = self.t
                if self.trips is not None:
                    for vid in conn.simulation.getArrivedIDList():
                        d = self.trips["depart"].pop(vid, None)
                        if d is not None:
                            self.trips["done"].append((d, self.t))
                if self.amb:
                    self._ambulance_step()
                if int(self.t) % 60 == 0:
                    self._minute()
                self._publish(live)
                if self.hosted_wall_s and time.time() - self.started > self.hosted_wall_s:
                    self.say("stopped: the hosted time limit", "hostedLimit", min=round(self.hosted_wall_s / 60))
                    break
                if conn.simulation.getMinExpectedNumber() == 0:
                    self.say("the demand has ended", "demandEnded")
                    break
                if live:
                    time.sleep(max(0.0, 1.0 / self.speed - (time.time() - tick)))
            self.status = "stopped"
        except traci.exceptions.FatalTraCIError:
            self.status, self.message = "failed", self._sumo_died(conn)
        except Exception as exc:                                     # noqa: BLE001 - the page shows the reason
            self.status = "failed"
            self.say(f"{type(exc).__name__}: {exc}", "error", text=f"{type(exc).__name__}: {exc}")
            traceback.print_exc()
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:                                        # noqa: BLE001
                pass
            self._publish_status()
            shutil.rmtree(getattr(self, "dir", ""), ignore_errors=True)

    def _sumo_died(self, conn) -> str:
        proc = getattr(conn, "_process", None)
        rc = None
        if proc is not None:
            try:
                rc = proc.wait(timeout=3)
            except Exception:                                        # noqa: BLE001
                pass
        why = f"SUMO stopped at {self.t:.0f} s (exit code {rc})."
        bluelight = self.amb is not None and rc not in (0, None) and self.amb_cfg["ambulance"]["vtype"]["bluelight"]
        if bluelight:
            why += (" A segmentation fault of SUMO 1.27.1's bluelight device on this network is known and recorded "
                    "(evidence/emergency/dhaka/sumo_bluelight_crash.json); the thesis settings keep the device. Start a new twin.")
        self.event("error", why, "sumoDied", t=round(self.t), rc=rc, bluelight=bool(bluelight))
        self.message_key, self.message_params = "sumoDied", {"t": round(self.t), "rc": rc, "bluelight": bool(bluelight)}
        return why

    def _minute(self) -> None:
        speeds = detectors.read_minute(self.conn, self.loops)
        v = self.fc.observe(speeds, self.lt.demand_scale * self.factor)
        observed = {r: s for r, s in speeds.items() if s is not None}
        self.forecast = {**v, "observed": observed, "predicted": {n: self.fc.predictions(n) for n in ("online", "chronos", "no_change")},
                         "loops": sum(len(x) for x in self.loops.values()), "roads": len(self.loops), "loops_sha256": self.loops_sha}
        if self.steer and self.t >= WARMUP_MIN * 60:
            self._steer()

    # ------------------------------------------------------------------ steering (closed loop; off by default)
    @staticmethod
    def _check_steer(st: dict) -> dict:
        w, share = st.get("forecaster", "online"), float(st.get("share", 0.3))
        if w not in STEER_WITH:
            raise Refused(f"forecaster must be one of {STEER_WITH}", "steerUnknown")
        if not 0.0 < share <= 1.0:
            raise Refused("share must be above 0 and at most 1", "steerShare")
        return {"forecaster": w, "share": share}

    def informed(self, vid: str) -> bool:
        """A fixed share of vehicles get the forecast (as SUMO's device.rerouting.probability): a seeded hash, so every arm of a
        comparison informs the same vehicles."""
        h = int(hashlib.sha256(f"{self.seed}|{vid}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        return h < self.steer["share"]

    def _steer(self) -> None:
        c, w = self.conn, self.steer["forecaster"]
        current = w == "current"
        if not current:
            pred = self.fc.predictions(w)
            for road, kmh in pred.items():
                c.edge.adaptTraveltime(road, self.net.getEdge(road).getLength() / max(kmh / 3.6, 0.5))   # predicted travel time, s
            self.steer_stats["edges_set"] = len(pred)
            if not pred:
                return                                   # nothing predicted yet (Chronos's first minute): no rerouting on stale weights
        skip = set(self.crashed) | ({self.amb.run.vehicle_id} if self.amb else set())
        for vid in c.vehicle.getIDList():
            if vid in skip or not self.informed(vid):
                continue
            before = c.vehicle.getRoute(vid)
            c.vehicle.rerouteTraveltime(vid, currentTravelTimes=current)
            self.steer_stats["reroutes"] += 1
            if c.vehicle.getRoute(vid) != before:
                self.steer_stats["route_changed"] += 1
                self.steered.add(vid)
        self.steer_stats["minutes"] += 1

    def _vehicle_state(self, vid: str) -> int:
        if vid in self.crashed:
            return CRASHED
        a = self.amb
        if a is not None:
            if vid == a.run.vehicle_id:
                return AMBULANCE_STATE
            if vid in a.run.makeway.before:
                return MAKING_WAY
        return STEERED if vid in self.steered else NORMAL

    def _publish(self, live: bool) -> None:
        c = self.conn
        res = c.vehicle.getAllSubscriptionResults()
        now = {}
        for vid, r in res.items():
            pos = r.get(0x42)
            if pos is None:
                continue
            if abs(pos[0]) > 1e7 or abs(pos[1]) > 1e7:
                continue                                         # SUMO's INVALID_DOUBLE_VALUE: not on the road this step (teleporting)
            lon, lat = self.net.convertXY2LonLat(*pos)
            if not (math.isfinite(lon) and math.isfinite(lat)):
                continue
            now[vid] = {"lon": round(lon, 6), "lat": round(lat, 6), "angle": int(round(r.get(0x43, 0))), "speed": int(round(r.get(0x40, 0) * 3.6)),
                        "s": self._vehicle_state(vid)}
        with self.lock:
            delta = diff_dicts(self.vehicles, now)
            self.vehicles = now
            if not live and int(self.t) % 30:
                return                                           # during the warm-up only a status every 30 simulated seconds
            self.index += 1
            if live and not self.sent_live:
                msg, self.sent_live = {"type": "full", "t": self.t, "vehicles": dict(now), **self._status()}, True
            else:
                msg = {"type": "step", "t": self.t, "vehicles": delta, **self._status(light=True)} if live else {"type": "status", **self._status()}
            self.frames.append((self.index, msg))
            del self.frames[:-MAX_FRAMES]

    def _publish_status(self) -> None:
        with self.lock:
            self.index += 1
            self.frames.append((self.index, {"type": "status", **self._status()}))
            del self.frames[:-MAX_FRAMES]

    def event(self, kind: str, text: str, key: str = "", **params) -> None:
        self.events.append({"t": self.t, "kind": kind, "text": text, "key": key, "params": params})

    def say(self, text: str, key: str = "", **params) -> None:
        """The status line (English for the API; key and params for the page)."""
        self.message, self.message_key, self.message_params = text, key, params

    # ------------------------------------------------------------------ commands
    def _commands(self) -> None:
        while True:
            try:
                cmd = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                self._do(cmd)
            except Refused as exc:
                self.event("refused", str(exc), exc.key, **exc.params)
            except Exception as exc:                                 # noqa: BLE001 - shown in the panel
                self.event("error", f"{type(exc).__name__}: {exc}", "error", text=f"{type(exc).__name__}: {exc}")

    def _do(self, cmd: dict) -> None:
        kind = cmd.get("cmd")
        if kind == "crash":
            self._crash(float(cmd["lon"]), float(cmd["lat"]))
        elif kind == "clear_crashes":
            for vid in list(self.crashed):
                if vid in self.conn.vehicle.getIDList():
                    self.conn.vehicle.setSpeed(vid, -1)
                    self.conn.vehicle.setLaneChangeMode(vid, 0b011001010101)
                self.crashed.pop(vid)
            self.event("crash", "crashes cleared", "cleared")
        elif kind == "ambulance":
            to = (float(cmd["to_lon"]), float(cmd["to_lat"])) if cmd.get("to_lon") is not None else None
            self._ambulance(float(cmd["lon"]), float(cmd["lat"]), to)
        elif kind == "demand":
            f = float(cmd["value"])
            if not 0.5 <= f <= 2.0:
                raise Refused("demand must be between 0.5x and 2x", "demandRange")
            self.factor = f
            self.conn.simulation.setScale(self.lt.demand_scale * f)
            self.event("demand", f"demand x{f:g}", "demand", x=f)
        elif kind == "technology":
            if cmd.get("value") not in TECHS:
                raise Refused(f"technology must be one of {TECHS}", "techUnknown")
            self.technology = cmd["value"]
            self.event("technology", f"next ambulance alerts over {self.technology}", "tech", tech=self.technology)
        elif kind == "speed":
            s = float(cmd["value"])
            if not 1 <= s <= 20:
                raise Refused("speed must be 1 to 20 simulated seconds per second", "speedRange")
            self.speed = s
        elif kind == "steer":
            if cmd.get("on"):
                self.steer = self._check_steer(cmd)
                self.event("steer", f"steering with {self.steer['forecaster']}, {self.steer['share']:.0%} of vehicles informed", "steerOn",
                           forecaster=self.steer["forecaster"], pct=round(self.steer["share"] * 100))
            else:
                self.steer = None
                self.event("steer", "steering off", "steerOff")
        elif kind == "stop":
            self.stop_event.set()
        else:
            raise Refused(f"unknown command {kind!r}", "unknownCmd")

    def _nearest_lane(self, lon: float, lat: float, vclass: str = "passenger", radius_m: float = 40):
        x, y = self.net.convertLonLat2XY(lon, lat)
        lanes = [(lane, d) for lane, d in self.net.getNeighboringLanes(x, y, radius_m) if lane.allows(vclass) and lane.getEdge().getFunction() == ""]
        if not lanes:
            raise Refused("that point is not on a road of the simulated area", "offRoad")
        lane, _ = min(lanes, key=lambda p: p[1])
        return lane, x, y

    def _crash(self, lon: float, lat: float) -> None:
        lane, x, y = self._nearest_lane(lon, lat)
        c = self.conn
        cars = [(v, math.dist((x, y), c.vehicle.getPosition(v))) for v in c.lane.getLastStepVehicleIDs(lane.getID())
                if v not in self.crashed and (self.amb is None or v != self.amb.run.vehicle_id)]
        cars = [p for p in cars if p[1] <= CRASH_PICK_M]
        if not cars:
            raise Refused(f"no car within {CRASH_PICK_M:.0f} m of that point on this road; click where cars are", "noCar", m=int(CRASH_PICK_M))
        vid = min(cars, key=lambda p: p[1])[0]
        c.vehicle.setSpeed(vid, 0)
        c.vehicle.setLaneChangeMode(vid, 0)
        lon2, lat2 = self.net.convertXY2LonLat(*c.vehicle.getPosition(vid))
        self.crashed[vid] = {"lane": lane.getID(), "road": lane.getEdge().getID(), "t": self.t, "lon": round(lon2, 6), "lat": round(lat2, 6)}
        name = lane.getEdge().getName() or lane.getEdge().getID()
        self.event("crash", f"crash on {name}: its lane is blocked", "crash", road=name)

    def _ambulance(self, lon: float, lat: float, to: tuple[float, float] | None) -> None:
        if self.amb is not None and self.amb.run.state not in ("arrived",):
            raise Refused("an ambulance is already driving; wait until it arrives", "ambBusy")
        vclass = self.amb_cfg["ambulance"]["vtype"]["vClass"]
        start, _, _ = self._nearest_lane(lon, lat, vclass)
        cmd_to = to is not None
        if to is None:
            if self.hospital is None:
                raise Refused("no hospital in this city's config; click a destination too", "noHospital")
            to = (self.hospital["lon"], self.hospital["lat"])
        end, _, _ = self._nearest_lane(*to, vclass, radius_m=40 if cmd_to else 250)   # a hospital may sit off the roads an ambulance may use
        path, _ = self.net.getShortestPath(start.getEdge(), end.getEdge(), vClass=vclass)
        if not path:
            raise Refused("no road route from there to the destination in the simulated area", "noRoute")
        if self.amb is not None:
            self.amb_log.append(self._counts()["ambulance"])
        self.amb = LiveAmbulance(self, [e.getID() for e in path], (lon, lat), to)
        km = round(sum(e.getLength() for e in path) / 1000, 1)
        self.event("ambulance", f"ambulance started: {len(path)} roads, {km} km, alerts over {self.technology}", "ambStarted", km=km, tech=self.technology)

    def _ambulance_step(self) -> None:
        a = self.amb
        before = a.run.state
        a.run.step(self.t)
        if before != "arrived" and a.run.state == "arrived":
            s = round(a.run.arrived - a.run.departed)
            self.event("ambulance", f"ambulance arrived after {s} s", "ambArrived", s=s)


class LiveAmbulance:
    """The RQ2 AmbulanceRun (core/simulation/ambulance/service.py), arm alert_preemption, on a route from the click. Only `add` differs:
    each ambulance gets its own route id, so a second one can start after the first arrives."""

    n = 0

    def __init__(self, sess: Session, edges: list[str], origin, dest):
        from core.simulation.ambulance import service
        net = sess.net
        signals = []
        for i, eid in enumerate(edges[:-1]):
            tls = net.getEdge(eid).getTLS()
            if tls is not None:
                x, y = net.getEdge(eid).getToNode().getCoord()[:2]
                signals.append({"tls": tls.getID(), "in_edge": eid, "route_index": i, "x": x, "y": y})
        scen = {"city_id": sess.city_id, "edges": edges, "lengths": [net.getEdge(e).getLength() for e in edges], "signals": signals,
                "demand": {"label": "SIMULATION", "calibrated_to": sess.lt.demand_label}}
        cfg = json.loads(json.dumps(sess.amb_cfg))
        cfg["ambulance"]["depart_s"] = sess.t
        LiveAmbulance.n += 1
        route_id = f"{service.ROUTE}_{sess.id}_{LiveAmbulance.n}"

        class Run(service.AmbulanceRun):
            def add(self) -> None:
                self.conn.route.add(route_id, self.scen["edges"])
                self.conn.vehicle.add(service.AMBULANCE, route_id, typeID=service.VTYPE, departLane="best", departSpeed="max")

        self.run = Run(sess.conn, scen, "alert_preemption", sess.technology, 1.0, sess.seed, cfg)
        self.origin = {"lon": round(origin[0], 6), "lat": round(origin[1], 6)}
        self.dest = {"lon": round(dest[0], 6), "lat": round(dest[1], 6)}
