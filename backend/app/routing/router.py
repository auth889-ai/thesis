"""Operations HTTP endpoints."""
from __future__ import annotations

from core.common import evidence_paths as config
from core.common.data.live_providers import observatory as observatory_mod
from core.simulation.routing import trip_analysis as analyze
from app.dependencies import _city_bits
from app.data.router import city
from fastapi import APIRouter, Request

router = APIRouter()


_RECORDED: dict[str, list] = {}


def _recorded(city) -> list[dict]:
    """The recorded datasets a city declares, with their sites placed on the city's network. A city that declares
    none costs nothing; one that does has its network read once, and the answer is kept while the app runs."""
    from core.common.data import real_speeds
    from core.simulation.routing import city_router
    if not (city.live and city.live.real_sources and any(s.kind == "recorded" for s in city.live.real_sources)):
        return []
    if city.city_id not in _RECORDED:
        built = city_router.network(city.city_id)
        _RECORDED[city.city_id] = real_speeds.recorded_sources(city.city_id, built[0] if built else None, built[1]["bbox"] if built else None)
    return _RECORDED[city.city_id]


@router.get("/api/operate/cities", tags=["operate"])
def operate_cities():
    """Cities the operations screen offers: the deployment's default city (observed, forecastable) plus any
    registered city — and any other name typed in is geocoded on the spot. `configured` lists every city that
    has a file in config/cities/, with what its config states; an unknown value stays null."""
    from core.common.data import city_config
    problems: dict[str, str] = {}                        # one bad file or one failing store must not take the whole list down (a fresh visitor saw 500 and no city)
    configured, home_id = [], None
    for cid in city_config.list_ids():
        try:
            c = city_config.load(cid)
        except Exception as exc:                          # a config that the schema refuses is reported, not served, and does not hide the others
            problems[cid] = f"{type(exc).__name__}: {str(exc)[:300]}"
            continue
        configured.append({"id": c.city_id, "display_name": c.display_name, "country": c.country, "center": c.center,
                           "bounding_box": list(c.bounding_box.tuple) if c.bounding_box else None, "time_zone": c.time_zone,
                           "default_languages": c.default_languages, "emergency_numbers": c.emergency_numbers,
                           "units": c.units.model_dump() if c.units else None, "plugins": c.plugins,
                           "datasets": [d.model_dump() for d in c.datasets], "default": False,
                           "recorded_sources": _recorded(c), "vehicle_mix": c.vehicle_mix.model_dump() if c.vehicle_mix else None,
                           "routing": {"engine": c.routing.engine, "extract": c.routing.extract, "extract_date": c.routing.extract_date, "credit": c.routing.credit} if c.routing else None})
    try:
        home = city_config.default()
        home_id = home.city_id
        out = [{"id": home.city_id, "label": home.label(), "forecast": True}]
    except Exception as exc:
        problems["default"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        out = []
    if configured and not any(c["id"] == home_id for c in configured):
        home_id = configured[0]["id"]                     # the deployment's default could not be loaded: the first good city stands in, and the problem says so
    for c in configured:
        c["default"] = c["id"] == home_id
    try:
        reg, _ = _city_bits()
        watched = set(observatory_mod.observatory.cities())
        for cid in reg.list_ids():
            sp = reg.get(cid)
            if sp and sp.display_name and not analyze.is_dhaka(sp.display_name) and cid in watched:   # only cities with history
                out.append({"id": cid, "label": sp.display_name, "forecast": cid in watched,
                            "steps": observatory_mod.observatory.readiness(cid)["steps_have"] if cid in watched else 0})
        from core.common.data import uploads as user_datasets
        for d in user_datasets.datasets():                  # uploaded datasets with road coordinates are operable cities
            if d.get("has_coords"):
                out.append({"id": d["id"], "label": f"{d['name'].split(' —')[0]} (your upload)", "forecast": True, "dataset": True, "steps": d["steps"]})
    except Exception as exc:
        problems["registry"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return {"cities": out, "configured": configured, "problems": problems}


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
    from core.ml.forecasting.operations import model_registry
    return model_registry.registry(scope)


@router.get("/api/runs", tags=["operate"])
def runs_recent(limit: int = 20):
    """The most recent prediction runs with their provenance (what computed each result)."""
    from core.common.data import provenance
    return {"runs": provenance.recent(limit)}


@router.get("/api/runs/{run_id}", tags=["operate"])
def run_provenance(run_id: str):
    """Technical details of one run: requested vs resolved model, checkpoint path + sha256, dataset /
    graph / input-window / raw-prediction / post-processed hashes, measured stage timings, result_source."""
    from core.common.data import provenance
    rec = provenance.load(run_id)
    return rec or {"run_id": run_id, "error": "UNAVAILABLE: no provenance record for this run id"}


@router.get("/api/analyze/{job}/provenance", tags=["operate"])
def analyze_provenance(job: str):
    from core.common.data import provenance
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
    from core.simulation.routing import analysis_routing as route_opt
    from core.simulation.twin.live import trip_comparison as twin_test
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
    from core.common.data import provenance as pv
    from core.simulation.routing import analysis_routing as route_opt
    from fastapi.responses import JSONResponse
    rec = pv.load(routing_run_id)
    if not rec:
        return JSONResponse(status_code=404, content={"error": f"ROUTING_RUN_NOT_FOUND: {routing_run_id}"})
    return route_opt.public(rec)


@router.get("/api/recorded/{city_id}/replay", tags=["operate"])
def recorded_replay(city_id: str, at: str, seconds: int = 60):
    """REAL recorded traffic: the vehicles a dataset's cameras tracked, from clock time `at` on the recording day, for `seconds`. A replay, not live."""
    from fastapi import HTTPException
    from core.common.data.recorded import replay
    from core.simulation.routing import city_router
    try:
        replay.parse_at(at)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    got = city_router.network(city_id)
    net, bbox = (got[0], got[1]["bbox"]) if got else (None, None)
    return replay.window(city_id, at, seconds, net, bbox)


@router.get("/api/route/{city_id}", tags=["operate"])
def city_route(city_id: str, origin: str, destination: str, profile: str = "car", at: str | None = None):
    """Whole-city routes from the city's own Valhalla server: two or three alternatives with turn-by-turn maneuvers,
    for a car or a motorcycle. Times are from map speeds, not live traffic, and say so; a stretch a recorded site
    measured is re-timed with the speed recorded there at `at` ("HH:MM", default: the city's time now). A city without a
    routing server, or a server that does not answer, is reported as such."""
    from fastapi import HTTPException
    from core.simulation.routing import valhalla
    try:
        a, b = (tuple(float(x) for x in p.split(",")) for p in (origin, destination))
        assert len(a) == len(b) == 2
    except (ValueError, AssertionError):
        raise HTTPException(422, 'origin and destination must each be "lat,lon"')
    import re
    if at is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", at):
        raise HTTPException(422, 'at must be "HH:MM"')
    return valhalla.route(city_id, a, b, profile=profile, at=at)


NAV_COSTINGS = {"auto", "motorcycle"}
NAV_MAX_BODY = 64 * 1024


@router.post("/api/navigate/{city_id}/route", tags=["operate"])
async def navigate_route(city_id: str, request: Request):
    """Live turn-by-turn navigation (Ferrostar, BSD-3): Ferrostar's own Valhalla request forwarded unchanged to the city's routing server,
    and its answer back unchanged, so the server stays private. Car or motorbike only; a city without a server is refused as /api/route does."""
    import json as _json
    from fastapi.responses import JSONResponse, Response
    from core.simulation.routing import valhalla
    raw = await request.body()
    if len(raw) > NAV_MAX_BODY:
        return JSONResponse(status_code=413, content={"error": "request too large"})
    try:
        body = _json.loads(raw)
    except ValueError:
        return JSONResponse(status_code=422, content={"error": "the body must be Valhalla JSON"})
    if body.get("costing") not in NAV_COSTINGS:
        return JSONResponse(status_code=422, content={"error": f"costing must be one of {sorted(NAV_COSTINGS)}"})
    refused, url, _ = valhalla._server(city_id, "car")
    if refused:
        return JSONResponse(status_code=503, content=refused)
    refused, answer = valhalla._ask(city_id, url, body, "route")
    if refused:
        return JSONResponse(status_code=502 if refused["code"] in ("engine_down", "engine_error") else 404, content=refused)
    return Response(content=_json.dumps(answer), media_type="application/json")


@router.get("/api/route/{city_id}/signal", tags=["operate"])
def city_route_signal(city_id: str, origin: str, destination: str, profile: str = "car"):
    """Where the whole-city route between two points may have weak or no mobile signal, stretch by stretch, from the road (tunnels,
    open country, on the city's own routing server) and the recorded signal history of opted-in phones; it says where history is missing."""
    from fastapi import HTTPException
    from app.routing import signal_predict
    try:
        a, b = (tuple(float(x) for x in p.split(",")) for p in (origin, destination))
        assert len(a) == len(b) == 2
    except (ValueError, AssertionError):
        raise HTTPException(422, 'origin and destination must each be "lat,lon"')
    return signal_predict.predict(city_id, a, b, profile=profile)


@router.get("/api/trip/{city_id}", tags=["operate"])
def city_trip(city_id: str, origin: str, destination: str, recorded_at: str | None = None):
    """A trip on the city's own road network: the route section by section, each section's real speed now and its
    forecast where either exists, and the travel time at each departure. `origin` and `destination` are "lat,lon".
    Every traffic value carries a tag (real, simulated or forecast); a section without data has none. With
    `recorded_at` ("HH:MM") each section also gets the reading a published dataset recorded on it at that clock time,
    with the dataset's own date; recorded readings are never part of the travel times."""
    from fastapi import HTTPException
    from app.routing import city_trip as service
    try:
        a, b = (tuple(float(x) for x in p.split(",")) for p in (origin, destination))
        assert len(a) == len(b) == 2
    except (ValueError, AssertionError):
        raise HTTPException(422, 'origin and destination must each be "lat,lon"')
    import re
    if recorded_at is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", recorded_at):
        raise HTTPException(422, 'recorded_at must be "HH:MM"')
    return service.trip(city_id, a, b, recorded_at=recorded_at)

