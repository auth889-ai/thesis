"""V2x HTTP endpoints."""
from __future__ import annotations

import json
import re
from fastapi import HTTPException
from app.protocols.evidence.vehicle_trace import vehicle_trace
from app import evidence_paths as config
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/experiment/v2x_closed_loop", tags=["experiment"])
def experiment_v2x_closed_loop(run: str | None = None):
    """The V2X closed-loop runs (src/pipeline/v2x/closed_loop.py): every run directory with its protocol,
    paired traffic metrics, network metrics and reroute counts — read as-is, never recomputed."""
    root = config.REPO / "results/v2x/closed_loop"
    dirs = sorted((d for d in root.glob("*/report.json")), key=lambda f: f.stat().st_mtime) if root.exists() else []
    if not dirs:
        return {"available": False, "command": "python -m app.control.closed_loop --city la_c4_central_wide --seeds 101 --profile ideal"}
    def summary(f):
        rep = json.loads(f.read_text()); P = rep["protocol"]
        key = "total_vehicle_hours_incl_never_inserted"
        return {"run": f.parent.name, "report": str(f.relative_to(config.REPO)), "city_id": P["city_id"], "profile": P["profile"], "profile_params": P["profile_params"], "penetration": P["penetration"], "moment": P.get("moment"),
                "seeds": rep["seeds"], "arms": rep["arms"], "model": P["model_label"], "checkpoint_sha256": P["checkpoint_sha256"], "mapped_detectors": P["mapped_detectors"], "communication": P["communication"], "demand": P["demand"],
                "paired": {pk: ms.get(key) for pk, ms in rep["paired"].items()}, "network": rep["network_summary"], "generated_utc": rep["generated_utc"]}
    runs = [summary(f) for f in dirs]
    if run:
        f = root / run / "report.json"
        if not f.exists():
            raise HTTPException(404, f"no such run {run}")
        rep = json.loads(f.read_text())
        rep["reroute_examples"] = []
        for r in rep["per_seed"]:
            for a, x in r["arms"].items():
                lf = config.REPO / x.get("reroute_log_file", "") if x.get("reroute_log_file") else None
                if lf and lf.exists():
                    rep["reroute_examples"] += [json.loads(l) for l in lf.read_text().splitlines()[:5]]
        return {"available": True, "result_source": "SYNTHETIC_WHAT_IF", "run": rep}
    return {"available": True, "result_source": "SYNTHETIC_WHAT_IF", "runs": runs}


@router.get("/api/experiment/v2x_closed_loop/vehicle_trace", tags=["experiment"])
def experiment_v2x_vehicle_trace(run: str, seed: int, arm: str, vehicle: str):
    """Return persisted causal evidence; never run inference or simulation here."""
    try:
        return vehicle_trace(config.REPO, run, seed, arm, vehicle)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/api/experiment/v2x_closed_loop/timeline", tags=["experiment"])
def experiment_v2x_timeline(run: str, seed: int, arm: str = "predictive_v2x"):
    """The control-room replay of one closed-loop arm: rounds, incidents, every delivered recommendation with
    its old/new route geometry, the incident edge, the corridor backdrop, and the arm comparison — all read
    from the run's own files."""
    from app.forecasting.operations import road_forecasts as forecast_map
    from app.protocols.evidence.replay_verification import verify
    if any(not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", value) for value in (run, arm)):
        raise HTTPException(422, "Run and arm must be identifiers, not paths")
    root = config.REPO / "results/v2x/closed_loop" / run
    try:
        verification = verify(root)
    except (ValueError, OSError) as exc:
        raise HTTPException(409, f"Replay verification FAILED: {exc}")
    arm_dir = root / f"s{seed}" / arm
    if not (arm_dir / "arm_result.json").exists():
        raise HTTPException(404, f"no arm result for {run}/s{seed}/{arm}")
    rep = json.loads((root / "report.json").read_text()) if (root / "report.json").exists() else {}
    P = rep.get("protocol") or json.loads((root / "PROTOCOL.json").read_text())
    res = json.loads((arm_dir / "arm_result.json").read_text())
    net, net_path, man = forecast_map._net(P["city_id"])
    def shape(eid):
        try:
            return forecast_map._shape(net, net.getEdge(eid))
        except KeyError:
            return None
    reroutes = [json.loads(l) for l in (arm_dir / "reroute_log.jsonl").read_text().splitlines()] if (arm_dir / "reroute_log.jsonl").exists() else []
    events = []
    for e in reroutes:
        if e.get("outcome") == "APPLIED":
            events.append({**{k: e.get(k) for k in ("vehicle_id", "sim_time_s", "latency_ms", "routing_run_id", "forecast_hash", "predicted_saving_s", "old_predicted_cost_s", "new_predicted_cost_s", "reason", "model")},
                           "old_route": [s for s in (shape(x) for x in e.get("old_route", [])) if s], "new_route": [s for s in (shape(x) for x in e.get("new_route", [])) if s], "outcome": "APPLIED"})
        else:
            events.append({k: e.get(k) for k in ("vehicle_id", "sim_time_s", "latency_ms", "outcome", "routing_run_id")})
    msgs = [json.loads(l) for l in (arm_dir / "messages_downlink.jsonl").read_text().splitlines()] if (arm_dir / "messages_downlink.jsonl").exists() else []
    incidents = [{**i, "shape": shape(i["edge"])} for i in (res.get("metrics", {}).get("incidents_applied") or P.get("incident") or [])]
    detected = (res.get("network") or {}).get("incidents_detected") or []
    arms = {}
    for r in rep.get("per_seed", []):
        if r["seed"] == seed:
            for a, x in r["arms"].items():
                m = x["metrics"]; arms[a] = {k: m.get(k) for k in ("total_vehicle_hours_incl_never_inserted", "mean_travel_time_all", "p95_travel_time_s", "arrived", "teleports")} | {"reroutes_applied": x.get("reroutes_applied", 0)}
    bg = forecast_map._background(P["city_id"])
    return {"run": run, "seed": seed, "arm": arm, "city_id": P["city_id"], "bbox": man["bbox"], "protocol": {k: P.get(k) for k in ("profile", "profile_params", "penetration", "moment", "round_s", "horizon_min", "model_label", "checkpoint_sha256", "mapped_detectors", "communication", "demand", "fork_t0_s", "fork")},
            "fork": res.get("fork"), "network": {k: v for k, v in (res.get("network") or {}).items() if k != "incidents_detected"}, "incidents_detected": detected, "incidents": incidents,
            "rounds": res.get("rounds", []), "events": events, "messages": [{k: m.get(k) for k in ("msg_id", "vehicle_id", "created_s", "deliver_at_s", "latency_ms", "status")} for m in msgs],
            "arms": arms, "arm_origins": rep.get("arm_origins"), "execution_kind": rep.get("execution_kind"), "replay_verification": verification,
            "background": {"major_edges": bg["major_edges"], "edges": bg["edges"]}, "duration_s": P.get("simulation_duration_s")}
