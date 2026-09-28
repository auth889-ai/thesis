"""Signal-control interfaces — GRADUATED FROM LAB 01.

Lab 01 validated this action contract with three classical controllers
(fixed-time, queue-actuated, movement max-pressure) over 5 seeds with 0
collisions. Labs 14-20 (network Max-Pressure, SUMO-RL/PPO, PressLight, FRAP,
CoLight, MAPPO, Forecast-Aware MAPPO) implement the same protocol via adapters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, Sequence, runtime_checkable

from app.common.types import JunctionId, TrafficObservation
from app.interfaces.forecasting import ForecastResult


class SignalActionType(str, Enum):
    HOLD = "hold"                    # keep current phase, no write
    EXTEND = "extend"                # prolong current green
    TERMINATE = "terminate"          # end green now (yellow follows by program)
    SWITCH_TO_PHASE = "switch_to_phase"   # explicit phase selection
    NOOP = "noop"                    # controller declines to act (e.g. mid-yellow)


@dataclass(frozen=True)
class SignalAction:
    """One controller decision for one junction.

    Kept minimal and declarative so a SafetyShield can inspect/replace it before
    it ever reaches the simulator.
    """

    junction_id: JunctionId
    action_type: SignalActionType = SignalActionType.NOOP
    target_phase: int | None = None
    duration_s: float | None = None
    reason: str = ""                                  # human-auditable rationale
    diagnostics: Mapping[str, float] = field(default_factory=dict)  # pressure, queues

    def __post_init__(self) -> None:
        if self.action_type is SignalActionType.SWITCH_TO_PHASE and self.target_phase is None:
            raise ValueError("SWITCH_TO_PHASE requires target_phase")
        if self.duration_s is not None and self.duration_s < 0:
            raise ValueError("duration_s must be >= 0")


@runtime_checkable
class TrafficController(Protocol):
    """Observation (+ optional forecast) → signal actions.

    The optional `forecast` argument is what makes Lab 20's contribution
    expressible without changing the interface: baselines ignore it, the
    forecast-aware controller uses it, and both are benchmarked identically.
    """

    def reset(self) -> None: ...

    def act(self, observation: TrafficObservation, time_s: float,
            forecast: ForecastResult | None = None) -> Sequence[SignalAction]: ...

    @property
    def name(self) -> str: ...

    @property
    def controlled_junctions(self) -> Sequence[JunctionId]: ...
