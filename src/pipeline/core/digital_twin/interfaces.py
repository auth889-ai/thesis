"""Digital-twin interface — Lab 13 target.

The twin is a calibrated simulation kept aligned with observed reality, able to
answer what-if questions faster than real time. It composes a SimulationBackend
(Lab 01) with real measurements (Lab 06) and calibration evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..common.types import TrafficMetrics, TrafficObservation, TrafficScenario
from ..control.interfaces import SignalAction


@dataclass(frozen=True)
class CalibrationReport:
    """Real-vs-simulated agreement.

    Fields follow the criteria of Alvarez Lopez et al. (2018) §VII: RMSE is the
    recommended measure, and a common network criterion is that >85% of
    simulated counts deviate <15% from measured counts (`counts_within_15pct`).
    """

    scenario_id: str
    flow_rmse_vph: float | None = None
    speed_rmse_ms: float | None = None
    queue_rmse_veh: float | None = None
    counts_within_15pct: float | None = None      # fraction in [0, 1]
    n_comparison_sites: int = 0
    observation_window_s: tuple[float, float] = (0.0, 0.0)
    per_site: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    passed: bool | None = None
    notes: str = ""


@runtime_checkable
class DigitalTwin(Protocol):
    """Calibrated, queryable model of the real network."""

    def sync(self, observation: TrafficObservation) -> None:
        """Align twin state with a real measurement."""

    def step(self, actions: Sequence[SignalAction] | None = None) -> TrafficObservation: ...

    def what_if(self, scenario: TrafficScenario,
                actions: Sequence[SignalAction] | None = None) -> TrafficMetrics:
        """Run a counterfactual faster than real time; must not disturb live state."""

    def calibrate(self, observations: Sequence[TrafficObservation]) -> CalibrationReport: ...

    @property
    def calibration(self) -> CalibrationReport | None: ...
