"""Read one vehicle's persisted causal evidence independently of HTTP."""
from pathlib import Path
import json
import re


def _vehicle_events(path: Path, vehicle: str):
    """Stream large message logs; retain only the selected vehicle's evidence."""
    if path.exists():
        with path.open() as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("vehicle_id") == vehicle:
                    yield record


def vehicle_trace(repo: Path, run: str, seed: int, arm: str, vehicle: str) -> dict:
    """The causal chain for ONE vehicle in one arm, read from the run's own logs: the server round that
    considered it (forecast hash, information source), its routing decision with candidate costs, the
    ROUTE_RECOMMENDATION message and its fate in the channel, the reroute applied in SUMO, and the trip
    outcome next to the same vehicle's outcome in the baseline arm (same demand, same start state)."""
    import xml.etree.ElementTree as ET
    if any(not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", value) for value in (run, arm)):
        raise ValueError("run and arm must be identifiers, not paths")
    root = repo / "results/v2x/closed_loop" / run
    arm_dir = root / f"s{seed}" / arm
    if not (arm_dir / "arm_result.json").exists():
        raise FileNotFoundError(f"no arm result for {run}/s{seed}/{arm}")
    res = json.loads((arm_dir / "arm_result.json").read_text())
    decisions = []
    for r in res.get("rounds", []):
        rec_path = root / f"s{seed}" / arm / f"routing_round_{r['round']}" / "routing_record.json"
        if not rec_path.exists():
            continue
        rec = json.loads(rec_path.read_text())
        for d in rec.get("decisions", []):
            if d.get("vehicle") == vehicle:
                decisions.append({"round": r["round"], "sim_time_s": r["sim_time_s"], "routing_run_id": r["routing_run_id"], "information": r.get("information"), "raw_prediction_hash": r.get("raw_prediction_hash"), "future_cost_hash": r.get("future_cost_hash"),
                                  "priced_edges": r.get("priced_edges"), "correction": r.get("correction"), "time_dependent": r.get("time_dependent"), "optimizer": r.get("optimizer"),
                                  **{k: d.get(k) for k in ("decision", "selected", "best_alternative", "current_future_cost_s", "alternative_future_cost_s", "predicted_saving_s", "predicted_saving_pct", "threshold_s", "threshold_pct", "candidates_requested", "candidates_real")},
                                  "candidates": [{k: c.get(k) for k in ("base_tt_s", "forecast_future_tt_s", "overlap_with_current")}
                                                 | {"id": c.get("route_id") or c.get("id"), "edges_n": len(c.get("edges") or [])}
                                                 for c in (d.get("candidates") or [])]})
    msgs = _vehicle_events(arm_dir / "messages_downlink.jsonl", vehicle)
    msgs = [{k: m.get(k) for k in ("msg_id", "routing_run_id", "type", "created_s", "deliver_at_s", "delivered_s", "latency_ms", "status", "expires_s", "size_bytes")} for m in msgs if m.get("vehicle_id") == vehicle]
    uplink_file = arm_dir / "messages_uplink.jsonl"
    uplink = _vehicle_events(uplink_file, vehicle)
    uplink = [{k: m.get(k) for k in ("msg_id", "type", "created_s", "deliver_at_s", "delivered_s", "latency_ms", "status", "expires_s", "size_bytes", "edge", "speed_mps", "lane_pos_m", "route_index")} for m in uplink if m.get("vehicle_id") == vehicle]
    rl = _vehicle_events(arm_dir / "reroute_log.jsonl", vehicle)
    rl = [{k: e.get(k) for k in ("message_id", "sim_time_s", "outcome", "routing_run_id", "latency_ms", "predicted_saving_s", "old_predicted_cost_s", "new_predicted_cost_s", "reason", "model", "forecast_hash")} | {"old_route_edges": len(e.get("old_route") or []), "new_route_edges": len(e.get("new_route") or [])} for e in rl if e.get("vehicle_id") == vehicle]
    def trip(a):
        f = root / f"s{seed}" / a / "tripinfo.xml"
        if not f.exists():
            return None
        for ti in ET.parse(f).getroot().iter("tripinfo"):
            if ti.get("id") == vehicle:
                return {k: float(ti.get(k)) for k in ("depart", "arrival", "duration", "routeLength", "waitingTime", "timeLoss", "rerouteNo") if ti.get(k) is not None}
        return {"status": "not arrived within the horizon"}
    this, base = trip(arm), trip("baseline")
    return {"run": run, "seed": seed, "arm": arm, "vehicle": vehicle, "information": res.get("information"), "fork": res.get("fork"), "decisions": decisions, "status_uplink": uplink,
            "status_uplink_logged": uplink_file.exists(), "messages": msgs, "reroutes": rl,
            "outcome": {"this_arm": this, "baseline": base, "travel_time_delta_s": (this["duration"] - base["duration"])
                        if this and base and "duration" in this and "duration" in base
                        and this.get("arrival", -1) >= 0 and base.get("arrival", -1) >= 0 else None}}

