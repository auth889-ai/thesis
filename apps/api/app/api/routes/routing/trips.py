"""Operations HTTP endpoints."""
from __future__ import annotations

from traffictwin.common import evidence_paths as config
from traffictwin.data.live_providers import observatory as observatory_mod
from traffictwin.optimization import trip_analysis as analyze
from app.api.deps import _city_bits
from app.api.routes.platform.cities import city
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/operate/cities", tags=["operate"])
def operate_cities():
    """Cities the operations screen offers: Dhaka (observed, forecastable) plus any registered
    city — and any other name typed in is geocoded on the spot."""
    reg, _ = _city_bits()
    out = [{"id": "dhaka", "label": "Dhaka", "forecast": True}]
    watched = set(observatory_mod.observatory.cities())
    for cid in reg.list_ids():
        sp = reg.get(cid)
        if sp and sp.display_name and not analyze.is_dhaka(sp.display_name) and cid in watched:   # only cities with history
            out.append({"id": cid, "label": sp.display_name, "forecast": cid in watched,
                        "steps": observatory_mod.observatory.readiness(cid)["steps_have"] if cid in watched else 0})
    from traffictwin.data import uploads as user_datasets
    for d in user_datasets.datasets():                  # uploaded datasets with road coordinates are operable cities
        if d.get("has_coords"):
            out.append({"id": d["id"], "label": f"{d['name'].split(' —')[0]} (your upload)", "forecast": True, "dataset": True, "steps": d["steps"]})
    return {"cities": out}


@router.get("/api/places", tags=["operate"])
def places_list(city: str = "dhaka", q: str = ""):
    """Place suggestions for the origin / destination inputs, INSIDE the named city (known Dhaka
    places, then OpenStreetMap bounded to the city). Free text and 'lat, lng' also work."""
    if not q and analyze.is_dhaka(city):
        return {"places": analyze.places()}
    return {"places": analyze.suggest(city, q)}


@router.get("/api/operate/models", tags=["operate"])
def operate_models(city: str = "dhaka"):
    """Forecast models that can serve this city right now, with the registry's reasons (flat)."""
    return {"city": city, "models": analyze.models_for_city(city)}


@router.get("/api/registry", tags=["operate"])
def models_registry(scope: str = "dhaka"):
    """THE MODEL REGISTRY for a scope (an uploaded dataset `user:<id>` or a city): grouped
    Recommended / Trained on your city / Pretrained / Research, every entry with the gates it
    passed, and what Automatic resolves to. Read fresh from disk — a finished training job
    appears without a restart."""
    from traffictwin.forecasting.operations import model_registry
    return model_registry.registry(scope)


@router.get("/api/runs", tags=["operate"])
def runs_recent(limit: int = 20):
    """The most recent prediction runs with their provenance (what computed each result)."""
    from traffictwin.data import provenance
    return {"runs": provenance.recent(limit)}


@router.get("/api/runs/{run_id}", tags=["operate"])
def run_provenance(run_id: str):
    """Technical details of one run: requested vs resolved model, checkpoint path + sha256, dataset /
    graph / input-window / raw-prediction / post-processed hashes, measured stage timings, result_source."""
    from traffictwin.data import provenance
    rec = provenance.load(run_id)
    return rec or {"run_id": run_id, "error": "UNAVAILABLE: no provenance record for this run id"}


@router.get("/api/analyze/{job}/provenance", tags=["operate"])
def analyze_provenance(job: str):
    from traffictwin.data import provenance
    rec = provenance.load(job)
    return rec or {"run_id": job, "error": "UNAVAILABLE: no provenance record (job still running, failed before inference, or unknown)"}


@router.post("/api/analyze", tags=["operate"])
def analyze_start(payload: dict):
    """ANALYZE TRAFFIC: origin, destination, departure, horizon -> current, forecast, decision.
    Runs in the background so the page can show each stage as it really happens."""
    return {"job": analyze.start(payload or {}), "poll": "/api/analyze/{job}"}


@router.get("/api/analyze/{job}", tags=["operate"])
def analyze_status(job: str):
    return analyze.status(job)


@router.post("/api/route/optimize", tags=["routing"])
def route_optimize(payload: dict | None = None):
    """ROUTE OPTIMIZATION for one AnalysisRun: its stored forecast -> continuous future edge costs ->
    duarouter candidates -> threshold + capacity admission. Returns the RoutingRun with every
    candidate's cost terms. 404 ANALYSIS_RUN_NOT_FOUND; 422 when the run holds no forecast."""
    from traffictwin.optimization import analysis_routing as route_opt
    from traffictwin.digital_twin.live import trip_comparison as twin_test
    from fastapi.responses import JSONResponse
    payload = payload or {}
    try:
        rec = twin_test.load_analysis(str(payload.get("analysis_run_id") or ""))
    except twin_test.AnalysisRunNotFound as exc:
        return JSONResponse(status_code=404, content={"error": f"ANALYSIS_RUN_NOT_FOUND: {exc}"})
    scen = twin_test.scenario_for(rec, lambda **k: None)
    if payload.get("origin_edge") and payload.get("destination_edge"):
        o_edge, d_edge = payload["origin_edge"], payload["destination_edge"]
    else:
        od = twin_test.map_od(scen["net"], rec["origin_resolved"], rec["destination_resolved"])
        o_edge, d_edge = od["origin"]["edge"], od["destination"]["edge"]
    seed = int(payload.get("seed") or twin_test.runtime_seed(rec["run_id"]))
    out = config.REPO / "results/routing/optimize" / rec["run_id"]
    try:
        rt = route_opt.optimize_for_analysis(rec, scen["net"], o_edge, d_edge, out, seed, float(payload.get("window_s") or 1800),
                                             hops=payload.get("hops"))
    except route_opt.NoStoredForecast as exc:
        return JSONResponse(status_code=422, content={"error": str(exc), "analysis_run_id": rec["run_id"]})
    return route_opt.public(rt)


@router.get("/api/route/optimize/{routing_run_id}", tags=["routing"])
def route_optimize_get(routing_run_id: str):
    from traffictwin.data import provenance as pv
    from traffictwin.optimization import analysis_routing as route_opt
    from fastapi.responses import JSONResponse
    rec = pv.load(routing_run_id)
    if not rec:
        return JSONResponse(status_code=404, content={"error": f"ROUTING_RUN_NOT_FOUND: {routing_run_id}"})
    return route_opt.public(rec)
