"""One interface every forecasting model answers to.

    forecast(city_data, model, horizons) -> Forecast

The audit's finding was that the runtime never called a real model: the Prediction page ran an
empirical transition model over four congestion classes and the trained networks sat unreachable in
a research page. This is the seam that fixes it. STAEformer, Graph WaveNet, STID and OpenCity all
implement `ForecastAdapter`, so the runtime asks for a forecast without knowing which family of
model answers, and every answer carries the same provenance.

Two rules the interface enforces, because both were violated before:

  * A forecast returns NUMERIC VALUES, not an ordinal class. "It will stay CONGESTED" is not a
    forecast, it is a restatement of the present.
  * An adapter that cannot honestly serve a request REFUSES it. `check(city_data)` returns the
    gate result and `forecast` raises `NotAvailable` rather than returning a number that has no
    standing. A model run outside its input schema is worse than no model, because the output
    looks the same.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


class NotAvailable(RuntimeError):
    """Raised when a model cannot honestly serve this city's data. Carries the reasons."""

    def __init__(self, model: str, reasons: list[str]):
        self.model, self.reasons = model, reasons
        super().__init__(f"{model} cannot serve this request: " + "; ".join(reasons))


@dataclass
class CityData:
    """The input contract: a T x N x F tensor over STABLE observation nodes, plus topology.

    This is deliberately the same shape every spatio-temporal model in the field expects, which is
    what lets one city be served by four different model families without special cases.
    """
    city_id: str
    node_ids: list[str]
    values: "list | object"            # (T, N) or (T, N, F); numpy array in practice
    adjacency: "list | object | None" = None
    interval_s: int = 300
    target: str = "speed"
    unit: str = "m/s"
    timestamps: list[str] = field(default_factory=list)
    reality: str = "REAL"

    @property
    def shape(self) -> tuple:
        try:
            return tuple(self.values.shape)
        except AttributeError:
            return (len(self.values), len(self.node_ids))

    def describe(self) -> dict:
        return {"city_id": self.city_id, "shape": list(self.shape), "nodes": len(self.node_ids),
                "interval_s": self.interval_s, "target": self.target, "unit": self.unit,
                "reality": self.reality,
                "first_utc": self.timestamps[0] if self.timestamps else None,
                "last_utc": self.timestamps[-1] if self.timestamps else None}


@dataclass
class Forecast:
    """What the runtime must be able to show for any prediction, per the audit."""
    model: str
    checkpoint: str | None
    dataset_schema: str
    input_window_steps: int
    output_horizon_steps: int
    horizons_min: list[int]
    values: dict                      # {horizon_min: [value per node]}
    unit: str
    node_ids: list[str]
    inference_utc: str
    city_id: str
    is_baseline: bool = False
    provenance: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class ForecastAdapter(ABC):
    """Implemented by every model family. The runtime only ever sees this."""

    name: str = "abstract"
    is_baseline: bool = False

    @abstractmethod
    def check(self, city_data: CityData) -> dict:
        """Can this model honestly serve this data? Returns {'ok': bool, 'reasons': [...]}"""

    @abstractmethod
    def forecast(self, city_data: CityData, horizons_min: list[int]) -> Forecast:
        """Numeric forecast per node per horizon. Raises NotAvailable when `check` fails."""

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def describe(self) -> dict:
        return {"model": self.name, "is_baseline": self.is_baseline,
                "class": type(self).__name__}
