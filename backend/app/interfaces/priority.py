"""Priority interfaces — Lab 23 (emergency vehicles, buses/person-delay,
pedestrian-aware control). Priority requests modify control intent; the
SafetyShield still has the final word."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence, runtime_checkable

from app.common.types import JunctionId, LaneId, TrafficObservation, VehicleClass
from app.interfaces.control import SignalAction


class PriorityKind(str, Enum):
    EMERGENCY = "emergency"
    TRANSIT = "transit"
    PEDESTRIAN = "pedestrian"


@dataclass(frozen=True)
class PriorityRequest:
    """A claim for preferential treatment at a junction."""

    kind: PriorityKind
    junction_id: JunctionId
    approach_lane: LaneId | None = None
    eta_s: float | None = None
    occupancy_persons: int = 1          # buses carry many — person-delay, not vehicle-delay
    vehicle_class: VehicleClass = VehicleClass.EMERGENCY
    urgency: float = 1.0                # [0, 1]
    metadata: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class PriorityPolicy(Protocol):
    """Adjusts proposed actions to honour priority claims.

    Returns adjusted actions; the caller then passes them through the
    SafetyShield, so priority can never bypass hard safety constraints.
    """

    def adjust(self, actions: Sequence[SignalAction], requests: Sequence[PriorityRequest],
               observation: TrafficObservation, time_s: float) -> Sequence[SignalAction]: ...

    @property
    def name(self) -> str: ...
