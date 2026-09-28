"""NLP interfaces — Lab 24: incident text → structured events that actually feed
the forecaster, twin, router and controller (never decorative NLP)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence, runtime_checkable

from traffictwin.common.types import EdgeId


class IncidentType(str, Enum):
    ACCIDENT = "accident"
    ROAD_CLOSURE = "road_closure"
    CONSTRUCTION = "construction"
    FLOODING = "flooding"
    PROTEST_OR_EVENT = "protest_or_event"
    VIP_MOVEMENT = "vip_movement"
    BREAKDOWN = "breakdown"
    WEATHER = "weather"
    OTHER = "other"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class TrafficIncident:
    """Structured event extracted from unstructured text.

    `affected_edges` is what makes the incident actionable: until text is
    grounded to network elements it cannot influence the twin or the router.
    """

    incident_type: IncidentType
    severity: Severity
    location_text: str
    affected_edges: Sequence[EdgeId] = ()
    start_time_s: float | None = None
    expected_duration_s: float | None = None
    confidence: float = 0.0
    source_text: str = ""
    source: str = "unknown"           # operator message, news, social, hotline
    language: str = "bn"              # Bangla by default; "en" also expected
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must lie in [0, 1]")


@runtime_checkable
class IncidentExtractor(Protocol):
    """Text → incidents. Must attach confidence; downstream may filter on it."""

    def extract(self, text: str, received_at_s: float,
                language: str | None = None) -> Sequence[TrafficIncident]: ...

    @property
    def name(self) -> str: ...
