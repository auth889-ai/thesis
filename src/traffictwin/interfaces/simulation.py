"""Simulation backend interface — GRADUATED FROM LAB 01.

Lab 01 proved this contract against SUMO 1.27.1 via TraCI (start → step → close,
seeded and deterministic, 15/15 clean runs). Any other backend (CityFlow,
LibSignal, a replay of recorded data) may satisfy the same protocol.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from traffictwin.common.types import JunctionId, TrafficObservation, TrafficScenario


@runtime_checkable
class SimulationBackend(Protocol):
    """Minimal lifecycle every simulator must expose.

    Contract (validated in Lab 01):
      * `reset(scenario)` fully re-initialises; two resets with the same
        scenario+seed must produce identical trajectories.
      * `step()` advances exactly `scenario.step_length_s` and returns the new
        observation.
      * `close()` is idempotent and releases the process/socket.
    """

    def reset(self, scenario: TrafficScenario) -> TrafficObservation: ...

    def step(self) -> TrafficObservation: ...

    def close(self) -> None: ...

    @property
    def time_s(self) -> float: ...

    @property
    def is_running(self) -> bool: ...


@runtime_checkable
class SignalActuator(Protocol):
    """Write-side of a simulator: how a controller changes signals.

    Deliberately separated from SimulationBackend so a SafetyShield can wrap the
    actuator without wrapping the whole simulator.
    """

    def signal_state(self, junction: JunctionId) -> str: ...

    def phase_index(self, junction: JunctionId) -> int: ...

    def set_phase(self, junction: JunctionId, phase_index: int) -> None: ...

    def set_phase_duration(self, junction: JunctionId, duration_s: float) -> None: ...

    def controlled_lanes(self, junction: JunctionId) -> list[str]: ...
