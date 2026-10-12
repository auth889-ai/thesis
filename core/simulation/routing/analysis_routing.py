"""ROUTE OPTIMIZATION for one AnalysisRun — the production entry to src/pipeline/routing.

The AnalysisRun is the only input: its stored raw prediction (verified against the run's
raw_prediction_hash), its resolved model, its horizon and its SUMO O/D edges. The forecast becomes
continuous future edge costs (src/pipeline/routing/edge_costs.py), SUMO's duarouter returns the
candidates, and the admission layer (src/pipeline/routing/route_optimizer.py) selects among them. The
result is a RoutingRun `rt_<id>` in provenance, linked both ways to the analysis, and is what the
Digital Twin's prediction-aware arm drives — nothing is recomputed with another model or window.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from core.common import evidence_paths as config
from core.common.data import provenance as pv

sys.path.insert(0, str(config.REPO))


class NoStoredForecast(RuntimeError):
    pass


def _forecast_from_analysis(rec: dict, horizon_min: int) -> tuple[dict[str, float], str]:
    raw = rec.get("raw_prediction")
    if not raw:
        raise NoStoredForecast("ANALYSIS_RUN_HAS_NO_STORED_FORECAST: this analysis was recorded before forecasts were kept with the run; "
                               "run the analysis again")
    check = pv.sha_json(raw)
    # Dhaka runs hash the same per-horizon dict; dataset runs hash the model's raw array (the dict is its
    # rounded projection), so the dict hash is verified only where it is the recorded hash
    if rec.get("raw_prediction_hash") and not rec.get("dataset_scope") and check != rec["raw_prediction_hash"]:
        raise NoStoredForecast(f"stored forecast hash {check} does not match the run's raw_prediction_hash {rec['raw_prediction_hash']}")
    vals = raw.get(str(horizon_min)) or raw.get(horizon_min)
    if not vals:
        raise NoStoredForecast(f"no forecast at horizon {horizon_min} min in this analysis (have {sorted(raw)})")
    return {k: v for k, v in vals.items() if v is not None}, rec.get("forecast_unit") or "congestion_level_0_3"


def optimize_for_analysis(rec: dict, net: str | Path, origin_edge: str, destination_edge: str, out: Path, seed: int,
                          window_s: float = 1800.0, current_route: list[str] | None = None, hops: int | None = None) -> dict:
    """One RoutingRun for the analysed trip. Raises NoStoredForecast when the run carries no forecast."""
    from core.simulation.routing import edge_costs as ec, route_optimizer as ro
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
        cmap, free_speed, facts = corridor_map_for(rec)
        values, unit = to_mps(values, unit)
        table = ec.build(values, unit, cmap, Path(net), horizon_min, cfg, hops, rec.get("resolved_model"), analysis_run_id, corridor_free_speed=free_speed)
        run.set(future_cost_hash=table["future_cost_hash"], raw_forecast_hash=table["raw_forecast_hash"], priced_edges=table["priced_edges"],
                direct_edges=table["direct_edges"], derived_edges=table["derived_edges"], coverage_hops=table["coverage_hops"],
                corridor_ratio=table["corridor_ratio"], config_hash=cfg["_config_hash"], config_file=cfg["_config_file"], config=cfg,
                forecast_unit=unit, corridor_source=facts.get("_source"), direct_edge_table=direct_edge_table(rec, table, facts))
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
                selected_routes_hash=rr["selected_routes_hash"], candidate_costs_hash=rr["candidate_costs_hash"], seed=seed, window_s=window_s,
                selected_route_hash=pv.sha_json(sel["edges"]) if sel else None, checkpoint_sha256=rec.get("checkpoint_sha256"),
                decision_reason=(f"{d['decision']}: predicted saving {d.get('predicted_saving_s')} s ({d.get('predicted_saving_pct')} %) against a threshold of {d.get('threshold_s')} s and {d.get('threshold_pct')} %"
                                 if d.get("predicted_saving_s") is not None else d["decision"]))
        run.finish("done")
        _link(analysis_run_id, rt_id)
        return run.rec
    except Exception as exc:                                  # noqa: BLE001
        run.finish("failed", f"{type(exc).__name__}: {exc}")
        raise


def corridor_map_for(rec: dict) -> tuple[dict, dict | None, dict]:
    """Which SUMO edges each forecast node covers. Dhaka: the project's corridor-to-edge map. An
    uploaded dataset: the genuine detector -> edge mapping of the scenario linked to that dataset
    (src/pipeline/city/sensor_map.py). Never a guess."""
    scope = rec.get("dataset_scope") or (rec.get("city") if str(rec.get("city", "")).startswith("user:") else None)
    if scope:
        from core.simulation.twin import sensor_map
        mapping = sensor_map.find_for_dataset(scope)
        if not mapping:
            raise NoStoredForecast(f"NO_SENSOR_MAPPING: no genuine detector -> SUMO edge mapping exists for {scope}; build the scenario and run src/pipeline/city/sensor_map.py")
        cmap, free, facts = sensor_map.corridor_map(mapping)
        facts["_source"] = {"file": mapping.get("file"), "file_hash": mapping.get("file_hash"), "upstream": mapping.get("source"), "counts": mapping.get("counts"),
                            "network": mapping.get("network"), "network_hash": mapping.get("network_hash")}
        return cmap, free, facts
    from core.simulation.routing.forecast_costs import corridor_records
    return corridor_records(), None, {"_source": {"file": "data/forecasting/live_dhaka/corridor_edges.json"}}


def to_mps(values: dict, unit: str | None) -> tuple[dict, str]:
    """A speed forecast reaches the cost builder in m/s; a congestion class passes through."""
    u = (unit or "").lower()
    if u.startswith("congestion_level"):
        return values, unit
    if "km/h" in u or "kmh" in u:
        return {k: (v / 3.6 if v is not None else None) for k, v in values.items()}, "speed_mps"
    if "mph" in u:
        return {k: (v * 0.44704 if v is not None else None) for k, v in values.items()}, "speed_mps"
    if "m/s" in u or "mps" in u:
        return values, "speed_mps"
    return values, unit or "unknown"


def direct_edge_table(rec: dict, table: dict, facts: dict) -> list[dict]:
    """Per DIRECT edge: detector, its predicted speeds at +15/+30/+60, the edge, its length and the
    future travel time the routing prices — the audit row the supervisor asked for."""
    raw = rec.get("raw_prediction") or {}
    unit = (rec.get("forecast_unit") or "").lower()
    k = 1 / 3.6 if "km/h" in unit else 0.44704 if "mph" in unit else 1.0
    rows = []
    for eid, row in (table.get("edges") or {}).items():
        if row.get("source") != "DIRECT":
            continue
        node = row.get("corridor"); f = facts.get(node) or {}
        sp = {h: (raw.get(h) or {}).get(node) for h in ("15", "30", "60")}
        rows.append({"sensor_id": f.get("sensor_id"), "node": node, "predicted_speed_15_mps": None if sp["15"] is None else round(sp["15"] * k, 3),
                     "predicted_speed_30_mps": None if sp["30"] is None else round(sp["30"] * k, 3), "predicted_speed_60_mps": None if sp["60"] is None else round(sp["60"] * k, 3),
                     "sumo_edge_id": eid, "edge_length_m": row.get("length_m"), "speed_limit_mps": row.get("speed_limit_mps"), "bounded_speed_mps": row.get("bounded_speed_mps"),
                     "future_travel_time_s": row.get("future_tt_s"), "horizon_min_priced": table.get("horizon_min"), "mapping_quality": f.get("quality"), "snap_m": f.get("snap_m")})
    return rows


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
    keys = ("run_id", "analysis_run_id", "resolved_model", "checkpoint_sha256", "horizon_min", "raw_prediction_hash", "future_cost_hash", "selected_route_hash", "decision_reason", "priced_edges", "direct_edges",
            "derived_edges", "coverage_hops", "candidates_requested", "candidates_real", "decision", "selected_route_id", "selected_route",
            "current_future_cost_s", "alternative_future_cost_s", "predicted_saving_s", "predicted_saving_pct", "threshold_s", "threshold_pct",
            "admission", "config_hash", "config_file", "origin_edge", "destination_edge", "seed", "status", "error")
    out = {k: rt.get(k) for k in keys}
    out["candidates"] = [{k: v for k, v in c.items() if k != "edges"} | {"n_edges": len(c.get("edges") or []), "first_edge": (c.get("edges") or [None])[0],
                                                                        "last_edge": (c.get("edges") or [None])[-1]} for c in (rt.get("candidates") or [])]
    return out
