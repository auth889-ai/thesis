"""Probes over HTTP: a browser posts its fixes; the map reads the cells."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.probes import service

router = APIRouter()


class Fix(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    recorded_at: str
    accuracy_m: float | None = None
    heading: float | None = None
    speed_kmh: float | None = None


class Batch(BaseModel):
    device_id: str = Field(min_length=4, max_length=128)
    city: str = Field(min_length=1, max_length=64)
    points: list[Fix] = Field(max_length=500)


@router.post("/api/probes", tags=["probes"])
def post_probes(batch: Batch):
    """Share location fixes from a phone. The device id is hashed before storage; raw fixes are purged
    after 24 hours; only the per-cell aggregates are kept. Returns what was accepted and why not."""
    if not batch.points:
        raise HTTPException(422, "no points")
    return service.ingest(batch.device_id, batch.city, [p.model_dump() for p in batch.points])


@router.get("/api/probes/cells", tags=["probes"])
def get_cells(city: str, minutes: int = 30):
    """The latest speed per road-direction cell in the last `minutes`, with how many fixes and devices it rests on."""
    return service.cells(city, max(5, min(minutes, 24 * 60)))


@router.get("/api/probes/status", tags=["probes"])
def get_status(city: str):
    """How the probe layer is configured and how much it holds for this city."""
    return service.status(city)
