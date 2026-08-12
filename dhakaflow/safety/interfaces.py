"""Safety interfaces — the shield every controller action passes through.

Lab 01 already enforced min/max-green and preserved yellow transitions inside
its controllers. The platform promotes that from "each controller behaves" to
"the system guarantees": an RL policy (Labs 15-20) cannot be trusted to respect
constraints on its own, so the shield sits between controller and actuator.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..common.types import JunctionId, TrafficObservation
from ..control.interfaces import SignalAction


@dataclass(frozen=True)
class SafetyConstraints:
    """Hard constraints. Defaults match the Lab 01 validated configuration."""

    min_green_s: float = 10.0
    max_green_s: float = 45.0
    yellow_s: float = 3.0
    all_red_s: float = 0.0
    min_pedestrian_clearance_s: float = 0.0
    forbid_conflicting_greens: bool = True
    allow_emergency_override: bool = True

    def __post_init__(self) -> None:
        if self.min_green_s <= 0 or self.max_green_s < self.min_green_s:
            raise ValueError("require 0 < min_green_s <= max_green_s")
        if self.yellow_s < 0 or self.all_red_s < 0:
            raise ValueError("transition times must be >= 0")


@dataclass(frozen=True)
class SafetyViolation:
    """A rejected or corrected action — recorded, never silently dropped."""

    junction_id: JunctionId
    rule: str                      # "min_green" | "conflicting_green" | ...
    original_action: SignalAction
    replacement_action: SignalAction | None
    time_s: float
    detail: str = ""


@runtime_checkable
class SafetyShield(Protocol):
    """Filters proposed actions; reports every intervention.

    Contract: `filter` NEVER raises on an unsafe action — it returns a safe
    replacement and logs a SafetyViolation, so training can continue while the
    violation count becomes a first-class evaluation metric.
    """

    def filter(self, actions: Sequence[SignalAction], observation: TrafficObservation,
               time_s: float) -> tuple[Sequence[SignalAction], Sequence[SafetyViolation]]: ...

    def action_mask(self, junction: JunctionId, observation: TrafficObservation,
                    time_s: float) -> Sequence[bool]: ...

    @property
    def constraints(self) -> SafetyConstraints: ...

    @property
    def violations(self) -> Sequence[SafetyViolation]: ...
