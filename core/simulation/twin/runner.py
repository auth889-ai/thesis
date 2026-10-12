"""Execute one controller branch in a new SUMO process."""
import argparse
import hashlib
import json
import time
from pathlib import Path
from core.common.paths import REPO
from core.simulation.twin import runtime as pr
from core.simulation.twin.state import state_content_hash
from core.simulation.twin.route_application import apply_recommendation
from core.simulation.twin.metrics import congestion_metrics
from core.networking.v2x.channel import Channel, connected
from core.simulation.closed_loop.protocols.oracle_gate import never_inserted_charge
from core.ml.forecasting.routing_forecast import Forecaster

def run_sumo(arm: str, seed: int, routes: Path, out: Path, P: dict, cfg: dict, fc: Forecaster, caps: dict, fork: tuple[Path, str] | None = None, oracle_edgedata: Path | None = None, event_hook=None, control_hook=None, trace_hook=None, *, controller_factory, information, optimizers, full_budget_arms) -> dict:
    import traci
    out.mkdir(parents=True, exist_ok=True)
    net_path = REPO / P["network"]
    ns = argparse.Namespace(net=str(net_path), routes=str(routes), seed=seed, scale=1.0, horizon=P["simulation_duration_s"], edgedata_period=300, time_to_teleport=P["time_to_teleport_s"], sumo_binary="sumo")
    cmd = pr.base_cmd(ns, out) + ["--vehroute-output", str(out / "vehroutes.xml"), "--route-steps", "0"]
    t_begin = 0
    if fork:
        state, state_sha = fork; t_begin = int(P["fork_t0_s"])
        i = cmd.index("--route-files"); cmd = cmd[:i] + cmd[i + 2:]                     # the state carries every vehicle, pending ones included
        cmd += ["--load-state", str(state), "--begin", str(t_begin)]
        if P.get("strict_fresh"):
            if state_content_hash(state) != state_sha:
                raise RuntimeError("Starting SUMO state changed between branches")
    sim_id = f"sim_v2x_s{seed}_{arm}_{P['profile']}_p{int(P['penetration'] * 100)}"
    if P.get("run_namespace"):
        sim_id += "_" + P["run_namespace"]
    t0 = time.time()
    traci.start(cmd, port=pr.free_port(), label=f"{sim_id}-{t0}")
    lanes = {}
    for edge in caps:
        try:
            lanes[edge] = [f"{edge}_{i}" for i in range(traci.edge.getLaneNumber(edge))]
        except traci.TraCIException:
            if P.get("strict_fresh"):
                raise
            lanes[edge] = []
    def apply_caps(t_now):
        for edge, steps in caps.items():
            cap = next((c for tf, c in reversed(steps) if tf <= t_now), steps[0][1])
            for inc in (P.get("incident") or []):
                if inc["edge"] == edge and t_now >= inc["t_start_s"]:
                    cap = min(cap, float(inc["cap_mps"]))
            for lid in lanes.get(edge, []):
                try:
                    traci.lane.setMaxSpeed(lid, cap)
                except traci.TraCIException:
                    if P.get("strict_fresh"):
                        raise
                    pass
    incidents = [dict(i) for i in (P.get("incident") or [])]; incident_log = []
    def apply_incidents(t_now):
        for inc in incidents:
            if inc.get("applied") or t_now < inc["t_start_s"]:
                continue
            n_l = 0
            for lid in [f"{inc['edge']}_{i}" for i in range(traci.edge.getLaneNumber(inc["edge"]))]:
                try:
                    traci.lane.setMaxSpeed(lid, float(inc["cap_mps"])); n_l += 1
                except traci.TraCIException:
                    if P.get("strict_fresh"):
                        raise
                    pass
            inc["applied"] = True; incident_log.append({"edge": inc["edge"], "t_start_s": t_now, "cap_mps": inc["cap_mps"], "lanes": n_l})
    apply_caps(t_begin); apply_incidents(t_begin)                                      # after a state load the lane caps are NOT in the state: re-applied identically in every arm
    up = Channel.from_profile("uplink", P["profile"], seed); down = Channel.from_profile("downlink", P["profile"], seed)
    for channel in (up, down):
        channel.expiry_from_creation = P.get("strict_fresh", False)
        channel.event_hook = trace_hook
    server = controller_factory(P, seed, cfg, fc, net_path, out, sim_id, information[arm], oracle_edgedata, optimizers.get(arm, "vehicle")) if arm in information else None
    if server:
        server.full_budget = arm in full_budget_arms
    reroute_log, teleports, applied, inapplicable, reactive_calls = [], [], 0, 0, 0
    pending_msgs: list[dict] = []; snapshots: list[dict] = []
    conn_cache: dict[str, bool] = {}
    is_conn = lambda v: conn_cache.setdefault(v, connected(v, P["penetration"], seed))
    H, t, k = P["simulation_duration_s"], t_begin, 0
    next_round = (t_begin // P["round_s"] + 1) * P["round_s"]
    while t < H and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep(); t = int(traci.simulation.getTime())
        if control_hook:
            for command in control_hook(t):
                if command["kind"] == "network":
                    for channel in (up, down):
                        channel.latency_ms, channel.loss, channel.ttl_s = command["latency_ms"], command["loss"], command["ttl_s"]
                        channel.jitter_ms, channel.samples = 0, None
                    P["profile_params"].update(latency_ms=command["latency_ms"], loss=command["loss"], ttl_s=command["ttl_s"], jitter_ms=0)
                else:
                    incident = {"edge": command["edge"], "cap_mps": command["cap_mps"], "t_start_s": t}
                    incidents.append(incident)
                    P.setdefault("incident", []).append(dict(incident))
                if event_hook:
                    event_hook({**command, "type": "intervention_applied", "sim_time_s": t})
        if event_hook and t % 30 == 0:
            positions = []
            for vid in sorted(traci.vehicle.getIDList())[:50]:
                xy = traci.vehicle.getPosition(vid)
                lon, lat = traci.simulation.convertGeo(*xy)
                positions.append({"vehicle_id": vid, "lon": lon, "lat": lat, "speed_mps": traci.vehicle.getSpeed(vid), "edge": traci.vehicle.getRoadID(vid)})
            event_hook({"type": "simulation", "sim_time_s": t, "active_vehicles": traci.vehicle.getIDCount(),
                        "reroutes_applied": applied, "inapplicable": inapplicable, "teleports": len(teleports),
                        "uplink_tx": len(up.log), "uplink_rx": sum(e["status"] == "DELIVERED" for e in up.log),
                        "downlink_tx": len(down.log), "downlink_rx": sum(e["status"] == "DELIVERED" for e in down.log),
                        "positions": positions})
        if t % 300 == 0:
            apply_caps(t)
        if incidents:
            apply_incidents(t)
        for vid in traci.simulation.getStartingTeleportIDList():
            try:
                where = traci.vehicle.getRoadID(vid)
            except Exception:
                where = None
            teleports.append({"vehicle_id": vid, "sim_time_s": t, "connected": is_conn(vid), "edge": where})
        if arm == "baseline":
            if t >= next_round:                                   # snapshot of the connected vehicles for the offline decision replay
                snap = {}
                for vid in traci.vehicle.getIDList():
                    if not is_conn(vid):
                        continue
                    try:
                        edge = traci.vehicle.getRoadID(vid)
                        if edge.startswith(":"):
                            continue
                        route = list(traci.vehicle.getRoute(vid)); idx = traci.vehicle.getRouteIndex(vid)
                        if 0 <= idx < len(route) - 2:
                            snap[vid] = [route[idx], route[idx:]]
                    except traci.TraCIException:
                        if P.get("strict_fresh"):
                            raise
                        pass
                snapshots.append({"round": k, "sim_time_s": t, "vehicles": snap}); k += 1; next_round += P["round_s"]
            continue
        if information.get(arm) == "oracle" and oracle_edgedata is None:
            raise RuntimeError("oracle_v2x needs the paired baseline run's edgedata.xml")
        ids = [v for v in traci.vehicle.getIDList() if is_conn(v)]
        if arm == "reactive":
            for vid in ids:
                if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["reactive_period_s"] == 0:
                    try:
                        if trace_hook:
                            old = list(traci.vehicle.getRoute(vid))[traci.vehicle.getRouteIndex(vid):]
                        traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True); reactive_calls += 1
                        if trace_hook:
                            actual = list(traci.vehicle.getRoute(vid))[traci.vehicle.getRouteIndex(vid):]
                            trace_hook({"type": "REACTIVE_ROUTE_RESULT", "vehicle_id": vid, "sim_time_s": t,
                                        "old_route": old, "actual_route": actual, "route_changed": old != actual,
                                        "route_verified": True, "outcome": "APPLIED" if old != actual else "NO_ACTION_DIFFERENCE"})
                    except traci.TraCIException:
                        if P.get("strict_fresh"):
                            raise
                        pass
            continue
        # ---- predictive_v2x: uplink status messages
        for vid in ids:
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % P["status_period_s"] == 0:
                try:
                    edge = traci.vehicle.getRoadID(vid)
                    if edge.startswith(":"):
                        continue
                    up.send(t, {"type": "VEHICLE_STATUS", "from": vid, "to": "TMS", "vehicle_id": vid, "t": t, "edge": edge, "lane_pos_m": round(traci.vehicle.getLanePosition(vid), 1),
                                "speed_mps": round(traci.vehicle.getSpeed(vid), 2), "angle_deg": round(traci.vehicle.getAngle(vid), 1), "route_index": traci.vehicle.getRouteIndex(vid)})
                except traci.TraCIException:
                    if P.get("strict_fresh"):
                        raise
                    pass
        for env in up.deliver(t):
            server.receive(env, t)
        server.detect(t)
        # ---- the round: forecast -> costs -> optimizer -> recommendations
        if t >= next_round:
            vehicles = {}
            for vid in ids:
                try:
                    edge = traci.vehicle.getRoadID(vid)
                    if edge.startswith(":"):
                        continue
                    route = list(traci.vehicle.getRoute(vid)); idx = traci.vehicle.getRouteIndex(vid)
                    if idx < 0 or idx >= len(route) - 2:
                        continue
                    vehicles[vid] = (route[idx], route[idx:])
                except traci.TraCIException:
                    if P.get("strict_fresh"):
                        raise
                    pass
            background = None
            if server.optimizer in ("cap", "net"):
                background = {}
                for vid in traci.vehicle.getIDList():
                    try:
                        route = list(traci.vehicle.getRoute(vid)); idx = traci.vehicle.getRouteIndex(vid)
                        if 0 <= idx < len(route):
                            background[vid] = route[idx:]
                    except traci.TraCIException:
                        if P.get("strict_fresh"):
                            raise
                        pass
            if event_hook:
                event_hook({"type": "planning", "sim_time_s": t, "round": k})
            msgs, rrec = server.plan_round(k, t, vehicles, background)
            if trace_hook:
                record_path = out / f"routing_round_{k}" / "routing_record.json"
                if record_path.exists():
                    record = json.loads(record_path.read_text())
                    for decision in record["decisions"]:
                        trace_hook({"type": "FORECAST_OPTIMIZER_DECISION", "sim_time_s": t, "vehicle_id": decision["vehicle"],
                                    "forecast": rrec, "decision": decision, "current_route": vehicles[decision["vehicle"]][1],
                                    "selected_route": record["selected_routes"].get(decision["vehicle"])})
            if event_hook:
                event_hook({"type": "forecast_and_routing", "sim_time_s": t, "round": rrec,
                            "inference_seconds": server.rounds[-1].get("inference_seconds")})
            pending_msgs.extend(msgs)
            print(f"      round {k} t={t}s as_of={rrec['as_of_index']} priced={rrec['priced_edges']} considered={rrec['vehicles_considered']} decisions={rrec['decisions']} sent={len(msgs)} statuses={rrec['statuses_known']}", flush=True)
            k += 1; next_round += P["round_s"]
        # ---- staggered sending: a recommendation leaves the server at its send_at_s, not all at once
        due_now = [m for m in pending_msgs if m.get("send_at_s", m["created_s"]) <= t]
        for m in due_now:
            down.send(t, m); pending_msgs.remove(m)
        # ---- downlink delivery: the reroute happens when the message arrives
        for env in down.deliver(t):
            entry = apply_recommendation(traci, env, t, verify=P.get("strict_fresh", False))
            if trace_hook:
                trace_hook({**entry, "type": "TRACI_ROUTE_RESULT"})
            if entry["outcome"] == "DEFERRED_ON_JUNCTION":                    # the message stays with the vehicle; applied at the next step off the junction
                env["deliver_at_s"] = t + 1; env["status"] = "QUEUED"; down.queue.append(env); continue
            if entry["outcome"] == "APPLIED":
                applied += 1
            else:
                inapplicable += 1
            reroute_log.append(entry)
            if event_hook:
                event_hook({**entry, "type": "route_action"})
    up.expire_all(t); down.expire_all(t)
    traci.close()
    m = pr.parse_metrics(out, horizon=H)
    m.update(never_inserted_charge(routes, out / "tripinfo.xml", H))
    m["congestion"] = congestion_metrics(out, net_path, t_begin, H)
    m["total_vehicle_hours_incl_never_inserted"] = round(m["total_vehicle_hours"] + m["never_inserted_vehicle_hours"], 4)
    m["teleports"] = len(teleports); m["teleport_events"] = teleports
    m["reactive_reroute_calls"] = reactive_calls
    m["incidents_applied"] = incident_log
    m["wall_s"] = round(time.time() - t0, 1)
    first_applied = next((e["sim_time_s"] for e in reroute_log if e["outcome"] == "APPLIED"), None)
    inc_t = min((float(i["t_start_s"]) for i in (P.get("incident") or [])), default=None)
    net_metrics = {"uplink": up.metrics(H), "downlink": down.metrics(H), "connected_vehicles": sum(1 for v in conn_cache.values() if v), "vehicles_seen": len(conn_cache), "penetration_configured": P["penetration"],
                   "recommendations_delivered": sum(1 for e in reroute_log), "reroutes_applied": applied, "recommendations_inapplicable": inapplicable,
                   "incidents_detected": (server.incidents if server else []), "incident_detection_delay_s": (server.incidents[0].get("detection_delay_s") if server and server.incidents else None),
                   "lead_time": {"incident_onset_s": inc_t, "first_reroute_applied_s": first_applied, "first_reroute_after_onset_s": (first_applied - inc_t) if (inc_t is not None and first_applied is not None and first_applied >= inc_t) else None,
                                 "reroutes_before_onset": sum(1 for e in reroute_log if e["outcome"] == "APPLIED" and inc_t is not None and e["sim_time_s"] < inc_t)}}
    if snapshots:
        (out / "round_snapshots.json").write_text(json.dumps({"seed": seed, "as_of0": fc.as_of0, "round_s": P["round_s"], "snapshots": snapshots}, indent=0))
    (out / "reroute_log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in reroute_log))
    # Keep both sides of the simulated channel.  The payload is retained because a per-vehicle
    # causal trace needs the observed edge/speed that reached the traffic-management server.
    (out / "messages_uplink.jsonl").write_text("".join(json.dumps({k: v for k, v in e.items() if k != "payload"} | e["payload"]) + "\n" for e in up.log))
    (out / "messages_downlink.jsonl").write_text("".join(json.dumps({k: v for k, v in e.items() if k != "payload"} | {"vehicle_id": e["payload"].get("vehicle_id")}) + "\n" for e in down.log))
    (out / "network_metrics.json").write_text(json.dumps(net_metrics, indent=1))
    res = {"simulation_run_id": sim_id, "arm": arm, "seed": seed, "profile": P["profile"], "penetration": P["penetration"], "moment": P["moment"], "config_hash": P["routing_config_hash"], "network_hash": P["network_hash"],
           "fork": {"t0_s": P.get("fork_t0_s"), "state_file": str(fork[0].relative_to(REPO)), "state_sha256": fork[1]} if fork else None, "information": information.get(arm, arm),
           "metrics": m, "network": net_metrics, "rounds": server.rounds if server else [], "routing_run_ids": server.routing_run_ids if server else [], "reroute_log_file": str((out / "reroute_log.jsonl").relative_to(REPO)),
           "reroutes_applied": applied, "out_dir": str(out.relative_to(REPO))}
    (out / "arm_result.json").write_text(json.dumps(res, indent=1, default=str))
    return res

