"""Profile routes: read, save, and find the city at the person's location."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.profile import service, store

router = APIRouter()


class ProfileRequest(BaseModel):
    user_id: str
    name: str | None = None
    timezone: str | None = Field(None, description="an IANA zone name, e.g. Asia/Dhaka, America/Los_Angeles")
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    home: str | None = None
    work: str | None = None
    on_time_target: float | None = Field(None, ge=0.5, le=0.99, description="the on-time probability departures must reach")


class LocateRequest(BaseModel):
    lat: float
    lng: float


@router.get("/api/profile", tags=["profile"])
def get_profile(user_id: str):
    return service.context(user_id)


@router.put("/api/profile", tags=["profile"])
def put_profile(req: ProfileRequest):
    fields = {k: v for k, v in req.model_dump().items() if v is not None and k != "user_id"}
    if "timezone" in fields:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(fields["timezone"])
        except Exception:                               # noqa: BLE001
            raise HTTPException(422, f"unknown timezone {fields['timezone']!r}")
    store.save(req.user_id, **fields)
    return service.context(req.user_id)


@router.post("/api/profile/locate", tags=["profile"])
def locate(req: LocateRequest):
    try:
        return service.locate(req.lat, req.lng)
    except Exception as exc:                            # noqa: BLE001 - the page shows why
        raise HTTPException(502, f"could not find the city at that point: {type(exc).__name__}: {str(exc)[:120]}")
