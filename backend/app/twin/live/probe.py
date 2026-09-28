"""The user probe: the analysed trip inserted as one vehicle, followed every step, scored from tripinfo."""
from __future__ import annotations

from pathlib import Path

from .settings import COLOUR


def add_probe(conn, probe: dict) -> dict:
    """Insert the probe vehicle on its route (the optimizer's, or SUMO's own findRoute) and return its state record."""
    import traci
    pid = probe["id"]
    if probe.get("route_edges"):                # the prediction-aware arm: duarouter on the forecast weights
        edges = list(probe["route_edges"])
    else:                                       # baseline / reactive: SUMO's own findRoute on the current network
        edges = list(conn.simulation.findRoute(probe["from_edge"], probe["to_edge"]).edges)
        if not edges:
            raise RuntimeError(f"SUMO_OD_MAPPING_FAILED: no route from {probe['from_edge']} to {probe['to_edge']}")
    conn.route.add(f"route_{pid}", edges)
    conn.vehicle.add(pid, f"route_{pid}", depart=str(float(probe.get("depart_s") or 0)), departLane="best", departSpeed="max")
    state = {"vehicle_id": pid, "origin_edge": probe["from_edge"], "destination_edge": probe["to_edge"],
             "initial_route": edges, "initial_route_source": probe.get("route_source") or ("production optimizer route" if probe.get("route_edges") else "traci.simulation.findRoute"),
             "active_route": edges, "departed_s": None, "arrived_s": None, "rerouted_times": 0, "teleported": False,
             "status": "WAITING TO DEPART", "current_edge": None, "speed_kmh": None, "elapsed_s": None, "route_progress": None}
    try:                                    # visibly distinct in sumo-gui: magenta and 8 m long
        conn.vehicle.setColor(pid, COLOUR["probe"]); conn.vehicle.setLength(pid, 8.0); conn.vehicle.setWidth(pid, 2.6)
    except traci.TraCIException:
        pass
    return state


def note_teleport(state: dict, t: int, edge: str | None) -> None:
    state.update(teleported=True, teleported_at_s=t, teleported_edge=edge, status="PROBE TELEPORTED")


def update_probe(conn, probe: dict, state: dict, t: int, gui: bool, sim) -> None:
    """Departure, arrival, and live telemetry straight from SUMO every step. `sim` keeps the gui tracking flag."""
    import traci
    pid = probe["id"]
    if state.get("departed_s") is None and pid in conn.vehicle.getIDList():
        state["departed_s"] = t; state["status"] = "DRIVING"
        if gui and not getattr(sim, "_tracking", None):      # the window follows the user's car from its first metre
            try:
                conn.gui.trackVehicle("View #0", pid); conn.gui.setZoom("View #0", 10000); sim._tracking = pid
            except traci.TraCIException:
                pass
    if state.get("departed_s") is None or state.get("arrived_s") is not None:
        return
    if pid in conn.simulation.getArrivedIDList():
        state["arrived_s"] = t; state["status"] = "ARRIVED"; state["elapsed_s"] = t - state["departed_s"]
        state.update(current_edge=probe["to_edge"], speed_kmh=0.0, route_progress=1.0)
        if gui and getattr(sim, "_tracking", None) == pid:     # the trip is over: stop tracking, show the network
            try:
                conn.gui.trackVehicle("View #0", ""); conn.gui.setZoom("View #0", 1500); sim._tracking = None
            except traci.TraCIException:
                pass
    elif pid in conn.vehicle.getIDList() and not state.get("teleported"):
        try:
            v = conn.vehicle.getSpeed(pid); w = conn.vehicle.getWaitingTime(pid)
            cur_edge = conn.vehicle.getRoadID(pid)
            state.update(current_edge=cur_edge, speed_kmh=round(v * 3.6, 1), elapsed_s=t - state["departed_s"],
                         waiting_now_s=round(w, 1), status="QUEUED" if v < 0.1 and w > 5 else "DRIVING",
                         route_progress=round(conn.vehicle.getRouteIndex(pid) / max(len(state["active_route"]), 1), 3))
            if t % 5 == 0:
                cur = list(conn.vehicle.getRoute(pid))
                if cur != state["active_route"]:
                    state["rerouted_times"] += 1; state["active_route"] = cur
                    state.setdefault("reroute_events", []).append({"sim_time_s": t, "edge": cur_edge, "route_edges": len(cur)})
                if gui:
                    conn.vehicle.setColor(pid, COLOUR["probe"])
        except traci.TraCIException:
            pass


def probe_tripinfo(out: Path, probe: dict, state: dict) -> None:
    """The probe's own trip from SUMO's tripinfo: the measured outcome."""
    import xml.etree.ElementTree as ET
    try:
        for el in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
            if el.get("id") == probe["id"]:
                state.update(travel_time_s=float(el.get("duration")), route_length_m=float(el.get("routeLength")),
                             waiting_time_s=float(el.get("waitingTime")), time_loss_s=float(el.get("timeLoss")),
                             finished=el.get("arrival") not in (None, "-1.00", "-1"))
    except Exception as exc:                          # noqa: BLE001
        state["tripinfo_error"] = str(exc)[:120]
