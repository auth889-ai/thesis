"""TEST IN DIGITAL TWIN — the analysed trip, and only that trip, becomes the SUMO scenario.

    POST /api/twin/test {analysis_run_id, gui?}   ->  {simulation_run_id}
    GET  /api/twin/test/{simulation_run_id}

The AnalysisRun (results/runs/provenance/<analysis_run_id>.json, written by Mission Control) is
the single source of truth: city, resolved origin/destination coordinates, departure, requested and
resolved model, checkpoint sha, horizon, raw / post-processed forecast hashes, recommended route,
route geometry hash, dataset and graph hashes. Nothing is taken from the page a second time.

From it:
    network        Dhaka -> the frozen dhaka_r1 twin (its validation status is recorded); any other city -> an OSM scenario built by
                   src/pipeline/city/sumo_scenario around THIS origin/destination (cached by its bbox)
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
import math
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app import config
from traffictwin.data import provenance as pv

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
    """The SUMO network this analysis runs on. Dhaka: the frozen twin with recorded validation state. Elsewhere: an OSM scenario
    built around the analysed trip (its own bbox), cached by that bbox."""
    from backend.app.simulation.runtime import networks, resolve_network
    if is_dhaka_run(rec):
        n = next(x for x in networks() if x["id"] == "dhaka_r1")
        return {**n, **resolve_network("dhaka_r1"), "demand_reality": n.get("demand"), "forecast_capable": True}
    scope = rec.get("dataset_scope") or (rec.get("city") if str(rec.get("city", "")).startswith("user:") else None)
    if scope:                                          # an uploaded dataset with a genuine detector -> edge mapping on a built scenario
        from pipeline.city import sensor_map
        mapping = sensor_map.find_for_dataset(scope)
        if mapping:
            n = next((x for x in networks() if x["id"] == mapping["city_id"]), None)
            if n:
                return {**n, **resolve_network(mapping["city_id"]), "demand_reality": n.get("demand"), "forecast_capable": True,
                        "sensor_mapping": {"file": mapping.get("file"), "counts": mapping.get("counts")}}
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


def optimized_route_for_probe(rec: dict, net: str, origin_edge: str, destination_edge: str, out: Path, seed: int) -> tuple[list[str] | None, dict]:
    """Prediction-aware arm: the RoutingRun for THIS analysis (its stored forecast -> continuous
    edge costs -> duarouter candidates -> admission). Returns the selected route and the public
    routing record; a run without a stored forecast yields no route and a visible reason."""
    from backend.app.routing import optimizer as route_opt
    rt = route_opt.find_existing(rec, origin_edge, destination_edge, seed)
    reused = rt is not None
    if rt is None:
        try:
            rt = route_opt.optimize_for_analysis(rec, net, origin_edge, destination_edge, out / "routing", seed, window_s=1800.0)
        except route_opt.NoStoredForecast as exc:
            return None, {"routing_run_id": None, "reason": str(exc)}
    return rt.get("selected_route"), {**route_opt.public(rt), "reused_existing_routing_run": reused}


GEN_VEH_RE = re.compile(r'<vehicle id="([^"]+)"([^>]*)>\s*<route[^>]*edges="([^"]+)"', re.S)
ROUTING_ROUND_S = 900


def read_any_routes(path: Path) -> list[tuple[str, float, list[str]]]:
    """(id, depart, edges) for every vehicle in a SUMO route file, whatever other attributes it has
    (randomTrips/duarouter output carries type and departLane; the calibrated file does not)."""
    import gzip
    txt = gzip.open(path, "rt").read() if str(path).endswith(".gz") else Path(path).read_text()
    out = []
    for vid, attrs, edges in GEN_VEH_RE.findall(txt):
        m = re.search(r'depart="([^"]+)"', attrs)
        out.append((vid, float(m.group(1)) if m else 0.0, edges.split()))
    return out


def rewrite_routes(src: Path, dst: Path, new_routes: dict[str, list[str]]) -> Path:
    """The same route file, with only the optimizer's changed vehicles carrying a new edge list;
    vehicle types, departure attributes and order are untouched, so the demand is identical."""
    txt = Path(src).read_text()
    def sub(m):
        vid = m.group(1)
        if vid in new_routes:
            return m.group(0).replace(m.group(3), " ".join(new_routes[vid]))
        return m.group(0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(GEN_VEH_RE.sub(sub, txt))
    return dst


def oracle_debug_routes(sim_id: str, net: str, demand: Path, baseline_out: Path, out: Path, seed: int, duration_s: int,
                        compliance: float, probe: dict) -> tuple[Path, list[str] | None, dict]:
    """ORACLE / PERFECT-FUTURE DEBUG ARM for any scenario: the measured edge travel times of the
    paired baseline run (same demand, same seed) pushed through the production optimizer in the
    same rounds the oracle gate uses. Not a learned model, never labelled as one."""
    from pipeline.routing import edge_costs as ec, route_optimizer as ro
    from pipeline.routing import predictive_routing as pr
    cfg = ec.load_config()
    edgedata = baseline_out / "edgedata.xml"
    if not edgedata.exists():
        raise RuntimeError(f"the baseline run left no edgedata.xml in {baseline_out}; the oracle debug arm needs it")
    veh = read_any_routes(demand)
    new_routes, rounds, probe_route = {}, [], None
    advised: list[str] = []
    for k in range(int(math.ceil(duration_s / ROUTING_ROUND_S))):
        b, e = k * ROUTING_ROUND_S, min((k + 1) * ROUTING_ROUND_S, duration_s)
        trips = [{"id": v, "from": r[0], "to": r[-1], "depart": d, "current_route": r} for v, d, r in veh if pr.equipped(v, compliance) and b <= d < e]
        if b <= float(probe["depart_s"]) < e:
            trips.append({"id": probe["id"], "from": probe["from_edge"], "to": probe["to_edge"], "depart": float(probe["depart_s"])})
        if not trips:
            continue
        table = ec.oracle_table(edgedata, Path(net), cfg, b, e)
        rdir = out / f"oracle_round_{k}"
        rec = ro.optimize(Path(net), trips, table, rdir, seed, float(ROUTING_ROUND_S), cfg, keep_candidates=False)
        rid = f"rt_oracle_{sim_id[4:]}_r{k}"
        for d in rec["decisions"]:
            sel = rec["selected_routes"].get(d["vehicle"])
            if d["vehicle"] == probe["id"]:
                probe_route = sel; probe_decision = d["decision"]
            elif d["decision"] == "REROUTE" and sel:
                new_routes[d["vehicle"]] = sel; advised.append(d["vehicle"])
        st = rec["stats"]
        rounds.append({"routing_run_id": rid, "round": k, "window_s": [b, e], "future_cost_hash": table["future_cost_hash"], "priced_edges": table["priced_edges"],
                       "vehicles": st["vehicles"], "admitted": st["vehicles_admitted"], "rejected_capacity": st["rejected_by_capacity_gate"],
                       "rejected_share": st["rejected_by_share_gate"], "mean_candidates_real": st["mean_candidates_real"]})
        (rdir / "routing_run.json").write_text(json.dumps({"routing_run_id": rid, "simulation_run_id": sim_id, "seed": seed, "round": k, "window_s": [b, e],
                                                            "future_cost_hash": table["future_cost_hash"], "stats": st, "config_hash": cfg["_config_hash"],
                                                            "label": "ORACLE / PERFECT-FUTURE DEBUG ARM — measured future of the paired baseline, not a learned model"}, indent=1))
    merged = rewrite_routes(demand, out / f"demand_oracle_{sim_id}.rou.xml", new_routes)
    info = {"label": "ORACLE / PERFECT-FUTURE DEBUG ARM", "not_ai": True, "routing_run_ids": [r["routing_run_id"] for r in rounds], "rounds": rounds,
            "routes_changed": len(new_routes), "advised_ids": advised, "config_hash": cfg["_config_hash"], "routes_file": str(merged),
            "probe_decision": locals().get("probe_decision"), "source": "measured edge travel times of the paired baseline run (same demand, same seed)"}
    return merged, probe_route, info


def _wait_twin(live_sim, poll_s: float = 0.5, max_s: float = 7200.0):
    n = int(max_s / poll_s)
    for _ in range(n):
        s = live_sim.state(with_vehicles=False)
        if s["status"] in ("done", "failed", "stopped"):
            return s
        time.sleep(poll_s)
    return live_sim.state(with_vehicles=False)


def _run(job: str, analysis_run_id: str, opts: dict) -> None:
    from backend.app.simulation.runtime import live_sim
    from pipeline.routing import integrated_chain as ic
    sim_id = job
    gui = bool(opts.get("gui"))
    run = pv.Run(sim_id, analysis_run_id=analysis_run_id, kind="twin_test", result_source="SYNTHETIC_WHAT_IF", gui=gui)
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
        from backend.app.simulation.runtime import scenario_label
        _set(job, stage="Loading demand", network_id=scen["id"], network_edges=scen.get("edges"), network_hash=pv.sha_file(net_path, 12),
             demand_reality=scen.get("demand_reality"), scenario=scenario_label(scen))
        _set(job, stage="Mapping your trip")
        od = map_od(net_path, rec["origin_resolved"], rec["destination_resolved"])
        seed = runtime_seed(analysis_run_id)
        probe_id = f"USER_PROBE_{analysis_run_id.split('_', 1)[-1]}"
        _set(job, origin_edge=od["origin"]["edge"], destination_edge=od["destination"]["edge"], od_mapping=od, seed=seed, probe_vehicle_id=probe_id)
        sc = config.REPO / "results/routing/SCALE_CHOICE.json"
        base_scale = (json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25) if scen["id"] == "dhaka_r1" else 1.0
        scale = round(base_scale * float(opts.get("demand_scale") or 1.0), 4)
        duration = int(opts.get("duration_s") or 1500)
        arms = [a for a in (opts.get("arms") or ["baseline", "reactive", "prediction_aware"]) if a in ("baseline", "reactive", "prediction_aware")]
        if not arms:
            raise ValueError("arms must be a subset of baseline, reactive, prediction_aware")
        fc_info: dict = {}
        out = config.REPO / "results/live/twin_tests" / sim_id
        out.mkdir(parents=True, exist_ok=True)
        pa_route, pa_routes_file, pa_advised = None, None, []
        pa_label = None
        if "prediction_aware" in arms and scen.get("forecast_capable"):
            _set(job, stage="Optimizing route")
            pa_route, fc_info = optimized_route_for_probe(rec, net_path, od["origin"]["edge"], od["destination"]["edge"], out, seed)
            validated = _validated(rec)
            fc_info = {**fc_info, "validated": validated}
            pa_label = f"PREDICTION-AWARE · Model: {fc_info.get('resolved_model')} · Validated: {'YES' if validated else 'NO'}"
            if not pa_route:
                arms.remove("prediction_aware")
        run.set(routing_run_id=fc_info.get("routing_run_id") or fc_id(fc_info), routing_decision=fc_info.get("decision"), future_cost_hash=fc_info.get("future_cost_hash"),
                # the simulation names the exact model and checkpoint it drives, copied from the analysis it was launched from
                model=rec.get("resolved_model"), checkpoint_sha256=rec.get("checkpoint_sha256"), raw_prediction_hash=rec.get("raw_prediction_hash"),
                selected_route_hash=fc_info.get("selected_route_hash"), validated=fc_info.get("validated"))
        _set(job, arms=arms, routing_run_id=fc_id(fc_info), forecast_hash=fc_info.get("future_cost_hash"), forecast=fc_info,
             model=fc_info.get("resolved_model") or rec.get("resolved_model"), demand_scale=scale, duration_s=duration)
        live_sim.owner = job
        for _ in range(120):
            if live_sim.state(with_vehicles=False).get("status") not in ("running", "paused", "starting"):
                break
            time.sleep(0.5)
        else:
            live_sim.stop()
        results, launches = [], {}
        baseline_out = None
        needs_oracle = "prediction_aware" in arms and not scen.get("forecast_capable")
        run_order = list(arms)
        if needs_oracle and "baseline" not in run_order:
            run_order.insert(0, "baseline")               # the oracle's future is the paired baseline: run it headless first
        headless_only = [a for a in run_order if a not in arms]
        for arm in run_order:
            probe = {"id": probe_id, "from_edge": od["origin"]["edge"], "to_edge": od["destination"]["edge"], "depart_s": 60}
            params = {"network": scen["id"], "seed": seed, "arm": arm if arm != "prediction_aware" else "baseline", "duration_s": duration, "scale": scale,
                      "compliance": 0.3, "step_delay_ms": int(opts.get("step_delay_ms") or 0) if gui and arm in arms else 0, "continuous": False,
                      "levels": "observed" if scen["id"] == "dhaka_r1" else "", "gui": gui and arm in arms, "probe": probe,
                      "simulation_run_id": sim_id, "analysis_run_id": analysis_run_id, "routing_run_id": None}
            policy = {"baseline": "no rerouting", "reactive": "rerouteTraveltime on current travel times (30 % equipped + the probe)"}.get(arm)
            if arm == "prediction_aware":
                if needs_oracle:
                    _set(job, stage="Optimizing routes (oracle debug)")
                    pa_routes_file, pa_route, oracle_info = oracle_debug_routes(sim_id, net_path, Path(scen["routes"]), baseline_out, out, seed, duration, 0.3, probe)
                    pa_advised = oracle_info["advised_ids"]; pa_label = oracle_info["label"]
                    fc_info = {**fc_info, "oracle_debug": {k: v for k, v in oracle_info.items() if k != "advised_ids"}}
                    params.update(arm="prediction_aware", routes_file=str(pa_routes_file), advised_ids=pa_advised, forecast_label=pa_label,
                                  routing_run_id=",".join(oracle_info["routing_run_ids"]))
                    policy = f"{pa_label}: measured future of the paired baseline → production optimizer ({oracle_info['routes_changed']} vehicles + the probe rerouted); NOT a learned model"
                    probe["route_source"] = "production optimizer on the paired baseline's measured edge times (oracle debug)"
                else:
                    # the trained model's routing run drives the probe; the demand file is the scenario's own,
                    # so the arm is recorded as prediction_aware with the model and its validation state
                    params.update(arm="prediction_aware", routes_file=str(scen["routes"]), advised_ids=[], forecast_label=pa_label, routing_run_id=fc_id(fc_info))
                    policy = f"{pa_label}: probe on the route selected by routing run {fc_id(fc_info)} ({fc_info.get('decision')}: forecast future cost + load + overlap, threshold {fc_info.get('threshold_s')} s)"
                    probe["route_source"] = f"production optimizer, routing run {fc_id(fc_info)}"
                if pa_route:
                    probe["route_edges"] = pa_route
            _set(job, stage={"baseline": "Running baseline", "reactive": "Running reactive", "prediction_aware": "Running prediction-aware"}[arm] + (" (headless, for the oracle's future)" if arm in headless_only else ""), arm=arm)
            r = live_sim.start(params, owner=job)
            if not r.get("started"):
                raise RuntimeError(r.get("reason", "could not start the twin"))
            s = _wait_twin(live_sim)
            if s["status"] != "done":
                raise RuntimeError(s.get("message") or f"run ended as {s['status']}")
            res = s["result"]
            if arm == "baseline":
                baseline_out = config.REPO / res["out_dir"]
            launches[arm] = res.get("launch")
            if arm in headless_only:
                continue
            results.append({"arm": arm, "seed": seed, "run_id": res["run_id"], "metrics": res["metrics"], "probe": res.get("probe") or s.get("probe"),
                            "routing_policy": policy, "routing_run_id": params.get("routing_run_id"), "label": pa_label if arm == "prediction_aware" else None,
                            "routes_changed": res.get("routes_changed") or res.get("reroutes", 0), "advisories_delivered": res.get("advised", 0),
                            "teleport_events": res.get("teleport_events") or [], "launch": res.get("launch"), "scenario": res.get("scenario")})
        _set(job, stage="Computing result")
        summary = ic.summarise([{k: v for k, v in x.items() if k not in ("probe", "teleport_events", "launch", "scenario")} for x in results]) if len(results) >= 2 else {}
        probe_tt = {x["arm"]: (x.get("probe") or {}).get("travel_time_s") for x in results}
        base = probe_tt.get("baseline")
        probe_cmp = {a: (None if base is None or tt is None or base == 0 else round(100 * (tt - base) / base, 1)) for a, tt in probe_tt.items()}
        result = {"simulation_run_id": sim_id, "analysis_run_id": analysis_run_id, "network": scen["id"], "network_edges": scen.get("edges"),
                  "demand_reality": scen.get("demand_reality"), "scenario": scenario_label(scen), "seed": seed, "seed_source": "generated at run time from the analysis run id",
                  "demand_scale": scale, "duration_s": duration, "gui": gui,
                  "od_mapping": od, "probe_vehicle_id": probe_id, "arms": results, "summary": summary,
                  "probe_travel_time_s": probe_tt, "probe_vs_baseline_pct": probe_cmp, "forecast": fc_info, "routing_run_id": fc_id(fc_info),
                  "prediction_aware_label": pa_label,
                  "label": "SIMULATED COUNTERFACTUAL — microscopic simulated vehicles in SUMO on this network; not a real-road measured outcome; single runtime seed (paired seeds under Research)",
                  "finished_utc": datetime.now(timezone.utc).isoformat()}
        run.set(status="done", probe={x["arm"]: x.get("probe") for x in results}, probe_travel_time_s=probe_tt, sumo_runs=[x["run_id"] for x in results],
                sumo_metrics={x["arm"]: x["metrics"] for x in results}, launches=launches, arms=arms, prediction_aware_label=pa_label,
                teleports={x["arm"]: len(x.get("teleport_events") or []) for x in results}, probe_vehicle_id=probe_id, seed=seed, demand_scale=scale)
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


def _validated(rec: dict) -> bool:
    """Whether the analysis's resolved model passed the registry's held-out trust gate on this scope."""
    try:
        from backend.app.forecasting import model_registry
        scope = rec.get("dataset_scope") or rec.get("city") or "dhaka"
        e = model_registry.resolve(scope, rec.get("resolved_model"))
        return bool(e.get("trust") == "ROUTING_ELIGIBLE" or e.get("status") == "VALIDATED")
    except Exception:                                   # noqa: BLE001
        return False


def fc_id(fc_info: dict) -> str | None:
    return (fc_info or {}).get("run_id") or (fc_info or {}).get("routing_run_id")


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
    opts = {"gui": bool((payload or {}).get("gui")), "arms": (payload or {}).get("arms"), "demand_scale": (payload or {}).get("demand_scale"),
            "step_delay_ms": (payload or {}).get("step_delay_ms"), "duration_s": (payload or {}).get("duration_s")}
    threading.Thread(target=_run, args=(job, analysis_run_id, opts), name=job, daemon=True).start()
    return {"started": True, "simulation_run_id": job, "analysis_run_id": analysis_run_id, "poll": f"/api/twin/test/{job}"}


def status(job: str) -> dict:
    with _LOCK:
        st = _JOBS.get(job)
        if st is None:
            rec = pv.load(job)
            return {"simulation_run_id": job, "status": rec.get("status", "unknown") if rec else "unknown", "provenance": rec} if rec else {"simulation_run_id": job, "status": "unknown"}
        return {k: v for k, v in st.items() if k != "_prov"}
