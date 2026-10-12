"""Automatic incident detection inside SUMO (AID, step J, 2026-10-11; our own design). One run = the corridor at Dhaka's density for
`horizon` s with E1 stations every 300 m on the ambulance route (stations.py). Incidents: at chosen times a vehicle on a chosen segment
stops in its lane (speed 0, no lane change) for `duration` s, then drives on. Every 30 s each station pair gives one row (stations.pair_features),
labelled 1 while an incident is active on that pair's segment. Live mode: a detector (the trained model or California #7) runs on the
rows as they come; a detection triggers the closed loop:
    - the V2X warning (core/networking/v2x/model.py `deliver`) from the pair's downstream station to the equipped cars within range, and
    - rerouting as in the live twin's steering (step A): the segment's edges get a long travel time (traci.edge.adaptTraveltime) and the
      warned cars whose route crosses them reroute (traci.vehicle.rerouteTraveltime).
Trip times are recorded for the comparison with and without the closed loop. SUMO 1.27.1 through TraCI; nothing replayed.
"""
from __future__ import annotations

import hashlib
import random
import statistics
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

from core.common.paths import REPO
from core.simulation.aid import stations as stn

CITY, DEMAND = "dhaka", "dhaka_density"
HORIZON_S = 3600
WARMUP_S = 600
BLOCK_TRAVELTIME_S = 9999.0


def demand_scale() -> float:
    from core.common.data import city_config
    lt = city_config.load(CITY).live_twin
    return lt.demand_scale if lt else 1.0


def plan_incidents(seed: int, n: int, pairs: list[int], horizon: int = HORIZON_S, duration: tuple[int, int] = (180, 300)) -> list[dict]:
    """`n` incidents at random times (after the warm-up, at least 400 s apart) on random pairs from `pairs`; fixed by the seed."""
    rng = random.Random(f"aid-incidents-{seed}")
    out, t = [], WARMUP_S
    for i in range(n):
        t += rng.randint(400, 700)
        if t + duration[1] > horizon - 120:
            break
        out.append({"id": i, "start_s": t, "duration_s": rng.randint(*duration), "pair": rng.choice(pairs)})
    return out


class Run:
    def __init__(self, seed: int, incidents: list[dict], gui: bool = False, detector=None, technology: str = "its_g5", share: float = 0.5,
                 horizon: int = HORIZON_S, colours: bool = False, on_interval=None, scale: float | None = None, cameras: bool = True):
        self.seed, self.incidents, self.gui, self.detector = seed, incidents, gui, detector
        self.technology, self.share, self.horizon, self.colours, self.on_interval = technology, share, horizon, colours, on_interval
        self.scale, self.with_cameras = scale, cameras                 # scale None = the city's counted density (demand_scale()); J2 cameras on by default (read only)
        self.rows: list[dict] = []
        self.cam_rows: list[dict] = []
        self.events: list[dict] = []
        self.trips: dict = {"depart": {}, "done": []}
        self.counts = {"detections": 0, "false_alarms": 0, "warned": 0, "rerouted": 0, "messages_sent": 0, "messages_delivered": 0}
        self.alarm_until: dict[int, float] = {}
        self.active_pairs: set[int] = set()

    # ------------------------------------------------------------------ setup
    def _prepare(self):
        import sumolib
        from core.simulation.ambulance import service
        self.scen = service.scenario(CITY, DEMAND)
        self.net = sumolib.net.readNet(str(self.scen["net"]))
        self.stations = stn.stations(self.net, self.scen["edges"])
        self.pairs = list(range(len(self.stations) - 1))
        self.dir = Path(tempfile.mkdtemp(prefix=f"aid-{self.seed}-"))
        self.loops, self.loops_sha = stn.write_additional(self.dir / "stations.add.xml", self.stations)
        self.limit = {st["id"]: self.net.getEdge(st["edge"]).getSpeed() * 3.6 for st in self.stations}
        cfg = service.settings()
        from core.simulation.aid import cameras as cam
        self.cams = cam.cameras(self.scen, self.net) if self.with_cameras else []
        self.observer = cam.Observer(self.cams) if self.with_cameras else None
        self.scale_used = demand_scale() if self.scale is None else self.scale
        ns = SimpleNamespace(sumo_binary="sumo-gui" if self.gui else "sumo", net=self.scen["net"], routes=self.scen["routes"], seed=self.seed, scale=self.scale_used,
                             horizon=self.horizon, edgedata_period=300, time_to_teleport=cfg["sumo"]["time_to_teleport_s"],
                             sumo_extra=["--lateral-resolution", str(cfg["sumo"]["lateral_resolution"])]
                             + (["--start", "--quit-on-end", "--window-size", "1600,1000", "--delay", "0"] if self.gui else []))
        return ns

    # ------------------------------------------------------------------ the run
    def go(self) -> dict:
        import traci
        from core.simulation.twin import runtime as pr
        ns = self._prepare()
        out = self.dir / "sumo"
        out.mkdir(exist_ok=True)
        label = f"aid-{self.seed}-{time.time_ns()}"
        cmd = pr.base_cmd(ns, out)
        cmd[cmd.index("--additional-files") + 1] += f",{self.dir / 'stations.add.xml'}"      # SUMO takes one option with a comma-separated list
        traci.start(cmd, port=pr.free_port(), label=label)
        c = self.conn = traci.getConnection(label)
        rng = random.Random(f"aid-{self.seed}|{self.technology}|{self.share}")
        from core.networking.v2x import model
        from core.simulation.twin import runtime as prt
        prev: dict[str, list[dict]] = {st["id"]: [] for st in self.stations}
        active: dict[int, dict] = {}                                  # incident id -> {vehicle, until, pair}
        t, t0 = 0.0, time.time()
        if self.gui:
            self._draw_pairs(c)
        try:
            while t < self.horizon:
                c.simulationStep()
                t = c.simulation.getTime()
                if self.observer is not None:
                    self.observer.step(c, t)
                for vid in c.simulation.getDepartedIDList():
                    self.trips["depart"][vid] = t
                for vid in c.simulation.getArrivedIDList():
                    d = self.trips["depart"].pop(vid, None)
                    if d is not None:
                        self.trips["done"].append((d, t))
                self._incidents(c, t, active)
                self.active_pairs = {a["pair"] for a in active.values()}
                if int(t) % stn.PERIOD_S == 0 and t >= stn.PERIOD_S:
                    reading = stn.read_interval(c, self.loops)
                    for sid, r in reading.items():
                        prev[sid].append(r)
                        del prev[sid][:-3]
                    for p in self.pairs:
                        up, down = self.stations[p], self.stations[p + 1]
                        hist = prev[down["id"]]
                        row = {"seed": self.seed, "t": t, "pair": p, "segment": up["segment_edges"][0],
                               **stn.pair_features(reading[up["id"]], reading[down["id"]], hist[-2] if len(hist) >= 2 else None, hist[-3] if len(hist) >= 3 else None, self.limit[down["id"]]),
                               "label": int(any(a["pair"] == p for a in active.values()))}
                        self.rows.append(row)
                        if self.detector is not None and t >= WARMUP_S and self.detector(p, row):
                            self._detected(c, t, p, up, rng, model, prt)
                    if self.observer is not None:
                        from core.simulation.aid import cameras as cam
                        for row in self.observer.window():
                            row.update({"seed": self.seed, "t": t, "label_any": int(bool(active)),
                                        "label_between": int(any(cam.covers(self.cams, (self.stations[a["pair"]]["chainage"], self.stations[a["pair"] + 1]["chainage"])) for a in active.values()))})
                            self.cam_rows.append(row)
                    if self.gui:
                        self._colour_pairs(c, t)
                    if self.on_interval:
                        self.on_interval(c, t, reading, active, self.counts)
        finally:
            try:
                c.close()
            except Exception:                                        # noqa: BLE001
                pass
        start, cut = WARMUP_S, self.horizon
        done = [a - d for d, a in self.trips["done"] if start <= d <= cut and a <= cut]
        open_ = [cut - d for d, a in self.trips["done"] if start <= d <= cut and a > cut] + [cut - d for d in self.trips["depart"].values() if start <= d <= cut]
        cohort = done + open_
        return {"seed": self.seed, "stations": len(self.stations), "pairs": len(self.pairs), "loops_sha256": self.loops_sha, "rows": len(self.rows), "scale": self.scale_used,
                "cameras": self.cams, "cam_rows": len(self.cam_rows),
                "incidents": self.incidents, "events": self.events, "counts": self.counts, "real_s": round(time.time() - t0, 1),
                "cohort_trips": len(cohort), "cohort_mean_s": round(statistics.fmean(cohort), 2) if cohort else None, "still_driving": len(open_),
                "finished_mean_s": round(statistics.fmean(done), 2) if done else None}

    def _incidents(self, c, t: float, active: dict) -> None:
        for inc in self.incidents:
            if inc["id"] in active or t < inc["start_s"] or inc.get("done"):
                continue
            seg = self.stations[inc["pair"]]["segment_edges"]
            cars = [v for e in seg for v in c.edge.getLastStepVehicleIDs(e) if c.vehicle.getSpeed(v) > 1.0]
            if not cars:
                continue                                              # nobody there yet: tried again next step
            v = cars[len(cars) // 2]
            c.vehicle.setSpeed(v, 0)
            c.vehicle.setLaneChangeMode(v, 0)
            if self.gui:
                c.vehicle.setColor(v, (230, 20, 20, 255))
            active[inc["id"]] = {"vehicle": v, "until": t + inc["duration_s"], "pair": inc["pair"]}
            inc["actual_start_s"], inc["vehicle"] = t, v
            self.events.append({"t": t, "kind": "incident", "pair": inc["pair"], "vehicle": v})
        for i, a in list(active.items()):
            if t >= a["until"]:
                if a["vehicle"] in c.vehicle.getIDList():
                    c.vehicle.setSpeed(a["vehicle"], -1)
                    c.vehicle.setLaneChangeMode(a["vehicle"], 0b011001010101)
                    if self.gui:
                        c.vehicle.setColor(a["vehicle"], (200, 200, 200, 255))
                active.pop(i)
                for inc in self.incidents:
                    if inc["id"] == i:
                        inc["done"] = True
                        inc["actual_end_s"] = t

    def _detected(self, c, t: float, p: int, up: dict, rng, model, prt) -> None:
        """The closed loop on a detection: a V2X warning from the pair's downstream station, then step-A rerouting of the warned cars."""
        if self.alarm_until.get(p, -1) > t:
            return                                                    # one alarm per pair per 5 minutes
        self.alarm_until[p] = t + 300
        self.counts["detections"] += 1
        if p not in self.active_pairs:
            self.counts["false_alarms"] += 1                          # an alarm on a pair with no active incident
        self.events.append({"t": t, "kind": "detection", "pair": p, "false": p not in self.active_pairs})
        down = self.stations[p + 1]
        sx, sy = self.net.getEdge(down["edge"]).getShape()[0]
        sender = model.Station(down["id"], sx, sy)
        seg = set(up["segment_edges"])
        for e in seg:
            c.edge.adaptTraveltime(e, BLOCK_TRAVELTIME_S)
        warned = 0
        for v in c.vehicle.getIDList():
            if not prt.equipped(v, self.share):
                continue
            x, y = c.vehicle.getPosition(v)
            d = model.deliver(sender, model.Station(v, x, y), t, self.technology, rng)
            self.counts["messages_sent"] += 1
            if not d.delivered:
                continue
            self.counts["messages_delivered"] += 1
            warned += 1
            if self.colours:
                c.vehicle.setColor(v, (255, 220, 0, 255))
            route, i = c.vehicle.getRoute(v), c.vehicle.getRouteIndex(v)
            if seg & set(route[max(i, 0) + 1:]):
                c.vehicle.rerouteTraveltime(v, False)
                if not seg & set(c.vehicle.getRoute(v)[c.vehicle.getRouteIndex(v) + 1:]):
                    self.counts["rerouted"] += 1
                    if self.colours:
                        c.vehicle.setColor(v, (30, 110, 235, 255))
        self.counts["warned"] += warned
        self.events[-1]["warned"] = warned


    # ------------------------------------------------------------------ sumo-gui: the pairs' colours (display only)
    GREEN, YELLOW, RED = (40, 170, 60, 110), (255, 210, 0, 150), (230, 20, 20, 170)

    def _draw_pairs(self, c) -> None:
        """One polygon per station pair along its segment's lanes, drawn under the cars; green until something is seen."""
        if not hasattr(self, "tentative"):
            self.tentative: dict[int, bool] = {}
        for p in self.pairs:
            shape = []
            for e in self.stations[p]["segment_edges"]:
                shape += [tuple(pt) for pt in self.net.getEdge(e).getShape()]
            c.polygon.add(f"aid_pair_{p}", shape, self.GREEN, fill=False, polygonType="aid", layer=-1, lineWidth=6.0)

    def _colour_pairs(self, c, t: float) -> None:
        for p in self.pairs:
            col = self.RED if self.alarm_until.get(p, -1) > t else self.YELLOW if self.tentative.get(p) else self.GREEN
            c.polygon.setColor(f"aid_pair_{p}", col)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
