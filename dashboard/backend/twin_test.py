"""TEST IN DIGITAL TWIN — the analysed trip, and only that trip, becomes the SUMO scenario.

    POST /api/twin/test {analysis_run_id, gui?}   ->  {simulation_run_id}
    GET  /api/twin/test/{simulation_run_id}

The AnalysisRun (results/runs/provenance/<analysis_run_id>.json, written by Mission Control) is
the single source of truth: city, resolved origin/destination coordinates, departure, requested and
resolved model, checkpoint sha, horizon, raw / post-processed forecast hashes, recommended route,
route geometry hash, dataset and graph hashes. Nothing is taken from the page a second time.

From it:
    network        Dhaka -> the calibrated dhaka_r1 twin; any other city -> an OSM scenario built by
                   pipeline/city/sumo_scenario around THIS origin/destination (cached by its bbox)
    O/D -> edges   the resolved coordinates are snapped to the nearest passenger edges (sumolib);
                   no edge within NEAR_M -> SUMO_OD_MAPPING_FAILED, never a substitute trip
    probe vehicle  one controlled vehicle for exactly that trip in every arm (baseline / reactive /
                   prediction-aware when a validated corridor forecast prices the network)
    seed           generated at run time from the analysis run id, recorded in provenance
    result         the probe's measured travel time per arm + network metrics, labelled
                   SIMULATED COUNTERFACTUAL (single seed; paired-seed CI lives under Research)

A simulation provenance record (sim_<id>) links back to the analysis run id, and the analysis run
lists its simulations.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config
import provenance as pv

sys.path.insert(0, str(config.REPO))
NEAR_M = 300.0
MARGIN_DEG = 0.015                                   # ~1.5 km around the trip's bounding box
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


class ODMappingFailed(RuntimeError):
    pass


class AnalysisRunNotFound(KeyError):
    pass


def _set(job: str, **kw) -> None:
    with _LOCK:
        _JOBS[job].update(kw)
        rec = _JOBS[job].get("_prov")
        if rec is not None:
            rec.set(**{k: v for k, v in kw.items() if k in ("stage", "network_id", "network_hash", "network_edges", "origin_edge", "destination_edge",
                                                          "probe_vehicle_id", "seed", "arms", "status", "error")})


def load_analysis(analysis_run_id: str) -> dict:
    rec = pv.load(analysis_run_id)
    if not rec or rec.get("status") != "done" or not rec.get("origin_resolved"):
        raise AnalysisRunNotFound(analysis_run_id)
    return rec


def is_dhaka_run(rec: dict) -> bool:
    o = rec["origin_resolved"]; d = rec["destination_resolved"]
    inside = lambda p: 23.60 <= p["lat"] <= 24.00 and 90.25 <= p["lng"] <= 90.55
    return str(rec.get("city", "")).lower().startswith("dhaka") or (inside(o) and inside(d))


def scenario_for(rec: dict, emit) -> dict:
    """The SUMO network this analysis runs on. Dhaka: the calibrated twin. Elsewhere: an OSM scenario
    built around the analysed trip (its own bbox), cached by that bbox."""
    from live_sim import networks, resolve_network
    if is_dhaka_run(rec):
        n = next(x for x in networks() if x["id"] == "dhaka_r1")
        return {**n, **resolve_network("dhaka_r1"), "demand_reality": n.get("demand"), "forecast_capable": True}
    o, d = rec["origin_resolved"], rec["destination_resolved"]
    s, n_ = min(o["lat"], d["lat"]) - MARGIN_DEG, max(o["lat"], d["lat"]) + MARGIN_DEG
    w, e = min(o["lng"], d["lng"]) - MARGIN_DEG, max(o["lng"], d["lng"]) + MARGIN_DEG
    bbox = (round(s, 4), round(w, 4), round(n_, 4), round(e, 4))
    key = hashlib.sha256(json.dumps(bbox).encode()).hexdigest()[:8]
    city_id = re.sub(r"[^a-z0-9]+", "_", str(rec.get("city", "city")).lower()).strip("_")[:24] + f"_{key}"
    from pipeline.city.registry import registry
    from pipeline.city import sumo_scenario
    if not registry.get(city_id):
        registry.create_from_bbox(f"{rec.get('city', 'city')} — {o.get('label', '')} → {d.get('label', '')}", bbox, city_id=city_id)
    man_f = sumo_scenario.scenario_dir(city_id) / "MANIFEST.json"
    if not man_f.exists():
        emit(stage="Preparing network")
        sumo_scenario.build(city_id, seed=11, period=2.0, end=1800)
    n = next((x for x in networks() if x["id"] == city_id), None)
    if not n:
        raise RuntimeError(f"scenario {city_id} was built but is not listed")
    return {**n, **resolve_network(city_id), "demand_reality": n.get("demand"), "forecast_capable": False, "bbox_built": bbox}


def map_od(net_path: str, o: dict, d: dict) -> dict:
    """Resolved coordinates -> the nearest passenger edges. No edge within NEAR_M -> SUMO_OD_MAPPING_FAILED."""
    import sumolib
    net = sumolib.net.readNet(str(net_path))

    def nearest(pt: dict, what: str):
        x, y = net.convertLonLat2XY(pt["lng"], pt["lat"])
        cands = [(dist, e) for e, dist in net.getNeighboringEdges(x, y, NEAR_M) if e.allows("passenger") and e.getFunction() == ""]
        if not cands:
            raise ODMappingFailed(f"SUMO_OD_MAPPING_FAILED: no drivable edge within {NEAR_M:.0f} m of the {what} "
                                  f"({pt.get('label')} at {pt['lat']:.5f}, {pt['lng']:.5f}) on {Path(net_path).name}")
        dist, e = min(cands, key=lambda t: t[0])
        return {"edge": e.getID(), "distance_m": round(float(dist), 1), "street": e.getName() or None, "length_m": round(e.getLength(), 1)}
    return {"origin": nearest(o, "origin"), "destination": nearest(d, "destination")}


def runtime_seed(analysis_run_id: str) -> int:
    """A seed generated now, from the analysis run id — recorded, never a fixed research seed."""
    return 100 + int(hashlib.sha256(analysis_run_id.encode()).hexdigest()[:6], 16) % 900


def forecast_route_for_probe(rec: dict, net: str, origin_edge: str, destination_edge: str, out: Path, seed: int, horizon_min: int) -> tuple[list[str] | None, dict]:
    """Prediction-aware arm on Dhaka: the same forecast-derived weights the chain uses, then
    duarouter for the probe's trip (official router on those weights)."""
    import subprocess
    from pipeline.routing.forecast_to_costs import build_table, fetch_forecast, write_weights
    res = fetch_forecast("dhaka", horizon_min, rec.get("resolved_model") if rec.get("resolved_model") not in (None, "none", "persistence") else None, source="recorded", as_of="latest")
    if not res.get("forecast"):
        return None, {"reason": str((res.get("decision") or {}).get("reason"))}
    table = build_table(res, horizon_min, Path(net))
    weights = write_weights(table, out / "forecast_weights.xml", 0.0, 3600.0)
    trips = out / "probe_trip.xml"; trips.write_text(f'<routes>\n  <trip id="probe" depart="0" from="{origin_edge}" to="{destination_edge}"/>\n</routes>\n')
    alt = out / "probe_route.rou.xml"
    subprocess.run(["duarouter", "--net-file", net, "--route-files", str(trips), "--weight-files", str(weights), "--weight-attribute", "traveltime",
                    "--output-file", str(alt), "--ignore-errors", "--no-warnings", "--no-step-log", "--seed", str(seed)], check=True, capture_output=True)
    m = re.search(r'<route edges="([^"]+)"', alt.read_text())
    return (m.group(1).split() if m else None), {"forecast_hash": pv.sha_json(table["edge_travel_times"]), "model": table["forecast"]["model"],
                                                  "checkpoint": table["forecast"]["checkpoint"], "priced_edges": table["priced_edges"]}


def _run(job: str, analysis_run_id: str, gui: bool) -> None:
    from live_sim import live_sim
    from pipeline.routing import integrated_chain as ic
    sim_id = job
    run = pv.Run(sim_id, analysis_run_id=analysis_run_id, kind="twin_test", result_source="SYNTHETIC_WHAT_IF")
    with _LOCK:
        _JOBS[job]["_prov"] = run
    try:
        rec = load_analysis(analysis_run_id)
        run.set(city=rec.get("city"), origin=rec.get("origin_resolved"), destination=rec.get("destination_resolved"), departure=(rec.get("request") or {}).get("departure_local") or (rec.get("request") or {}).get("departure"),
                requested_model=rec.get("requested_model"), resolved_model=rec.get("resolved_model"), checkpoint_sha256=rec.get("checkpoint_sha256"),
                horizon_min=rec.get("horizon_min"), raw_prediction_hash=rec.get("raw_prediction_hash"), postprocessed_prediction_hash=rec.get("postprocessed_prediction_hash"),
                recommended_route=rec.get("recommended"), route_geometry_hash=rec.get("route_geometry_hash"), dataset_hash=rec.get("dataset_hash"), graph_hash=rec.get("graph_hash"))
        _set(job, stage="Preparing network")
        scen = scenario_for(rec, lambda **k: _set(job, **k))
        net_path = scen["net"]
        _set(job, stage="Loading demand", network_id=scen["id"], network_edges=scen.get("edges"), network_hash=pv.sha_file(net_path, 12),
             demand_reality=scen.get("demand_reality"))
        _set(job, stage="Mapping your trip")
        od = map_od(net_path, rec["origin_resolved"], rec["destination_resolved"])
        seed = runtime_seed(analysis_run_id)
        probe_id = f"probe_{analysis_run_id}"
        _set(job, origin_edge=od["origin"]["edge"], destination_edge=od["destination"]["edge"], od_mapping=od, seed=seed, probe_vehicle_id=probe_id)
        sc = config.REPO / "results/routing/SCALE_CHOICE.json"
        scale = (json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25) if scen["id"] == "dhaka_r1" else 1.0
        arms = ["baseline", "reactive"]
        fc_info: dict = {}
        out = config.REPO / "results/live/twin_tests" / sim_id
        out.mkdir(parents=True, exist_ok=True)
        pa_route = None
        if scen.get("forecast_capable"):
            pa_route, fc_info = forecast_route_for_probe(rec, net_path, od["origin"]["edge"], od["destination"]["edge"], out, seed, int(rec.get("horizon_min") or 15))
            if pa_route:
                arms.append("prediction_aware")
        _set(job, arms=arms, forecast_hash=fc_info.get("forecast_hash"), forecast=fc_info, model=fc_info.get("model") or rec.get("resolved_model"))
        live_sim.owner = job
        for _ in range(120):
            if live_sim.state(with_vehicles=False).get("status") not in ("running", "paused", "starting"):
                break
            time.sleep(0.5)
        else:
            live_sim.stop()
        results = []
        for arm in arms:
            _set(job, stage={"baseline": "Running baseline", "reactive": "Running reactive", "prediction_aware": "Running prediction-aware"}[arm], arm=arm)
            probe = {"id": probe_id, "from_edge": od["origin"]["edge"], "to_edge": od["destination"]["edge"], "depart_s": 60}
            if arm == "prediction_aware":
                probe["route_edges"] = pa_route
            r = live_sim.start({"network": scen["id"], "seed": seed, "arm": arm if arm != "prediction_aware" else "baseline",
                                "duration_s": 1500, "scale": scale, "compliance": 0.3, "step_delay_ms": 0, "continuous": False,
                                "levels": "observed" if scen["id"] == "dhaka_r1" else "", "gui": gui, "probe": probe}, owner=job)
            if not r.get("started"):
                raise RuntimeError(r.get("reason", "could not start the twin"))
            for _ in range(3600):
                s = live_sim.state(with_vehicles=False)
                if s["status"] in ("done", "failed", "stopped"):
                    break
                time.sleep(0.5)
            if s["status"] != "done":
                raise RuntimeError(s.get("message") or f"run ended as {s['status']}")
            res = s["result"]
            results.append({"arm": arm, "seed": seed, "run_id": res["run_id"], "metrics": res["metrics"], "probe": s.get("probe"),
                            "routing_policy": {"baseline": "no rerouting", "reactive": "rerouteTraveltime on current travel times (30 % equipped + the probe)",
                                               "prediction_aware": "probe routed by duarouter on forecast-derived edge costs"}[arm],
                            "routes_changed": res.get("reroutes", 0), "advisories_delivered": 0})
        _set(job, stage="Computing result")
        summary = ic.summarise([{k: v for k, v in x.items() if k != "probe"} for x in results]) if len(results) >= 2 else {}
        probe_tt = {x["arm"]: (x.get("probe") or {}).get("travel_time_s") for x in results}
        base = probe_tt.get("baseline")
        probe_cmp = {a: (None if base is None or tt is None or base == 0 else round(100 * (tt - base) / base, 1)) for a, tt in probe_tt.items()}
        result = {"simulation_run_id": sim_id, "analysis_run_id": analysis_run_id, "network": scen["id"], "network_edges": scen.get("edges"),
                  "demand_reality": scen.get("demand_reality"), "seed": seed, "seed_source": "generated at run time from the analysis run id",
                  "od_mapping": od, "probe_vehicle_id": probe_id, "arms": results, "summary": summary,
                  "probe_travel_time_s": probe_tt, "probe_vs_baseline_pct": probe_cmp, "forecast": fc_info,
                  "label": "SIMULATED COUNTERFACTUAL — microscopic simulated vehicles in SUMO on this network; not a real-road measured outcome; single runtime seed (paired seeds under Research)",
                  "finished_utc": datetime.now(timezone.utc).isoformat()}
        run.set(status="done", probe={a: x.get("probe") for a, x in zip([x["arm"] for x in results], results)}, probe_travel_time_s=probe_tt, sumo_runs=[x["run_id"] for x in results],
                sumo_metrics={x["arm"]: x["metrics"] for x in results})
        run.finish("done")
        _link_analysis(analysis_run_id, sim_id)
        _set(job, status="done", stage="done", result=result)
    except AnalysisRunNotFound as exc:
        run.finish("failed", "ANALYSIS_RUN_NOT_FOUND"); _set(job, status="failed", stage="failed", error=f"ANALYSIS_RUN_NOT_FOUND: {exc}")
    except ODMappingFailed as exc:
        run.finish("failed", str(exc)); _set(job, status="failed", stage="failed", error=str(exc))
    except Exception as exc:                            # noqa: BLE001 - shown on the page, never replaced by a stored result
        run.finish("failed", f"{type(exc).__name__}: {exc}"); _set(job, status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")
    finally:
        live_sim.owner = None
        with _LOCK:
            _JOBS[job].pop("_prov", None)


def _link_analysis(analysis_run_id: str, sim_id: str) -> None:
    rec = pv.load(analysis_run_id)
    if rec:
        rec.setdefault("simulation_run_ids", []).append(sim_id)
        pv.save(rec)


def start(payload: dict) -> dict:
    analysis_run_id = str((payload or {}).get("analysis_run_id") or "").strip()
    if not analysis_run_id:
        return {"started": False, "error": "ANALYSIS_RUN_NOT_FOUND: analysis_run_id is required"}
    try:
        load_analysis(analysis_run_id)
    except AnalysisRunNotFound:
        return {"started": False, "error": f"ANALYSIS_RUN_NOT_FOUND: {analysis_run_id}", "http": 404}
    with _LOCK:
        busy = [j for j, st in _JOBS.items() if st.get("status") == "running"]
        if busy:
            return {"started": False, "error": f"a digital-twin test is already running ({busy[0]})"}
        job = "sim_" + uuid.uuid4().hex[:8]
        _JOBS[job] = {"simulation_run_id": job, "analysis_run_id": analysis_run_id, "status": "running", "stage": "Preparing network",
                      "started_utc": datetime.now(timezone.utc).isoformat()}
    threading.Thread(target=_run, args=(job, analysis_run_id, bool((payload or {}).get("gui"))), name=job, daemon=True).start()
    return {"started": True, "simulation_run_id": job, "analysis_run_id": analysis_run_id, "poll": f"/api/twin/test/{job}"}


def status(job: str) -> dict:
    with _LOCK:
        st = _JOBS.get(job)
        if st is None:
            rec = pv.load(job)
            return {"simulation_run_id": job, "status": rec.get("status", "unknown") if rec else "unknown", "provenance": rec} if rec else {"simulation_run_id": job, "status": "unknown"}
        return {k: v for k, v in st.items() if k != "_prov"}
