"""Forecasting interfaces — Labs 07-12 (baselines, DCRNN, Graph WaveNet, STID,
STAEformer, Chronos-2) all plug in here and are compared on ONE leaderboard.

No model is implemented in the platform; adapters wrap official code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class ForecastRequest:
    """What to predict, from what history."""

    node_ids: Sequence[str]                 # detector/lane/edge identifiers
    history_values: Sequence[Sequence[float]]   # [T_hist][N] canonical units
    history_timestamps_s: Sequence[float]
    horizons_s: Sequence[float] = (300.0, 900.0, 1800.0)   # 5 / 15 / 30 min
    target_variable: str = "flow_vph"
    exogenous: Mapping[str, Sequence[float]] = field(default_factory=dict)  # incidents, weather


@dataclass(frozen=True)
class ForecastResult:
    """Point predictions plus optional uncertainty.

    `uncertainty` is first-class because Lab 20 (Forecast-Aware MAPPO) must be
    able to test whether forecast *uncertainty* — not just the point forecast —
    improves control. A model without uncertainty returns None, never zeros.
    """

    node_ids: Sequence[str]
    horizons_s: Sequence[float]
    values: Sequence[Sequence[float]]           # [H][N]
    uncertainty: Sequence[Sequence[float]] | None = None   # [H][N] std or interval width
    model_name: str = "unknown"
    issued_at_s: float = 0.0
    metadata: Mapping[str, str] = field(default_factory=dict)

    def horizon_index(self, horizon_s: float) -> int:
        try:
            return list(self.horizons_s).index(horizon_s)
        except ValueError as exc:
            raise KeyError(f"horizon {horizon_s}s not produced by {self.model_name}") from exc


@runtime_checkable
class TrafficForecaster(Protocol):
    """Uniform contract for every forecasting model in the benchmark.

    Fairness rules enforced by the benchmark harness, not by the model:
    identical data, identical chronological splits, identical horizons, identical
    metrics. `fit` may be a no-op for zero-shot foundation models.
    """

    def fit(self, request: ForecastRequest, targets: Sequence[Sequence[float]]) -> None: ...

    def predict(self, request: ForecastRequest) -> ForecastResult: ...

    @property
    def name(self) -> str: ...

    @property
    def supports_uncertainty(self) -> bool: ...
