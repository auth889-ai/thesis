"""Routing interfaces — Lab 22 (Dijkstra/A*, current-fastest, forecast-fastest,
time-dependent, system-optimal, then RL/MARL challengers such as URB/RouteRL)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..common.types import EdgeId, TrafficObservation, VehicleClass
from ..forecasting.interfaces import ForecastResult


@dataclass(frozen=True)
class RouteRequest:
    origin: EdgeId
    destination: EdgeId
    depart_time_s: float
    vehicle_class: VehicleClass = VehicleClass.CAR
    vehicle_id: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    """A chosen path plus the basis for choosing it (auditable by the copilot)."""

    edges: Sequence[EdgeId]
    estimated_travel_time_s: float
    estimated_distance_m: float | None = None
    strategy: str = "unknown"          # "shortest" | "current_fastest" | "forecast_fastest" | ...
    used_forecast: bool = False
    confidence: float | None = None
    diagnostics: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.edges:
            raise ValueError("a RouteDecision must contain at least one edge")
        if self.estimated_travel_time_s < 0:
            raise ValueError("estimated_travel_time_s must be >= 0")


@runtime_checkable
class Router(Protocol):
    """Uniform contract for every routing strategy in the benchmark."""

    def route(self, request: RouteRequest, observation: TrafficObservation | None = None,
              forecast: ForecastResult | None = None) -> RouteDecision: ...

    @property
    def name(self) -> str: ...

    @property
    def uses_forecast(self) -> bool: ...
