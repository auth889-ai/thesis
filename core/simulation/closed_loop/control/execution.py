#!/usr/bin/env python3
"""Fresh identical-state comparison. Static protocol/assets are inputs, saved results are not."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import traceback
import shutil

from core.common.paths import REPO
from core.simulation.closed_loop.control.scenario import REFERENCE, read
from core.simulation.closed_loop.control import closed_loop as cl
from core.simulation.closed_loop.control.live_controls import Timeline, scheduled
from core.common.data.execution_trace import TraceStore
from core.simulation.routing import edge_costs as ec
from core.simulation.closed_loop.protocols.oracle_gate import sha_file

ARMS = ("predictive_v2x", "baseline", "reactive", "persistence_v2x", "oracle_v2x")
JOBS = REPO / "results/v2x/executions"


class ExecutionCancelled(Exception):
    pass


def save(path, data):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, indent=1, default=str))
    temp.replace(path)


def execute(job_id):
    job_dir = JOBS / job_id
    request = read(job_dir / "request.json")
    state = {"job_id": job_id, "run_id": job_id, "run": job_id, "status": "running", "stage": "checking_static_inputs",
             "arm": "warmup", "started_utc": datetime.now(timezone.utc).isoformat(), "protocol_version": "fresh_identical_state_v2",
             "execution_kind": "FRESH_EXECUTION", "controls_open": False, "recent_actions": [], "forecast": None, "simulation": None}
    trace = None
    def publish(**changes):
        if changes.get("status") not in {"failed", "cancelled"} and (job_dir / "cancel.request").exists():
            raise ExecutionCancelled("Cancellation requested; partial output is not a completed experiment.")
        state.update(changes)
        state["updated_utc"] = datetime.now(timezone.utc).isoformat()
        save(job_dir / "status.json", state)
    try:
        publish()
        # Configuration is reusable; historical simulation outputs are not.
        P = read(REPO / "results/v2x/closed_loop" / REFERENCE / "PROTOCOL.json")
        cfg = ec.load_config()
        if cfg["_config_hash"] != P["routing_config_hash"] or cl.controller_config()["_hash"] != P["controller_config_hash"]:
            raise RuntimeError("Frozen optimizer/controller configuration changed")
        for path_key, hash_key in (("network", "network_hash"), ("mapping_file", "mapping_hash")):
            if sha_file(REPO / P[path_key]) != P[hash_key]:
                raise RuntimeError(f"Frozen {path_key} changed")
        if cl.sumo_version() != P["sumo_version"]:
            raise RuntimeError("SUMO version differs from frozen protocol")
        checkpoint = Path(P["checkpoint_path"])
        checkpoint_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if not checkpoint_sha.startswith(P["checkpoint_sha256"]):
            raise RuntimeError("Checkpoint hash mismatch")
        if request.get("protocol_version") != "fresh_identical_state_v2":
            raise ValueError("Legacy execution requests cannot be resumed as fresh experiments")
        seed = request["seed"]
        root = REPO / "results/v2x/closed_loop" / job_id
        root.mkdir(exist_ok=False)
        P.update(run_namespace=job_id, strict_fresh=True, seeds=[seed], checkpoint_sha256=checkpoint_sha,
                 observation_as_of_index=request["observation_as_of_index"], protocol_id="FRESH_IDENTICAL_STATE_v2",
                 moment_rule="Explicit recorded observation index at simulation t=0; advances every 300 seconds.",
                 ttl_semantics="Expires from payload creation, including server staggering and channel delay.")
        save(root / "PROTOCOL.json", P)
        publish(stage="loading_checkpoint", start_sim_time_s=0, end_sim_time_s=P["simulation_duration_s"],
                checkpoint_sha256=checkpoint_sha, observation_as_of_index=P["observation_as_of_index"],
                input_scope="RECORDED METR-LA OBSERVATIONS", traffic_scope="SYNTHETIC SUMO DEMAND",
                networking_scope="SIMULATED V2X EMULATOR")
        fc = cl.Forecaster(P, seed)
        caps = fc.caps(P["simulation_duration_s"])
        net = cl.net_for(REPO / P["network"])
        save(job_dir / "routable_edges.json", [e.getID() for e in net.getEdges() if e.allows("passenger")])
        publish(forecast_contract=fc.contract, horizons_min=[0, 15, 30, 60],
                routing_horizon_min=P["horizon_min"], network_profile=P["profile_params"])
        trace = TraceStore(job_dir)
        def event(value):
            value = {**value, "arm": state["arm"], "run_id": job_id}
            with (job_dir / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(value) + "\n")
            trace.flush()
            if value["type"] == "simulation":
                publish(stage="observing_traffic" if state["arm"] == "warmup" else "simulating", simulation=value)
            elif value["type"] == "planning":
                publish(stage="inference_and_optimization", planning_time_s=value["sim_time_s"])
            elif value["type"] == "forecast_and_routing":
                publish(stage="sending_recommendations", forecast=value["round"])
            elif value["type"] == "route_action":
                publish(recent_actions=(state["recent_actions"] + [value])[-20:])
            elif value["type"] == "intervention_applied":
                publish(last_intervention=value)
        publish(stage="generating_new_demand")
        routes, demand = cl.demand_for_seed(P, seed, root / f"s{seed}" / "demand")
        publish(stage="starting_warmup_sumo")
        fork = cl.save_fork_state(seed, routes, root / f"s{seed}" / "prefix", P, caps, event_hook=event)
        fork_record = {"t0_s": P["fork_t0_s"], "state_file": str(fork[0].relative_to(REPO)), "state_sha256": fork[1]}
        publish(fork_sha256=fork[1], start_sim_time_s=P["fork_t0_s"])
        timeline = Timeline(job_dir)
        arms, interventions = {}, []
        for arm in ARMS:
            publish(arm=arm, stage="starting_sumo", controls_open=arm == "predictive_v2x", forecast=None,
                    simulation=None, recent_actions=[], completed_arms=list(arms))
            arms[arm] = cl.run_sumo(arm, seed, routes, root / f"s{seed}" / arm, copy.deepcopy(P), cfg, fc, caps, fork,
                root / f"s{seed}/baseline/edgedata.xml" if arm == "oracle_v2x" else None,
                event_hook=event, control_hook=timeline.poll if arm == "predictive_v2x" else scheduled(interventions),
                trace_hook=lambda value: trace.add(arm, value))
            if arm == "predictive_v2x":
                interventions = timeline.freeze(publish)
        origins = {arm: "FRESH_EXECUTION" for arm in arms}
        rec = {"seed": seed, "as_of_index": fc.as_of0, "demand": demand, "fork": fork_record, "arms": arms}
        result = cl.report(P, [rec], list(arms))
        result.update(execution_kind="FRESH_EXECUTION", arm_origins=origins, run_dir=str(root.relative_to(REPO)),
                      research_gate_update=False, interventions=interventions,
                      comparison_scope="All arms freshly executed from the same new state. Single realization; no new significance claim.")
        save(root / "report.json", result)
        save(root / "provenance.json", {"run_id": job_id, "internal_seed": seed, "request": request, "fork": fork_record,
             "demand": demand, "checkpoint_sha256": checkpoint_sha, "interventions": interventions, "arm_origins": origins,
             "execution_order": list(ARMS), "ttl_semantics": P["ttl_semantics"], "research_gate_update": False})
        trace.close()
        trace = None
        shutil.copyfile(job_dir / "trace.sqlite", root / "vehicle_trace.sqlite")
        shutil.copyfile(job_dir / "events.jsonl", root / "execution_events.jsonl")
        manifest = {}
        for path in root.rglob("*"):
            if path.is_file():
                with path.open("rb") as stream:
                    manifest[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
        save(root / "manifest.json", manifest)
        publish(status="done", stage="complete", controls_open=False, seed=seed, completed_arms=list(arms), result={
            "arm_origins": origins, "metrics": {a: x["metrics"] for a, x in arms.items()},
            "fresh_reroutes_applied": arms["predictive_v2x"]["reroutes_applied"],
            "comparison_scope": result["comparison_scope"], "report": str((root / "report.json").relative_to(REPO)),
            "network": arms["predictive_v2x"]["network"]})
    except ExecutionCancelled as exc:
        publish(status="cancelled", stage="cancelled", controls_open=False, error=str(exc))
    except Exception as exc:
        publish(status="failed", stage="failed", controls_open=False, error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        raise
    finally:
        if trace:
            trace.close()
        try:
            import traci
            traci.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()
    from core.simulation.closed_loop.control.jobs import ID
    if not ID.fullmatch(args.job_id):
        raise SystemExit("invalid job identifier")
    execute(args.job_id)


if __name__ == "__main__":
    main()
