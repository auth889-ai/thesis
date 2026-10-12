"""Transit routes: the lines around a trip, and a door-to-door rail option to set beside the road routes."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.common.data import osm

from app.transit import service

router = APIRouter()


class TransitPlanRequest(BaseModel):
    city: str = "dhaka"
    origin: str = Field(..., examples=["Farmgate"])
    destination: str = Field(..., examples=["Motijheel"])
    depart_at: str | None = Field(None, description="ISO-8601 datetime with offset; now when absent")


@router.post("/api/transit/plan", tags=["transit"])
def transit_plan(req: TransitPlanRequest):
    """Walk, wait, ride, walk on every rail line within walking reach of both ends, from OpenStreetMap read now."""
    from core.simulation.routing.trip.places import resolve_place
    from app.commute.service import LOCAL_UTC_OFFSET_H
    try:
        o, d = resolve_place(req.origin, req.city), resolve_place(req.destination, req.city)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    depart = None
    if req.depart_at:
        try:
            depart = datetime.fromisoformat(req.depart_at)
        except ValueError:
            raise HTTPException(422, "depart_at must be an ISO-8601 datetime")
    out = service.plan((o["lat"], o["lng"]), (d["lat"], d["lng"]), depart, LOCAL_UTC_OFFSET_H)
    return {"origin": o, "destination": d, **out}


@router.get("/api/transit/lines", tags=["transit"])
def transit_lines(south: float, west: float, north: float, east: float):
    """The rail-type routes OpenStreetMap has in a box, with their ordered stops."""
    try:
        return {"lines": osm.rail_lines(south, west, north, east), "source": "openstreetmap"}
    except Exception as exc:                            # noqa: BLE001
        raise HTTPException(503, f"OpenStreetMap unavailable: {type(exc).__name__}")
