"""Commute routes: plan a departure for a target arrival from the city's own observed history; a corridor's profile; watch a route."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.commute import service
from app.commute.schemas import CommutePlanRequest

router = APIRouter()


@router.post("/api/commute/plan", tags=["commute"])
def commute_plan(req: CommutePlanRequest):
    """Leave when? The latest departure that still arrives by `arrive_by` with ≥ 80 % probability, the route to
    take, ETA now vs at that departure, and the day's traffic profile with the congestion window."""
    try:
        arrive = datetime.fromisoformat(req.arrive_by)
    except ValueError:
        raise HTTPException(422, "arrive_by must be an ISO-8601 datetime, e.g. 2026-09-29T09:00:00+06:00")
    try:
        return service.plan(req.city, req.origin, req.destination, arrive, buffer_min=req.buffer_min, step_min=req.step_min)
    except (ValueError, LookupError) as exc:
        raise HTTPException(422, str(exc))


@router.get("/api/commute/profile", tags=["commute"])
def commute_profile(corridor: str = "farmgate_to_shahbagh", city: str = "dhaka", tz_offset_h: float = 6.0):
    """One corridor's own time-of-day profile from the city's observed history (OWN_OBSERVED, never Google-derived)."""
    p = service.profile(corridor, city, tz_offset_h)
    if not any(s["samples"] for s in p["slots"]):
        raise HTTPException(404, f"no own readings for corridor {corridor} in {city} yet")
    return p


@router.post("/api/commute/watch", tags=["commute"])
def commute_watch(payload: dict):
    """Watch a route: it becomes an observed corridor of its city and the recorder samples it every five minutes."""
    try:
        return service.watch_route(payload.get("city", ""), payload.get("origin", ""), payload.get("destination", ""))
    except (ValueError, LookupError) as exc:
        raise HTTPException(422, str(exc))
