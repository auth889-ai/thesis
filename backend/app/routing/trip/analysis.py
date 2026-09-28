"""The analysis, stage by stage, each reported as it happens and recorded with provenance:

    Resolving city            origin and destination
    Validating traffic data   the candidate routes and the corridor states (live provider or local router)
    Loading checkpoint        the registry's forecast decision for this city
    Running inference         the forecast per corridor, then the observatory fill-in
    Evaluating routes         every route priced from the forecast; one recommended, with the reason
    Preparing result          hashes, run record, the page's payload
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

from . import places
from .corridors import accuracy, corridor_polylines, levels_from_speeds, observatory_fill, usable
from .geometry import HORIZONS
from .pricing import bbox_of, decide, layers_for, price_routes
from app.data.live_providers import live

from .routes import fetch_routes


def horizon_for(p: dict) -> tuple[int, int, str | None]:
    """(requested horizon, the horizon actually used, departure): a departure further out than the
    requested horizon moves the analysis to the next available horizon."""
    horizon = int(p.get("horizon_min") or 30)
    dep = p.get("departure")
    lead = horizon
    if dep:
        try:
            d = datetime.fromisoformat(dep)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            lead = max(horizon, int((d - datetime.now(timezone.utc)).total_seconds() // 60))
        except ValueError:
            pass
    return horizon, min([x for x in HORIZONS if x >= lead] or [60]), dep


def forecast_for(city: str, cid: str | None, model_req: str | None, observe: dict, corr: dict) -> tuple[dict, dict, dict, dict, dict]:
    """(forecast bundle, its forecast, predicted levels per horizon, observed levels, corridor snapshot)."""
    if places.is_dhaka(city):
        from app.routing.forecast_costs import recorded_forecast
        fc = recorded_forecast("dhaka", HORIZONS, model_req, "latest")
        f = fc.get("forecast") or {}
        pred = {hh: dict(zip(f.get("node_ids", []), f["values"].get(hh) or f["values"].get(str(hh)) or []))
                for hh in HORIZONS} if f else {hh: {} for hh in HORIZONS}
        return fc, f, pred, dict((fc.get("observed") or {}).get("levels") or {}), corr
    if cid and observe["steps_have"] >= 1:
        # a city being observed: its own corridors, its own live history, the same forecast
        # interface — persistence from the first sample, Chronos from the eighth
        from app.data.live_providers import observatory as obs_mod
        from app.data.live_providers import live
        from app.forecasting.adapters.registry import forecast as run_forecast
        cd_city = obs_mod.observatory.city_data(cid)
        service = live.provider()
        corr = service.corridors_for(cid) if service else corr
        fc = run_forecast(cd_city, HORIZONS, model_req)
        f = fc.get("forecast") or {}
        fc["input"] = cd_city.describe()
        observed, pred = levels_from_speeds(cd_city, f or None, corr)
        return fc, f, pred, observed, corr
    return {"forecast": None, "observed": {}, "input": {}}, {}, {hh: {} for hh in HORIZONS}, {}, corr


def run(job: str, p: dict, emit) -> dict:
    """The whole analysis for one request. Raises on failure (the job table records the reason)."""
    from app.data import provenance as pv
    city = p.get("city") or "dhaka"
    run_ = pv.Run(job, city=city, origin=p.get("origin"), destination=p.get("destination"), requested_model=p.get("model") or "auto",
                  horizon_min=int(p.get("horizon_min") or 30), request=p)
    try:
        return _run(job, p, emit, city, run_)
    except BaseException as exc:
        try:
            run_.finish("failed", f"{type(exc).__name__}: {exc}")
        except Exception:                               # noqa: BLE001 - provenance never masks the real error
            pass
        raise


def _run(job: str, p: dict, emit, city: str, run) -> dict:
    from app.data import provenance as pv
    horizon, h, dep = horizon_for(p)
    model_req = (p.get("model") or "").strip() or None      # a specific model, or the registry's forecast decision
    from app.forecasting.operations import model_registry
    product = model_registry.state(places.city_id_for(city) or city)
    if not model_req or model_req.lower() in ("auto", "best"):
        model_req = product["forecast"]["model"] if product["forecast"]["model"] not in ("persistence",) else None
    run.stage("Resolving city", emit)
    o = places.resolve_place(p.get("origin") or "farmgate", city)
    d = places.resolve_place(p.get("destination") or "shahbagh", city)
    run.set(origin_resolved=o, destination_resolved=d)
    run.stage("Validating traffic data", emit)
    routes, corr, traffic_basis = fetch_routes(o, d, city, run, emit)
    run.stage("Loading checkpoint", emit)
    dhaka = places.is_dhaka(city)
    cid = places.city_id_for(city)
    from app.data.live_providers import observatory as obs_mod
    observe = {"city_id": cid, "watched": bool(cid) and cid in obs_mod.observatory.cities(),
               "steps_have": obs_mod.observatory.readiness(cid)["steps_have"] if cid else 0}
    fc, f, pred, observed, corr = forecast_for(city, cid, model_req, observe, corr)
    forecastable = bool(f)
    run.set(resolved_model=f.get("model") if f else "none", checkpoint_path=f.get("checkpoint") if f else None,
            dataset_hash=pv.sha_json(fc.get("input") or {}), graph_hash=None,
            input_window_hash=pv.sha_json((fc.get("input") or {}).get("last_utc") or fc.get("input") or {}),
            cache_hit_training=False, result_source="LIVE_COMPUTATION")
    run.stage("Running inference", emit)
    if dhaka:
        try:
            observatory_fill(city, corr, pred, observed)
        except Exception as exc:                        # noqa: BLE001 - the recorded forecast still stands
            emit(observatory_note=f"observatory forecast unavailable: {type(exc).__name__}: {exc}")
    acc = accuracy(f.get("model", ""))
    clean = {str(k): {kk: (None if vv is None or vv != vv else round(float(vv), 4)) for kk, vv in v.items()} for k, v in pred.items()}
    run.set(raw_prediction_hash=pv.sha_json(clean),
            raw_prediction_first10=[None if v is None or v != v else round(float(v), 3) for v in list(pred.get(HORIZONS[0], {}).values())[:10]],
            # the full raw prediction is kept with the run so the route optimizer prices edges from
            # THIS forecast, never from a recomputation on a later window
            raw_prediction=clean, forecast_unit=f.get("unit") if f else None)
    run.stage("Evaluating routes", emit)
    if dhaka:
        axes = corridor_polylines(corr)
    elif forecastable:
        axes = {c["id"]: [tuple(pt) for sgm in (c.get("segments") or []) for pt in (sgm.get("coordinates") or [])]
                for c in corr.get("corridors", []) if usable(c)}
        axes = {k: v for k, v in axes.items() if len(v) >= 2}
    else:
        axes = {}
    cards = price_routes(routes, axes, pred, observed)
    best_now, best_pred, saving, reason = decide(cards, h, forecastable, city)
    a_h = (acc.get(h) or {}) if dhaka else {}       # the backtest is Dhaka's; never borrowed
    cur_speed = (best_now["distance_m"] / best_now["eta_now_s"] * 3.6) if best_now.get("distance_m") else None
    result = {
        "city": city, "is_dhaka": dhaka, "forecastable": forecastable, "observe": observe, "bbox": bbox_of(cards),
        "origin": o, "destination": d, "departure": dep, "horizon_min": h, "requested_horizon_min": horizon,
        "current": {"eta_s": best_now["eta_now_s"], "route": best_now["key"],
                    "speed_kmh": round(cur_speed, 1) if cur_speed else None,
                    "congestion": best_now["category_now"], "distance_m": best_now["distance_m"]},
        "forecast": {"eta_s": best_now["forecast"][h]["eta_s"], "risk": best_now["forecast"][h]["risk"],
                     "covered": best_now["forecast"][h]["covered"],
                     "confidence": (f"{a_h['class_accuracy'] * 100:.0f} % class accuracy at +{h} min on this city's recorded data" if a_h else
                                    (f"{observe['steps_have']} live samples so far — not yet scored" if forecastable
                                     else f"no observed corridors in {city} yet")),
                     "class_accuracy": a_h.get("class_accuracy"), "model": f.get("model"),
                     "checkpoint": f.get("checkpoint"), "input_steps": f.get("input_window_steps"),
                     "observed_levels": observed},
        "decision": {"recommended": best_pred["key"], "saving_s": max(0, saving), "reason": reason,
                     "basis": "forecast-derived future edge costs on the observed corridors"},
        "routes": cards, "layers": layers_for(corr, axes, pred, dhaka or forecastable), "retrieved_at": routes.get("retrieved_at"),
        "source": {"traffic": live.traffic_words(routes, traffic_basis), "traffic_basis": traffic_basis, "is_live": bool(routes.get("is_live")),
                   "traffic_coverage": bool(routes.get("traffic_coverage")), "routing": routes.get("source"), "forecast": fc.get("input", {}),
                   "incidents": [i for r in routes.get("routes", [])[:3] for i in (r.get("incidents") or [])]},
    }
    run.stage("Preparing result", emit)
    run.set(postprocessed_prediction_hash=pv.sha_json([c["forecast"] for c in cards]), recommended=best_pred["key"])
    rec = run.finish("done")
    result.update(run_id=job, result_source="LIVE_COMPUTATION", cache_hit_training=False, inference_recomputed=True,
                  provenance=run.summary(), stages=rec["stages"],
                  forecast_decision={**product["forecast"], "model_used": f.get("model") if f else None}, routing_policy=product["routing"])
    return result
