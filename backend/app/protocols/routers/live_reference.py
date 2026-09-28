"""Live reference HTTP endpoints."""
from __future__ import annotations

from app.data import reference_corridors as corridor_registry
from app.data.live_providers import observatory as observatory_mod
from app.data.live_providers import google_routes as live_service
from app.forecasting.operations import live_reference as predict_live
from app import credentials as key_store
from app.twin.live import counterfactual_jobs as simulate
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/live/corridors", tags=["live"])
def live_corridors(force: bool = False):
    """Every monitored Dhaka corridor, live. `force=true` bypasses the short in-memory cache."""
    return live_service.service.corridors(force=force)


@router.get("/api/live/corridor/{corridor_id}", tags=["live"])
def live_corridor(corridor_id: str, force: bool = False):
    """One corridor: traffic-aware ETA, static ETA, penalty, geometry and speed intervals."""
    return live_service.service.corridor(corridor_id, force=force)


@router.get("/api/live/routes", tags=["live"])
def live_routes(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    """Alternative routes between two points, traffic-aware, from the live API."""
    return live_service.service.routes((origin_lat, origin_lng), (dest_lat, dest_lng))


@router.get("/api/live/health", tags=["live"])
def live_health():
    """API health and credential presence. Reports a key fingerprint, never a key."""
    return {"live": live_service.service.health(), "credentials": key_store.status()}


@router.get("/api/predict/{corridor_id}", tags=["predict"])
def predict(corridor_id: str, force: bool = False):
    """Live state, then 5 / 15 / 30 / 60 min ahead.

    The response separates LIVE DHAKA INPUT from MODEL VALIDATED ON REAL BENCHMARK DATA and sets
    `dhaka_accuracy_claimed: false` — there is not yet enough lawful Dhaka ground truth to state
    an accuracy figure, so none is given.
    """
    cur = live_service.service.corridor(corridor_id, force=force)
    pred = predict_live.predictor.predict(
        corridor_id,
        current_state=cur.get("category", "UNKNOWN"),
        duration_s=cur.get("duration_s"),
        static_s=cur.get("static_duration_s"))
    return {"live": cur, "prediction": pred,
            "source": "google_routes + this project's recorded verdicts",
            "retrieved_at": cur.get("retrieved_at"),
            "is_live": cur.get("is_live", False),
            "request_status": cur.get("request_status", "UNKNOWN")}


@router.post("/api/simulate", tags=["simulate"])
def simulate_start(payload: dict):
    """Start a SUMO counterfactual from the selected live state. Returns a job to poll.

    Results are a SIMULATED COUNTERFACTUAL on the calibrated twin, never a live-road outcome.
    """
    return simulate.runner.start(
        corridor_id=payload.get("corridor_id", ""),
        category=payload.get("category", "UNKNOWN"),
        seeds=payload.get("seeds") or [11, 12, 13],
        horizon=int(payload.get("horizon", 1800)),
        compliance=float(payload.get("compliance", 0.3)))


@router.get("/api/simulate/{job_id}", tags=["simulate"])
def simulate_status(job_id: str):
    return simulate.runner.status(job_id)


@router.get("/api/corridors", tags=["live"])
def corridor_list():
    """The monitored corridors and which of them a counterfactual can honestly be run on."""
    return {"corridors": [corridor_registry.describe(c) for c in corridor_registry.CORRIDORS],
            "total": len(corridor_registry.CORRIDORS),
            "sumo_mapped": sum(1 for c in corridor_registry.CORRIDORS if c["sumo_mapped"])}


@router.get("/api/observatory", tags=["live"])
def observatory_status(city_id: str = "dhaka"):
    return {"status": observatory_mod.observatory.status(),
            "readiness": observatory_mod.observatory.readiness(city_id)}


@router.post("/api/observatory/start", tags=["live"])
def observatory_start(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.start(cid)


@router.post("/api/observatory/sample", tags=["live"])
def observatory_sample(payload: dict | None = None):
    cid = (payload or {}).get("city_id", "dhaka")
    return observatory_mod.observatory.sample(cid)
