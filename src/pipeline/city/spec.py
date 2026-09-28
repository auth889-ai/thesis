"""What a city IS in this system, and what it is allowed to claim.

The old architecture was `DHAKA -> twelve corridors -> empirical transition`. Every part of that
was a constant, so the application could only ever be as large as the constants. This module is the
first half of the replacement:

    CITY -> ROAD GRAPH -> STABLE NODES -> DATA ADAPTER -> MODEL CAPABILITY -> FORECAST

A `CitySpec` is a description, not a promise. Any city on earth can be instantiated as software —
a name and a bounding box are enough to build a road graph. What a city may *claim* is decided
separately, by `CityCapabilities`, from the data that actually exists for it. That separation is
the point: instantiating Dhaka must not imply we can forecast Dhaka.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


class Capability(str, Enum):
    """What a city is entitled to do, in increasing order of evidence required."""

    LIVE_ONLY = "LIVE_ONLY"
    """A live traffic provider answers for this city. Current conditions only — no forecast.
    Honest default for a city with no historical sensor data."""

    SIMULATION_ONLY = "SIMULATION_ONLY"
    """A SUMO network exists, so counterfactuals can be run, but there is no live feed and no
    validated forecast. Model outputs, never road measurements."""

    ZERO_SHOT = "ZERO_SHOT"
    """A historical dataset exists in a schema a pre-trained foundation model accepts, AND the city
    is absent from that model's pre-training corpus. Only then is 'zero-shot' truthful."""

    FINE_TUNED = "FINE_TUNED"
    """A foundation model has been adapted on this city's own training split."""

    FULL_FORECAST = "FULL_FORECAST"
    """A city-specific model was trained and evaluated on this city's data under a published
    protocol. The strongest claim available."""


ORDER = [Capability.LIVE_ONLY, Capability.SIMULATION_ONLY, Capability.ZERO_SHOT,
         Capability.FINE_TUNED, Capability.FULL_FORECAST]


@dataclass
class CityCapabilities:
    """Derived from evidence, never asserted by hand.

    Each field answers a question with a fact, and `granted` is computed from those facts. A city
    with a live feed and nothing else gets LIVE_ONLY, and the interface must show that rather than
    inventing a forecast.
    """
    has_live_provider: bool = False
    has_sumo_network: bool = False
    has_historical_dataset: bool = False
    dataset_nodes: int | None = None
    dataset_timesteps: int | None = None
    in_foundation_pretraining: bool | None = None   # None = unknown, not False
    schema_satisfies_foundation: bool | None = None  # does the data fit the model's input gates?
    foundation_model: str | None = None
    city_specific_models: list[str] = field(default_factory=list)
    reproduction_verdict: str | None = None
    blocking: list[str] = field(default_factory=list)

    @property
    def granted(self) -> list[Capability]:
        out: list[Capability] = []
        if self.has_live_provider:
            out.append(Capability.LIVE_ONLY)
        if self.has_sumo_network:
            out.append(Capability.SIMULATION_ONLY)
        # Zero-shot needs BOTH: the city absent from the pre-training corpus, and data that
        # actually satisfies the model's input schema. Held out but too small is still unusable,
        # and claiming otherwise is how a foundation model gets run on 12 corridors.
        if (self.has_historical_dataset and self.in_foundation_pretraining is False
                and self.schema_satisfies_foundation is not False):
            out.append(Capability.ZERO_SHOT)
        if self.has_historical_dataset and self.foundation_model and self.reproduction_verdict:
            if "FINE" in (self.reproduction_verdict or "").upper():
                out.append(Capability.FINE_TUNED)
        if self.city_specific_models:
            out.append(Capability.FULL_FORECAST)
        return out

    @property
    def best(self) -> Capability:
        g = self.granted
        return max(g, key=ORDER.index) if g else Capability.LIVE_ONLY

    def explain(self) -> dict:
        return {
            "granted": [c.value for c in self.granted],
            "best": self.best.value,
            "live_traffic": self.has_live_provider,
            "simulation": self.has_sumo_network,
            "historical_dataset": self.has_historical_dataset,
            "dataset_nodes": self.dataset_nodes,
            "dataset_timesteps": self.dataset_timesteps,
            "in_foundation_pretraining": self.in_foundation_pretraining,
            "schema_satisfies_foundation": self.schema_satisfies_foundation,
            "foundation_model": self.foundation_model,
            "city_specific_models": self.city_specific_models,
            "reproduction_verdict": self.reproduction_verdict,
            "blocking": self.blocking,
            "zero_shot_note": (
                "zero-shot requires the city to be ABSENT from the foundation model's "
                "pre-training corpus; a city inside it can never support the claim"),
        }


@dataclass
class CitySpec:
    """A city as a first-class object. Nothing here is Dhaka-specific."""
    city_id: str
    display_name: str
    country: str = ""
    timezone: str = "UTC"
    bbox: tuple[float, float, float, float] | None = None   # south, west, north, east
    center: tuple[float, float] | None = None               # lat, lon
    drive_side: str = "right"
    osm_graph: str | None = None          # path to a cached graph, if built
    sumo_network: str | None = None       # path to a .net.xml, if built
    traffic_provider: str | None = None   # e.g. "google_routes"
    dataset_adapter: str | None = None    # registered dataset key, if one exists
    forecast_capability: str = Capability.LIVE_ONLY.value
    source: str = "manual"                # manual | geocoded | bbox | dataset
    created_utc: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bbox"] = list(self.bbox) if self.bbox else None
        d["center"] = list(self.center) if self.center else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CitySpec":
        d = dict(d)
        if d.get("bbox"):
            d["bbox"] = tuple(d["bbox"])
        if d.get("center"):
            d["center"] = tuple(d["center"])
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=1))
