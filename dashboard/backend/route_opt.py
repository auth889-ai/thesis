"""ROUTE OPTIMIZATION for one AnalysisRun — the production entry to pipeline/routing.

The AnalysisRun is the only input: its stored raw prediction (verified against the run's
raw_prediction_hash), its resolved model, its horizon and its SUMO O/D edges. The forecast becomes
continuous future edge costs (pipeline/routing/edge_costs.py), SUMO's duarouter returns the
candidates, and the admission layer (pipeline/routing/route_optimizer.py) selects among them. The
result is a RoutingRun `rt_<id>` in provenance, linked both ways to the analysis, and is what the
Digital Twin's prediction-aware arm drives — nothing is recomputed with another model or window.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import config
import provenance as pv

sys.path.insert(0, str(config.REPO))


class NoStoredForecast(RuntimeError):
    pass


def _forecast_from_analysis(rec: dict, horizon_min: int) -> tuple[dict[str, float], str]:
    raw = rec.get("raw_prediction")
    if not raw:
        raise NoStoredForecast("ANALYSIS_RUN_HAS_NO_STORED_FORECAST: this analysis was recorded before forecasts were kept with the run; "
                               "run the analysis again")
    check = pv.sha_json(raw)
    if rec.get("raw_prediction_hash") and check != rec["raw_prediction_hash"]:
        raise NoStoredForecast(f"stored forecast hash {check} does not match the run's raw_prediction_hash {rec['raw_prediction_hash']}")
    vals = raw.get(str(horizon_min)) or raw.get(horizon_min)
    if not vals:
        raise NoStoredForecast(f"no forecast at horizon {horizon_min} min in this analysis (have {sorted(raw)})")
    return {k: v for k, v in vals.items() if v is not None}, rec.get("forecast_unit") or "congestion_level_0_3"


def optimize_for_analysis(rec: dict, net: str | Path, origin_edge: str, destination_edge: str, out: Path, seed: int,
                          window_s: float = 1800.0, current_route: list[str] | None = None, hops: int | None = None) -> dict:
    """One RoutingRun for the analysed trip. Raises NoStoredForecast when the run carries no forecast."""
    from pipeline.routing import edge_costs as ec, route_optimizer as ro
    from pipeline.routing.forecast_to_costs import corridor_records
    analysis_run_id = rec["run_id"]
    horizon_min = int(rec.get("horizon_min") or 15)
    rt_id = "rt_" + uuid.uuid4().hex[:8]
    run = pv.Run(rt_id, kind="routing", analysis_run_id=analysis_run_id, result_source="LIVE_COMPUTATION",
                 requested_model=rec.get("requested_model"), resolved_model=rec.get("resolved_model"), checkpoint_path=rec.get("checkpoint_path"),
                 horizon_min=horizon_min, raw_prediction_hash=rec.get("raw_prediction_hash"), origin_edge=origin_edge, destination_edge=destination_edge)
    try:
        run.stage("Pricing edges from the forecast")
        values, unit = _forecast_from_analysis(rec, horizon_min)
        cfg = ec.load_config()
        table = ec.build(values, unit, corridor_records(), Path(net), horizon_min, cfg, hops, rec.get("resolved_model"), analysis_run_id)
        run.set(future_cost_hash=table["future_cost_hash"], raw_forecast_hash=table["raw_forecast_hash"], priced_edges=table["priced_edges"],
                direct_edges=table["direct_edges"], derived_edges=table["derived_edges"], coverage_hops=table["coverage_hops"],
                corridor_ratio=table["corridor_ratio"], config_hash=cfg["_config_hash"], config_file=cfg["_config_file"], config=cfg)
        run.stage("Requesting route candidates from SUMO")
        trips = [{"id": f"probe_{analysis_run_id}", "from": origin_edge, "to": destination_edge, "depart": 0.0, "current_route": current_route}]
        out.mkdir(parents=True, exist_ok=True)
        (out / "edge_costs.json").write_text(__import__("json").dumps({k: v for k, v in table.items() if k != "config"}, indent=1))
        rr = ro.optimize(Path(net), trips, table, out, seed, window_s, cfg)
        run.stage("Selecting among candidates")
        d = rr["decisions"][0]
        sel = next((c for c in d["candidates"] if c["route_id"] == d["selected"]), None)
        run.set(generator=rr["generator"], candidates=d["candidates"], candidates_requested=d["candidates_requested"], candidates_real=d["candidates_real"],
                decision=d["decision"], selected_route_id=d["selected"], selected_route=sel["edges"] if sel else None,
                current_future_cost_s=d.get("current_future_cost_s"), alternative_future_cost_s=d.get("alternative_future_cost_s"),
                predicted_saving_s=d.get("predicted_saving_s"), predicted_saving_pct=d.get("predicted_saving_pct"),
                threshold_s=d.get("threshold_s"), threshold_pct=d.get("threshold_pct"), admission=rr["stats"],
                selected_routes_hash=rr["selected_routes_hash"], candidate_costs_hash=rr["candidate_costs_hash"], seed=seed, window_s=window_s)
        run.finish("done")
        _link(analysis_run_id, rt_id)
        return run.rec
    except Exception as exc:                                  # noqa: BLE001
        run.finish("failed", f"{type(exc).__name__}: {exc}")
        raise


def find_existing(rec: dict, origin_edge: str, destination_edge: str, seed: int) -> dict | None:
    """The most recent finished RoutingRun of this analysis for the same O/D edges and seed — the
    same stored forecast and the same deterministic duarouter calls, so it is reused, not redone."""
    for rt_id in reversed(rec.get("routing_run_ids") or []):
        rt = pv.load(rt_id)
        if rt and rt.get("status") == "done" and rt.get("origin_edge") == origin_edge and rt.get("destination_edge") == destination_edge \
                and rt.get("seed") == seed and rt.get("raw_prediction_hash") == rec.get("raw_prediction_hash"):
            return rt
    return None


def _link(analysis_run_id: str, rt_id: str) -> None:
    rec = pv.load(analysis_run_id)
    if rec:
        rec.setdefault("routing_run_ids", []).append(rt_id)
        pv.save(rec)


def public(rt: dict) -> dict:
    """What the page and the twin get: the decision with its terms, never the whole config."""
    keys = ("run_id", "analysis_run_id", "resolved_model", "horizon_min", "raw_prediction_hash", "future_cost_hash", "priced_edges", "direct_edges",
            "derived_edges", "coverage_hops", "candidates_requested", "candidates_real", "decision", "selected_route_id", "selected_route",
            "current_future_cost_s", "alternative_future_cost_s", "predicted_saving_s", "predicted_saving_pct", "threshold_s", "threshold_pct",
            "admission", "config_hash", "config_file", "origin_edge", "destination_edge", "seed", "status", "error")
    out = {k: rt.get(k) for k in keys}
    out["candidates"] = [{k: v for k, v in c.items() if k != "edges"} | {"n_edges": len(c.get("edges") or []), "first_edge": (c.get("edges") or [None])[0],
                                                                        "last_edge": (c.get("edges") or [None])[-1]} for c in (rt.get("candidates") or [])]
    return out
