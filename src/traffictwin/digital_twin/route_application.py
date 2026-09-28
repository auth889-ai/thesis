"""Apply delivered route recommendations and verify TraCI readback."""
def apply_recommendation(traci, env: dict, t: float, verify=False) -> dict:
    """A ROUTE_RECOMMENDATION has just ARRIVED at the vehicle (after the channel's latency). Apply it
    only if the vehicle still exists and is still on an edge of the recommended route; otherwise it
    is logged as inapplicable. Nothing is applied for dropped messages because they never arrive."""
    m = env["payload"]; vid = m["vehicle_id"]
    entry = {"vehicle_id": vid, "sim_time_s": t, "message_id": env["msg_id"], "created_s": m["created_s"], "latency_ms": env["latency_ms"],
             "routing_run_id": m.get("routing_run_id"), "forecast_hash": m.get("forecast_hash"), "edge_cost_hash": m.get("edge_cost_hash"), "model": m.get("model"), "horizon_min": m.get("horizon_min"),
             "reason": m.get("reason"), "old_predicted_cost_s": m.get("old_predicted_cost_s"), "new_predicted_cost_s": m.get("new_predicted_cost_s"), "predicted_saving_s": m.get("predicted_saving_s")}
    try:
        if vid not in traci.vehicle.getIDList():
            entry["outcome"] = "VEHICLE_GONE"; return entry
        cur = traci.vehicle.getRoadID(vid)
        if cur.startswith(":"):
            entry.update(outcome="DEFERRED_ON_JUNCTION", current_edge=cur); return entry      # SUMO refuses route changes mid-junction: retry next step
        new = list(m["route"])
        if cur not in new:
            entry.update(outcome="INAPPLICABLE_PAST_FORK", current_edge=cur); return entry
        tail = new[new.index(cur):]
        old = list(traci.vehicle.getRoute(vid))[traci.vehicle.getRouteIndex(vid):]
        traci.vehicle.setRoute(vid, tail)
        entry.update(outcome="APPLIED", current_edge=cur, old_route=old, new_route=tail, affected_edges=sorted(set(tail) ^ set(old)))
        if verify:
            actual = list(traci.vehicle.getRoute(vid))[traci.vehicle.getRouteIndex(vid):]
            if actual != tail:
                raise RuntimeError(f"TraCI route readback mismatch for {vid}")
            entry.update(route_verified=True, actual_route=actual, route_changed=actual != old)
            if actual == old:
                entry["outcome"] = "NO_ACTION_DIFFERENCE"
    except traci.TraCIException as ex:
        if verify:
            raise
        entry["outcome"] = f"TRACI_ERROR: {ex}"
    return entry

