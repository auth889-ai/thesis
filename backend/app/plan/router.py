"""The day, the watch on it, and what actually happened."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.plan import day, monitor, notifications, outcomes

router = APIRouter()


class OutcomeRequest(BaseModel):
    user_id: str = "demo"
    ref: str = "trip"
    origin: str = ""
    destination: str = ""
    predicted_s: float | None = None
    recommended_depart_utc: str | None = None
    departed_utc: str = Field(..., description="ISO-8601")
    arrived_utc: str = Field(..., description="ISO-8601")
    deadline_utc: str | None = None


class ReadRequest(BaseModel):
    user_id: str = "demo"
    ids: list[str] | None = None


@router.get("/api/plan/day", tags=["plan"])
def plan_day(user_id: str = "demo", hours: float = 24.0):
    """The timeline: events, tasks due, reminders, and a fresh departure for every event or saved commute with a place."""
    return day.timeline(user_id, hours)


@router.post("/api/plan/check", tags=["plan"])
def plan_check(user_id: str = "demo"):
    """Recompute this person's departures now and report any change (the monitor does this every few minutes)."""
    return {"changes": monitor.tick(user_id), "monitor": monitor.state()}


@router.get("/api/notifications", tags=["plan"])
def notifications_list(user_id: str = "demo"):
    rows = notifications.list_for(user_id)
    return {"notifications": rows, "unread": sum(1 for r in rows if not r["read_utc"]), "monitor": monitor.state()}


@router.post("/api/notifications/read", tags=["plan"])
def notifications_read(req: ReadRequest):
    return {"marked": notifications.mark_read(req.user_id, req.ids)}


@router.post("/api/outcomes", tags=["plan"])
def outcomes_record(req: OutcomeRequest):
    try:
        row = outcomes.record(req.user_id, req.ref, req.origin, req.destination, req.predicted_s, req.recommended_depart_utc, req.departed_utc, req.arrived_utc, req.deadline_utc)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return {"outcome": row, "calibration": outcomes.calibration(req.user_id)}


@router.get("/api/outcomes", tags=["plan"])
def outcomes_list(user_id: str = "demo"):
    return {"outcomes": outcomes.list_for(user_id), "calibration": outcomes.calibration(user_id)}
