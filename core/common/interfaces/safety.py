"""Safety interfaces — the shield every controller action passes through.

Lab 01 already enforced min/max-green and preserved yellow transitions inside
its controllers. The platform promotes that from "each controller behaves" to
"the system guarantees": an RL policy (Labs 15-20) cannot be trusted to respect
constraints on its own, so the shield sits between controller and actuator.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Protocol, Sequence, runtime_checkable

from core.common.types import JunctionId, TrafficObservation
from core.common.interfaces.control import SignalAction


@dataclass(frozen=True)
class SafetyConstraints:
    """Hard signal-timing constraints for ONE scenario/junction group.

    There are **no universal timing values**. Green/yellow/all-red durations
    depend on approach speed, junction geometry, crossing width, pedestrian
    volumes and local regulation, so every value must come from a named,
    scenario-specific profile supplied by config — never from a library default.
    `profile_name` is mandatory so that any reported result states which timing
    regime produced it.

    Dhaka profiles must be derived from Dhaka field/regulatory data (Labs 02/03
    onward) and are NOT expected to equal the Lab 01 reference values.
    """

    profile_name: str
    min_green_s: float
    max_green_s: float
    yellow_s: float
    all_red_s: float = 0.0
    min_pedestrian_clearance_s: float = 0.0
    forbid_conflicting_greens: bool = True
    allow_emergency_override: bool = True
    provenance: str = ""            # where these numbers came from

    def __post_init__(self) -> None:
        if not self.profile_name:
            raise ValueError("profile_name is required — timing values are never anonymous")
        if self.min_green_s <= 0 or self.max_green_s < self.min_green_s:
            raise ValueError("require 0 < min_green_s <= max_green_s")
        if self.yellow_s < 0 or self.all_red_s < 0:
            raise ValueError("transition times must be >= 0")
        if self.min_pedestrian_clearance_s < 0:
            raise ValueError("min_pedestrian_clearance_s must be >= 0")

    @classmethod
    def from_profile(cls, name: str, **overrides) -> "SafetyConstraints":
        """Build from a registered named profile (see SAFETY_PROFILES)."""
        try:
            base = SAFETY_PROFILES[name]
        except KeyError as exc:
            raise KeyError(f"unknown safety profile {name!r}; "
                           f"available: {sorted(SAFETY_PROFILES)}") from exc
        return replace(base, **overrides) if overrides else base


#: Timing regime validated by Lab 01 on its synthetic 4-arm unit junction.
#: Use for regression tests, examples and reproducing Lab 01 — NOT as a Dhaka
#: default and NOT as a recommendation for any real intersection.
LAB01_VALIDATED_REFERENCE_PROFILE = SafetyConstraints(
    profile_name="LAB01_VALIDATED_REFERENCE_PROFILE",
    min_green_s=10.0,
    max_green_s=45.0,
    yellow_s=3.0,
    all_red_s=0.0,
    min_pedestrian_clearance_s=0.0,
    provenance=("Lab 01 synthetic unit junction (paper_labs/01_sumo_foundation), "
                "validated 5-seed run at commit ca2ac81; synthetic scenario values, "
                "no real-world jurisdiction"),
)

#: Named profiles available to configs. Dhaka profiles are added only when
#: backed by field/regulatory evidence; there is deliberately no "default".
SAFETY_PROFILES: dict[str, SafetyConstraints] = {
    LAB01_VALIDATED_REFERENCE_PROFILE.profile_name: LAB01_VALIDATED_REFERENCE_PROFILE,
}


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
