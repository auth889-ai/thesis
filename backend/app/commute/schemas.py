"""Request contracts of the commute domain."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CommutePlanRequest(BaseModel):
    city: str = "dhaka"
    origin: str = Field(..., examples=["Farmgate"])
    destination: str = Field(..., examples=["Shahbagh"])
    arrive_by: str = Field(..., description="ISO-8601 datetime with offset, e.g. 2026-09-29T09:00:00+06:00")
    buffer_min: int = Field(5, ge=0, le=60, description="safety margin subtracted from the deadline")
    step_min: int = Field(10, ge=5, le=30, description="candidate departures every N minutes")
