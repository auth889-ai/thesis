"""The stepping loop of a live run: one SUMO step at a time, reading every vehicle through TraCI
subscriptions, applying the arm's rerouting, recording teleports, and publishing the snapshot the
map reads. Nothing is animated for effect: what the map shows is what SUMO computed."""
from __future__ import annotations

import hashlib
import time

from core.simulation.twin.live.probe import note_teleport, update_probe
from core.simulation.twin.live.settings import COLOUR, LIVE_REFRESH_S, MAX_VEHICLES_SHOWN, TELEPORT_REASON


class StepLoop:
    def __init__(self, sim, conn, net, cfg: dict, prep: dict, probe: dict | None, probe_state: dict, demand, live_coupled: bool, t_wall: float, note) -> None:
        import traci.constants as tc
        self.sim, self.conn, self.net, self.cfg, self.prep, self.probe, self.probe_state, self.demand = sim, conn, net, cfg, prep, probe, probe_state, demand
        self.live_coupled, self.t_wall, self.note = live_coupled, t_wall, note
        self.gui = bool(cfg.get("gui"))
        self.sub = [tc.VAR_POSITION, tc.VAR_SPEED, tc.VAR_WAITING_TIME, tc.VAR_ANGLE]
        self.vclass: dict[str, str] = {}                    # vehicle -> its class in the city's vehicle mix, else its SUMO vehicle class; read once at departure
        self.signals = False                                # traffic-light phase states, subscribed on the first step
        self.tc = tc
        self.arrived = self.teleports = self.reroutes = 0
        self.depart_t: dict[str, int] = {}                  # vehicle -> departure step, for the mean travel time so far
        self.tt_sum, self.tt_n = 0.0, 0
        self.heavy: set[str] = set()
        self.rerouted: dict[str, str] = {}                  # vid -> "reactive" | "advised", for the colours
        self.teleport_events: list[dict] = []
        self.last_live = 0.0
        self.t = 0
        self.emergency = None                               # an core.simulation.ambulance.service.AmbulanceRun, when this is an ambulance run

    def run(self) -> int:
        """Step until stopped, until the horizon, or until SUMO has no vehicle left. Returns the last simulation second."""
        sim, conn, cfg = self.sim, self.conn, self.cfg
        while not sim._stop.is_set() and self.t < cfg["duration_s"] and conn.simulation.getMinExpectedNumber() > 0:
            if sim._pause.is_set():
                time.sleep(0.1); continue
            conn.simulationStep()
            self.t = int(conn.simulation.getTime())
            if self.demand:
                self._continuous()
            self._departures(); self._arrivals(); self._teleports()
            if self.probe:
                update_probe(conn, self.probe, self.probe_state, self.t, self.gui, sim)
            if cfg["arm"] == "reactive":
                self._reactive_reroute()
            if self.emergency:
                self.emergency.step(self.t)
                sim._set(emergency=self.emergency.public())
            self._publish()
            if cfg["step_delay_ms"]:
                time.sleep(cfg["step_delay_ms"] / 1000)
        return self.t

    # ------------------------------------------------------------------ per-step work
    def _continuous(self) -> None:
        if self.live_coupled and time.time() - self.last_live >= LIVE_REFRESH_S:
            self.last_live = time.time()
            try:
                self.demand.apply_live()
            except Exception as exc:              # noqa: BLE001 - the twin keeps running
                self.note(f"live refresh failed: {type(exc).__name__}: {exc}")
        self.demand.insert_due(self.t)

    def _departures(self) -> None:
        import traci
        for vid in self.conn.simulation.getDepartedIDList():
            self.conn.vehicle.subscribe(vid, self.sub); self.depart_t[vid] = self.t
            try:
                kind = self.conn.vehicle.getTypeID(vid)                    # a city's vehicle mix names its classes as vehicle types
                self.vclass[vid] = self.conn.vehicle.getVehicleClass(vid) if kind == "DEFAULT_VEHTYPE" or kind.startswith("veh_") or (self.emergency and vid == self.emergency.vehicle_id) else kind
            except traci.TraCIException:
                pass
            if self.gui:
                try:
                    if self.conn.vehicle.getVehicleClass(vid) in ("bus", "truck", "trailer", "coach", "delivery"):
                        self.heavy.add(vid); self.conn.vehicle.setColor(vid, COLOUR["heavy"])
                except traci.TraCIException:
                    pass

    def _arrivals(self) -> None:
        for vid in self.conn.simulation.getArrivedIDList():
            d0 = self.depart_t.pop(vid, None)
            if d0 is not None:
                self.tt_sum += self.t - d0; self.tt_n += 1
        self.arrived += self.conn.simulation.getArrivedNumber()

    def _teleports(self) -> None:
        """Every teleport is recorded, never hidden."""
        import traci
        tele_now = self.conn.simulation.getStartingTeleportIDList()
        self.teleports += len(tele_now)
        for vid in tele_now:
            try:
                edge = self.conn.vehicle.getRoadID(vid)
            except traci.TraCIException:
                edge = None
            is_probe = bool(self.probe and vid == self.probe["id"])
            ev = {"vehicle_id": vid, "sim_time_s": self.t, "edge": edge, "arm": self.cfg["arm"], "reason": TELEPORT_REASON, "is_probe": is_probe}
            self.teleport_events.append(ev)
            if is_probe:
                note_teleport(self.probe_state, self.t, edge)
            self.note(f"TELEPORT {ev}")

    def _is_probe(self, vid: str) -> bool:
        return bool(self.probe and vid == self.probe["id"])

    def _reactive_reroute(self) -> None:
        """Equipped vehicles that the channel reached re-plan on current travel times once a minute, staggered per vehicle."""
        import traci
        from core.simulation.closed_loop.protocols.chains import integrated_chain as ic
        from core.simulation.twin import runtime as pr
        cfg, conn = self.cfg, self.conn
        for vid in conn.vehicle.getIDList():
            if not (pr.equipped(vid, cfg["compliance"]) or self._is_probe(vid)):
                continue
            if not ic.delivered(vid, self.prep["deliver_p"], cfg["v2x"], cfg["seed"]) and not self._is_probe(vid):
                continue
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + self.t) % 60 == 0:
                try:
                    before = conn.vehicle.getRoute(vid)
                    conn.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                    self.reroutes += 1
                    if self.gui and conn.vehicle.getRoute(vid) != before:
                        self.rerouted[vid] = "reactive"; conn.vehicle.setColor(vid, COLOUR["reactive"])
                except traci.TraCIException:
                    pass

    def _colour(self, vid: str, v: float, w: float) -> None:
        """Colour what the viewer sees in sumo-gui: stopped red, otherwise its role."""
        import traci
        from core.simulation.twin import runtime as pr
        cfg = self.cfg
        try:
            if v < 0.1 and w > 20:
                self.conn.vehicle.setColor(vid, COLOUR["stopped"])
            elif vid in self.heavy:
                self.conn.vehicle.setColor(vid, COLOUR["heavy"])
            else:
                advised = vid in self.prep["advised_ids"] or (cfg["arm"] == "prediction_aware" and not self.prep["advised_ids"] and pr.equipped(vid, cfg["compliance"]))
                self.conn.vehicle.setColor(vid, COLOUR[self.rerouted.get(vid) or ("advised" if advised else "normal")])
        except traci.TraCIException:
            pass

    def _publish(self) -> None:
        """Read every subscribed vehicle once and publish positions and KPIs for this step."""
        from core.simulation.twin import runtime as pr
        tc, cfg, t = self.tc, self.cfg, self.t
        res = self.conn.vehicle.getAllSubscriptionResults()
        vehicles, speeds, waits, halting = [], [], [], 0
        for vid, d in res.items():
            x, y = d[tc.VAR_POSITION]
            v = float(d[tc.VAR_SPEED]); w = float(d[tc.VAR_WAITING_TIME])
            if v < 0 or x < -1e6:                         # arrived this step: INVALID values
                continue
            speeds.append(v); waits.append(w); halting += v < 0.1
            if self.gui and t % 5 == 0 and not self._is_probe(vid):
                self._colour(vid, v, w)
            if len(vehicles) < MAX_VEHICLES_SHOWN:
                lon, lat = self.net.convertXY2LonLat(x, y)
                marked = vid in self.emergency.makeway.before if self.emergency else pr.equipped(vid, cfg["compliance"])     # in an ambulance run: making way now
                vehicles.append([round(lon, 6), round(lat, 6), round(v * 3.6, 1), int(marked),
                                 vid, round(float(d.get(tc.VAR_ANGLE, 0.0)), 1), self.vclass.get(vid, "passenger")])
        n = len(res)
        if not self.signals:                                # one subscription per traffic light, then one read per step for all of them
            self.signals = True
            for tid in self.conn.trafficlight.getIDList():
                self.conn.trafficlight.subscribe(tid, [tc.TL_RED_YELLOW_GREEN_STATE])
        self.sim._set(signals={tid: r[tc.TL_RED_YELLOW_GREEN_STATE] for tid, r in self.conn.trafficlight.getAllSubscriptionResults().items()})
        if self.probe:
            self.sim._set(probe=dict(self.probe_state))
        self.sim._set(sim_time_s=t, vehicles=vehicles, teleport_events=self.teleport_events[-200:], kpis={
            "vehicles_on_road": n, "shown": len(vehicles), "mean_travel_time_so_far_s": round(self.tt_sum / self.tt_n, 1) if self.tt_n else None,
            "trips_completed": self.tt_n, "teleport_events": len(self.teleport_events), "probe_status": self.probe_state.get("status") if self.probe else None,
            "mean_speed_kmh": round(sum(speeds) / n * 3.6, 2) if n else 0.0,
            "mean_waiting_s": round(sum(waits) / n, 2) if n else 0.0,
            "halting": halting, "arrived": self.arrived, "teleports": self.teleports,
            "reroutes": self.reroutes, "sim_time_s": t, "wall_s": round(time.time() - self.t_wall, 1),
            "progress": 0.0 if cfg["continuous"] else round(t / cfg["duration_s"], 3),
            "hour": self.demand.hour(t) if self.demand else None,
            "live_applied_utc": self.demand.live_applied_utc if self.demand else None,
            "live_multipliers": self.demand.live_mult if self.demand else {}})
