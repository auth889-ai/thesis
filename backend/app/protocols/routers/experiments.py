"""Experiments HTTP endpoints."""
from __future__ import annotations

import json
import sys
import threading
from core.common import evidence_paths as config
from core.simulation.closed_loop.protocols.evidence.json_reader import _read_json
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/experiment/sweep", tags=["experiment"])
def experiment_sweep(grid: str = "compliance"):
    """E4: the penetration curve, every point a full three-arm paired-seed run."""
    f = config.REPO / f"results/routing/sweep_{grid}.json"
    if not f.exists():
        return {"available": False, "missing": str(f.relative_to(config.REPO)),
                "command": f"make sweep" if grid == "compliance" else "make sweep-v2x"}
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


@router.get("/api/experiment/ablation", tags=["experiment"])
def experiment_ablation():
    """E3: oracle / model / persistence / random through the same chain."""
    f = config.REPO / "results/routing/ablation_forecast_quality.json"
    if not f.exists():
        return {"available": False, "missing": str(f.relative_to(config.REPO)), "command": "make ablation"}
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", **json.loads(f.read_text())}


@router.get("/api/experiment/oracle_gate", tags=["experiment"])
def experiment_oracle_gate(seed_set: str = "final"):
    """The frozen oracle outcome gate (Blocker #3): the newest report of the named seed set, read as-is."""
    root = config.REPO / "results/routing/oracle_gate"
    cands = sorted(root.glob(f"FINAL_PROTOCOL_v1_{seed_set}_cfg*/report.json"), key=lambda f: f.stat().st_mtime) if root.exists() else []
    if not cands:
        return {"available": False, "command": f"python -m core.simulation.closed_loop.protocols.oracle_gate --seeds {seed_set}"}
    rep = json.loads(cands[-1].read_text())
    P = rep.get("protocol", {})
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", "report": str(cands[-1].relative_to(config.REPO)), "seed_set": rep.get("seed_set"),
            "seeds": rep.get("seeds"), "verdict": rep.get("verdict"), "primary": rep.get("primary"), "paired": rep.get("paired"),
            "same_population_all_seeds": rep.get("same_population_all_seeds"), "generated_utc": rep.get("generated_utc"),
            "protocol": {k: P.get(k) for k in ("protocol_id", "network", "network_hash", "demand_source", "demand_sample_fraction", "simulation_duration_s", "routing_round_s",
                                               "compliance", "routing_config_hash", "min_saving_s", "min_saving_pct", "sumo_version", "dev_seeds", "final_seeds", "primary_metric", "coverage_mode")},
            "learned_model_final_outcome": {"status": "SEE_LEARNED_GATE", "endpoint": "/api/experiment/learned_gate", "note": "the learned-model outcome runs under its own frozen protocol (FINAL_LEARNED_PROTOCOL_v1) and is reported separately"}}


@router.get("/api/experiment/learned_gate", tags=["experiment"])
def experiment_learned_gate(seed_set: str = "final"):
    """The frozen learned-model outcome gate (Blocker #6): the newest report of the named seed set, read as-is.
    Headline pairs: Graph WaveNet vs baseline, vs reactive, vs persistence-predictive; persistence vs baseline.
    The oracle arm, when present, is research-only and never the headline."""
    root = config.REPO / "results/routing/learned_gate"
    cands = sorted(root.glob(f"FINAL_LEARNED_PROTOCOL_v1_{seed_set}_cfg*/report.json"), key=lambda f: f.stat().st_mtime) if root.exists() else []
    if not cands:
        return {"available": False, "command": f"python -m core.simulation.closed_loop.protocols.learned_gate --seeds {seed_set}"}
    rep = json.loads(cands[-1].read_text())
    P = rep.get("protocol", {})
    key = P.get("primary_metric_key", "total_vehicle_hours_incl_never_inserted")
    pairs = rep.get("paired", {})
    def head(pk):
        st = (pairs.get(pk) or {}).get(key) or {}
        return {k: st.get(k) for k in ("pair", "seeds", "mean_pct", "median_pct", "ci95", "wins", "losses", "ties", "label", "p_value", "mean_abs")}
    prov = {"protocol_id": P.get("protocol_id"), "model": P.get("model_label"), "checkpoint": P.get("checkpoint"), "checkpoint_sha256": P.get("checkpoint_sha256"), "dataset": P.get("dataset"),
            "dataset_hash": P.get("dataset_hash"), "graph_hash": P.get("graph_hash"), "mapping_hash": P.get("mapping_hash"), "network_hash": P.get("network_hash"), "routing_config_hash": P.get("routing_config_hash"),
            "sumo_version": P.get("sumo_version"), "seeds": rep.get("seeds"), "report": str(cands[-1].relative_to(config.REPO)), "generated_utc": rep.get("generated_utc"), "result_source": "RESEARCH_BENCHMARK"}
    per_seed = [{"seed": r["seed"], "analysis_run_id": r.get("analysis_run_id"), "raw_prediction_hash": r.get("raw_prediction_hash"), "as_of_time": (r.get("forecast_quality") or {}).get("as_of_time"),
                 "arms": {a: {"simulation_run_id": x.get("simulation_run_id"), "routing_run_ids": x.get("routing_run_ids"), "edge_cost_hashes": x.get("edge_cost_hashes"),
                              "vehicle_hours": (x.get("metrics") or {}).get(key), "teleports": len((x.get("metrics") or {}).get("teleport_events") or [])} for a, x in (r.get("arms") or {}).items()},
                 **{k: v for k, v in (r.get("quality_vs_outcome") or {}).items()}} for r in rep.get("per_seed", [])]
    return {"available": True, "result_source": "RESEARCH_BENCHMARK", "report": prov["report"], "seed_set": rep.get("seed_set"), "seeds": rep.get("seeds"), "verdict": rep.get("verdict"), "outcome": rep.get("outcome"),
            "primary_metric": P.get("primary_metric"), "learned_vs_baseline": head("learned_predictive_vs_baseline"), "learned_vs_reactive": head("learned_predictive_vs_reactive"),
            "learned_vs_persistence": head("learned_predictive_vs_persistence_predictive"), "persistence_vs_baseline": head("persistence_predictive_vs_baseline"), "reactive_vs_baseline": head("reactive_vs_baseline"),
            "oracle_research_only": head("oracle_vs_baseline") if "oracle_vs_baseline" in pairs else None, "paired": pairs, "teleports": rep.get("teleports"),
            "forecast_quality": {k: v for k, v in (rep.get("forecast_quality") or {}).items() if k != "per_seed"}, "per_seed": per_seed, "same_population_all_seeds": rep.get("same_population_all_seeds"),
            "provenance": prov, "protocol": {k: P.get(k) for k in ("protocol_id", "city_id", "dataset", "model", "model_label", "checkpoint", "checkpoint_sha256", "held_out_skill", "mapping_counts", "coverage_hops", "min_saving_s", "min_saving_pct",
                                                                  "demand_method", "calibration_method", "simulation_duration_s", "routing_round_s", "round_horizons_min", "compliance", "forecast_moments", "sumo_version", "dev_seeds", "final_seeds", "primary_metric", "model_selection_rule")},
            "generated_utc": rep.get("generated_utc")}


@router.get("/api/experiment/chain", tags=["experiment"])
def experiment_chain(tag: str = "_ideal", run_id: str | None = None):
    """A chain experiment that HAS run — the newest of `tag`, or the run you name.

    This endpoint only reads; POST /api/experiment/chain/run executes a new one.
    """
    ic = _chain_module()
    f = (ic.RUNS / run_id / "run.json") if run_id else \
        (config.REPO / f"results/routing/integrated_chain{tag}.json")
    if not f.exists():
        return {"available": False,
                "missing": str(f.relative_to(config.REPO)),
                "run_it": "POST /api/experiment/chain/run",
                "command": "python -m core.simulation.closed_loop.protocols.chains.integrated_chain --seeds 11,12,13,14,15"}
    rec = json.loads(f.read_text())
    kind = str(((rec.get("options") or rec.get("request") or {}).get("forecast_kind")) or rec.get("forecast_kind") or "").lower()
    src = "SYNTHETIC_WHAT_IF" if kind in ("random", "oracle") else "RESEARCH_BENCHMARK"
    return {"available": True, "result_source": src, **rec}


_CHAIN_LOCK = threading.Lock()


_CHAIN_ACTIVE: dict[str, dict] = {}


def _chain_module():
    import sys
    sys.path.insert(0, str(config.REPO))
    from core.simulation.closed_loop.protocols.chains import integrated_chain
    return integrated_chain


@router.post("/api/experiment/chain/run", tags=["experiment"])
def experiment_chain_run(payload: dict | None = None):
    """Execute the whole chain now: forecast -> future edge costs -> routing -> SUMO -> metrics.

    Body (all optional): seeds, horizon, horizon_min, compliance, v2x, source, as_of, levels, tag.
    Returns a run_id straight away — SUMO takes minutes, so the run is done on a worker thread and
    polled through /api/experiment/chain/run/{run_id}.
    """
    ic = _chain_module()
    opts = {k: v for k, v in (payload or {}).items()
            if k in ic.DEFAULTS or k in ("run_id",)}
    run_id = ic.new_run_id(str(opts.get("tag") or ""))
    opts["run_id"] = run_id

    with _CHAIN_LOCK:
        busy = [r for r, st in _CHAIN_ACTIVE.items() if st.get("status") == "running"]
        if busy:
            return {"started": False, "reason": "a chain run is already in flight on this server",
                    "running": busy}
        _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "running", "stage": "starting"}

    def _work():
        try:
            rec = ic.run_chain(**opts)
            with _CHAIN_LOCK:
                _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "done",
                                         "summary": rec["summary"]}
        except BaseException as exc:                    # noqa: BLE001 - reported, never swallowed
            with _CHAIN_LOCK:
                _CHAIN_ACTIVE[run_id] = {"run_id": run_id, "status": "failed",
                                         "error": f"{type(exc).__name__}: {exc}"}
            (ic.RUNS / run_id).mkdir(parents=True, exist_ok=True)
            (ic.RUNS / run_id / "status.json").write_text(json.dumps(
                {"run_id": run_id, "status": "failed",
                 "error": f"{type(exc).__name__}: {exc}"}, indent=1))

    threading.Thread(target=_work, name=f"chain-{run_id}", daemon=True).start()
    return {"started": True, "run_id": run_id, "config": opts,
            "poll": f"/api/experiment/chain/run/{run_id}",
            "note": ("this is a real execution: a model forecast, a duarouter re-route on its "
                     "output and three SUMO runs. Metrics appear only when they are measured.")}


@router.get("/api/experiment/chain/runs", tags=["experiment"])
def experiment_chain_runs(limit: int = 20):
    """Every chain execution this repository holds, newest first."""
    ic = _chain_module()
    out = []
    if ic.RUNS.exists():
        for d in sorted((x for x in ic.RUNS.iterdir() if x.is_dir()), reverse=True)[:limit]:
            rec = _read_json(d / "status.json") or {"run_id": d.name, "status": "unknown"}
            out.append({"run_id": d.name, "status": rec.get("status"),
                        "stage": rec.get("stage"), "started_utc": rec.get("started_utc"),
                        "arms_done": rec.get("arms_done"), "arms_total": rec.get("arms_total"),
                        "finished": (d / "run.json").exists()})
    return {"runs": out, "dir": (str(ic.RUNS.relative_to(config.REPO))
                                 if ic.RUNS.is_relative_to(config.REPO) else str(ic.RUNS))}


@router.get("/api/experiment/chain/run/{run_id}", tags=["experiment"])
def experiment_chain_status(run_id: str):
    """What THIS execution measured. While it runs, the stage and the arms already finished."""
    ic = _chain_module()
    d = ic.RUNS / run_id
    if ".." in run_id or "/" in run_id or not d.is_dir():
        return {"found": False, "run_id": run_id}
    st = _read_json(d / "status.json") or {}
    done = d / "run.json"
    result = _read_json(done) if done.exists() else None
    with _CHAIN_LOCK:
        live = _CHAIN_ACTIVE.get(run_id, {})
    return {"found": True, "run_id": run_id, "status": live.get("status", st.get("status")),
            "stage": st.get("stage"), "arms_done": st.get("arms_done"),
            "arms_total": st.get("arms_total"), "error": live.get("error") or st.get("error"),
            "config": st.get("config"), "command": st.get("command"),
            "result": result}
