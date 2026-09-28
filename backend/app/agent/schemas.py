"""Request contracts of the agent domain."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GoalRequest(BaseModel):
    user_id: str = "demo"
    text: str = Field(..., min_length=3, examples=["I must be at Shahbagh by 09:00 tomorrow from Farmgate; remind me 30 minutes before I should leave."])


class ApproveRequest(BaseModel):
    call_id: str
    approved: bool = True


class AnswerRequest(BaseModel):
    step_id: str
    text: str = Field(..., min_length=1)
