"""THE CONTRACTS — Person, Commitment, Constraint, TravelEdge, Outcome, Action, Event.

Frozen in docs/PROBLEM.md. Every field has one meaning; anything a model or a person produces must validate here
before it is stored. Times are timezone-aware instants; local presentation is the client's job."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _aware(v: datetime) -> datetime:
    if v.tzinfo is None:
        raise ValueError("timestamps must carry a timezone")
    return v.astimezone(timezone.utc)


class Place(BaseModel):
    id: str | None = Field(None, description="assigned by the store on first save")
    name: str = Field(..., min_length=1)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    kind: str = Field("other", pattern="^(home|work|saved|other)$")


class MobilityProfile(BaseModel):
    max_walk_min: int = Field(20, ge=0, le=180)
    wheelchair: bool = False
    avoid_stairs: bool = False
    elevator_required: bool = False


class Person(BaseModel):
    id: str
    name: str | None = None
    timezone: str = "UTC"
    city: str | None = None
    home: Place | None = None
    places: list[Place] = Field(default_factory=list)
    mobility: MobilityProfile = Field(default_factory=MobilityProfile)
    on_time_target: float = Field(0.8, ge=0.5, le=0.99)
    calibration_factor: float = Field(1.0, ge=0.5, le=3.0, description="measured from outcomes: actual ÷ predicted travel time")


class CommitmentType(str, enum.Enum):
    CLASS = "class"; WORK = "work"; MEETING = "meeting"; INTERVIEW = "interview"; EXAM = "exam"; MEDICAL = "medical"
    DEADLINE = "deadline"; ERRAND = "errand"; TRAVEL = "travel"; SOCIAL = "social"; OTHER = "other"


class Priority(str, enum.Enum):
    MUST = "must"; SHOULD = "should"; COULD = "could"


class Flexibility(str, enum.Enum):
    FIXED = "fixed"                       # happens at `start`
    MOVABLE = "movable"                   # may move inside [window_start, window_end]
    ANYTIME_BEFORE = "anytime_before"     # any time before `deadline`, needs `duration_min`


class Commitment(BaseModel):
    id: str
    person_id: str
    title: str = Field(..., min_length=1)
    type: CommitmentType = CommitmentType.OTHER
    location: Place | None = None
    start: datetime | None = None
    deadline: datetime = Field(..., description="the latest acceptable arrival or completion instant")
    duration_min: int = Field(60, ge=0)
    priority: Priority = Priority.SHOULD
    flexibility: Flexibility = Flexibility.FIXED
    window_start: datetime | None = None
    window_end: datetime | None = None
    requirements: list[str] = Field(default_factory=list, description="things to bring or finish first: CV, ID, the report")
    depends_on: list[str] = Field(default_factory=list, description="commitment ids that must complete before this one")
    source: str = Field("person", description="person | calendar | task | agent | email")
    created_at: datetime = Field(default_factory=now_utc)

    _aware = field_validator("start", "deadline", "window_start", "window_end", "created_at", mode="after")(lambda v: _aware(v) if v else v)

    @model_validator(mode="after")
    def _consistent(self):
        if self.flexibility == Flexibility.FIXED and self.start is None:
            raise ValueError("a fixed commitment needs a start")
        if self.start and self.deadline < self.start:
            raise ValueError("deadline is before start")
        if self.flexibility == Flexibility.MOVABLE and not (self.window_start and self.window_end and self.window_start <= self.window_end):
            raise ValueError("a movable commitment needs window_start <= window_end")
        if self.flexibility == Flexibility.ANYTIME_BEFORE and self.duration_min <= 0:
            raise ValueError("an anytime-before commitment needs a positive duration")
        if self.id in self.depends_on:
            raise ValueError("a commitment cannot depend on itself")
        return self


class ConstraintKind(str, enum.Enum):
    WEATHER = "weather"; ACCESSIBILITY = "accessibility"; COST = "cost"; TIME = "time"; CUSTOM = "custom"


class Constraint(BaseModel):
    id: str
    person_id: str
    kind: ConstraintKind
    applies_to: list[str] = Field(default_factory=list, description="commitment or edge ids; empty means the whole day")
    params: dict[str, str | int | float | bool] = Field(default_factory=dict, description="one row per key in the store")
    severity: str = Field("soft", pattern="^(hard|soft)$")
    source: str = "person"
    created_at: datetime = Field(default_factory=now_utc)


class Mode(str, enum.Enum):
    CAR = "car"; TRANSIT = "transit"; WALK = "walk"; CYCLE = "cycle"; MIXED = "mixed"


class Uncertainty(BaseModel):
    p10_s: int | None = Field(None, ge=0)
    p50_s: int | None = Field(None, ge=0)
    p90_s: int | None = Field(None, ge=0)
    method: str | None = Field(None, description="recorded_bands | conformal | none")

    @model_validator(mode="after")
    def _ordered(self):
        vals = [v for v in (self.p10_s, self.p50_s, self.p90_s) if v is not None]
        if vals != sorted(vals):
            raise ValueError("p10 <= p50 <= p90")
        return self


class Freshness(str, enum.Enum):
    LIVE = "live"; TYPICAL = "typical"; RECORDED = "recorded"; STATIC = "static"


class TravelEdge(BaseModel):
    id: str
    person_id: str
    origin: Place
    destination: Place
    mode: Mode
    depart: datetime
    duration_s: int = Field(..., ge=0, description="expected")
    distance_m: int | None = Field(None, ge=0)
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    cost: float | None = Field(None, ge=0)
    accessible: bool | None = None
    provider: str = Field(..., description="who produced the duration: amazon_location | valhalla | otp | r5 | static")
    model: str | None = None
    freshness: Freshness = Freshness.STATIC
    generated_at: datetime = Field(default_factory=now_utc)

    _aware = field_validator("depart", "generated_at", mode="after")(lambda v: _aware(v))

    @property
    def arrive(self) -> datetime:
        from datetime import timedelta
        return self.depart + timedelta(seconds=self.duration_s)


class Outcome(BaseModel):
    id: str
    person_id: str
    commitment_id: str
    planned_departure: datetime | None = None
    actual_departure: datetime | None = None
    predicted_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    on_time: bool | None = None
    forecast_error_s: int | None = None
    recorded_at: datetime = Field(default_factory=now_utc)


class Action(BaseModel):
    """One thing the system did or proposed, under the permission engine's decision."""
    id: str
    person_id: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk: str = Field("read", pattern="^(read|write_reversible|write_irreversible|external|financial)$")
    decision: str = Field("allow", pattern="^(allow|ask|refuse)$")
    approved_by: str | None = None
    executed_at: datetime | None = None
    result: dict[str, Any] | None = None
    goal_id: str | None = None


class EventKind(str, enum.Enum):
    TRAFFIC_UPDATED = "TrafficUpdated"; CALENDAR_CHANGED = "CalendarChanged"; TRANSIT_DELAYED = "TransitDelayed"; WEATHER_CHANGED = "WeatherChanged"
    USER_LATE = "UserLate"; COMMITMENT_UPDATED = "CommitmentUpdated"; PLAN_INVALIDATED = "PlanInvalidated"; REPAIR_PROPOSED = "RepairProposed"


class Event(BaseModel):
    id: str
    person_id: str | None = None
    kind: EventKind
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=now_utc)
    source: str = "system"


ENTITIES = {"person": Person, "commitment": Commitment, "constraint": Constraint, "travel_edge": TravelEdge, "outcome": Outcome, "action": Action, "event": Event}
