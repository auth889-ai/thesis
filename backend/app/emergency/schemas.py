"""Request for a live ambulance run on the simulated twin."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    city_id: str
    arm: Literal["no_alert", "alert", "alert_preemption"] = "alert_preemption"
    technology: Optional[str] = None               # a technology of the network model; refused when one of its parameters has no source
    equipped_share: float = Field(1.0, ge=0.0, le=1.0)
    demand: Literal["generated", "calibrated"] = "generated"
    depart_s: int = Field(60, ge=1, le=3000)
    duration_s: int = Field(1800, ge=120, le=3600)
    step_delay_ms: int = Field(1000, ge=0, le=2000)
