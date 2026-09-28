"""Evaluation interfaces — metrics computation and the fair-benchmark contract.

GRADUATED FROM LAB 00 (traffic-science metric definitions, MFD/critical point)
and LAB 01 (transport metric set + multi-seed benchmark harness that produced
the validated 5-seed matrix).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

from app.common.types import TrafficMetrics, TrafficObservation, TrafficScenario


@runtime_checkable
class MetricsComputer(Protocol):
    """Turns raw run artifacts into a TrafficMetrics record.

    Implementations must mark proxy metrics via `TrafficMetrics.proxy_metrics`
    (Lab 01 precedent: stops = waitingCount proxy, spillback = queue-ratio proxy).
    """

    def compute(self, scenario: TrafficScenario,
                observations: Sequence[TrafficObservation],
                artifacts: Mapping[str, str] | None = None) -> TrafficMetrics: ...

    @property
    def proxy_metric_names(self) -> Sequence[str]: ...


@dataclass(frozen=True)
class BenchmarkSpec:
    """Fair-comparison contract — the conditions every arm must share.

    Enforced by the harness, not by trust: `assert_fair` refuses to compare arms
    whose scenario, seeds, warmup, duration, horizons or metrics differ.
    """

    benchmark_id: str
    scenario_ids: Sequence[str]
    seeds: Sequence[int]
    warmup_s: float = 0.0
    duration_s: float = 3600.0
    metrics: Sequence[str] = ("avg_travel_time_s", "p95_travel_time_s",
                              "avg_waiting_time_s", "mean_queue_veh",
                              "p95_queue_veh", "throughput_veh")
    forecast_horizons_s: Sequence[float] = ()
    safety_constraints_id: str = "default"
    notes: str = ""

    def assert_fair(self, arms: Mapping[str, "ArmSetup"]) -> None:
        """Raise if any arm deviates from the shared conditions."""
        problems: list[str] = []
        for name, arm in arms.items():
            if tuple(arm.scenario_ids) != tuple(self.scenario_ids):
                problems.append(f"{name}: different scenarios")
            if tuple(arm.seeds) != tuple(self.seeds):
                problems.append(f"{name}: different seeds")
            if arm.warmup_s != self.warmup_s:
                problems.append(f"{name}: different warmup")
            if arm.duration_s != self.duration_s:
                problems.append(f"{name}: different duration")
            if arm.safety_constraints_id != self.safety_constraints_id:
                problems.append(f"{name}: different safety constraints")
        if problems:
            raise ValueError("unfair benchmark configuration: " + "; ".join(problems))


@dataclass(frozen=True)
class ArmSetup:
    """One competitor in a benchmark (a controller, router or forecaster)."""

    name: str
    component_category: str            # "controller" | "router" | "forecaster"
    component_name: str                # registry key
    scenario_ids: Sequence[str] = ()
    seeds: Sequence[int] = ()
    warmup_s: float = 0.0
    duration_s: float = 3600.0
    safety_constraints_id: str = "default"
    config: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkResult:
    """Per-arm, per-seed outcomes plus the spec they were produced under."""

    spec: BenchmarkSpec
    per_arm: Mapping[str, Sequence[TrafficMetrics]] = field(default_factory=dict)
    provenance: Mapping[str, str] = field(default_factory=dict)

    def clean(self) -> bool:
        """True only if every run in every arm is free of collisions/violations."""
        return all(m.is_clean() for runs in self.per_arm.values() for m in runs)


@runtime_checkable
class Benchmark(Protocol):
    """Runs all arms under identical conditions and returns comparable results."""

    def run(self, spec: BenchmarkSpec, arms: Mapping[str, ArmSetup]) -> BenchmarkResult: ...
