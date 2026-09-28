"""Commute routes: plan a departure for a target arrival; the recorded time-of-day profile of a corridor."""
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
def commute_profile(corridor: str = "farmgate_to_shahbagh"):
    """The recorded congestion profile of one corridor by local time of day (TYPICAL_RECORDED, never live)."""
    p = service.profile(corridor)
    if not any(s["samples"] for s in p["slots"]):
        raise HTTPException(404, f"no recorded history for corridor {corridor}")
    return p
