"""A city, as one tracked file: config/cities/<city_id>.yaml.

Everything that differs between cities lives there — the area, the time zone, the languages, the emergency
numbers, the units, the vehicle classes, the optional plugins, the datasets and the SUMO network. Code asks this
module; it does not name a city.

Every key must be present in the file. A value nobody has sourced is written as `null`, so "unknown" is a statement
in the file and a missing key is an error, never a silent default.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from core.common.paths import REPO

CONFIG_DIR = REPO / "config/cities"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BoundingBox(_Strict):
    south: float
    west: float
    north: float
    east: float
    source: str

    @model_validator(mode="after")
    def _ordered(self):
        if not (self.south < self.north and self.west < self.east):
            raise ValueError("bounding_box needs south < north and west < east")
        return self

    @property
    def tuple(self) -> tuple[float, float, float, float]:
        return (self.south, self.west, self.north, self.east)


class Units(_Strict):
    speed: Literal["km/h", "mph"]
    distance: Literal["km", "mi"]


class Dataset(_Strict):
    id: str
    kind: str
    source: str


class Prebuilt(_Strict):
    """A network that already exists and must not be rebuilt (its results depend on these exact files)."""
    network_id: str
    network: str                 # repo-relative path
    network_sha256: str          # of the uncompressed .net.xml
    routes: str
    routes_sha256: str           # of the file as stored
    demand_scale: float


class Build(_Strict):
    """Random demand for a network built from the bounding box."""
    seed: int
    period_s: float
    horizon_s: int


class Sumo(_Strict):
    """`prebuilt` alone: an existing network and demand, kept to reproduce old results. `build` alone: network and
    demand generated from the bounding box. Both: the existing network with newly generated demand."""
    prebuilt: Optional[Prebuilt]
    build: Optional[Build]


class RealSource(_Strict):
    """A source of measured road speeds or counts for this city, and whether it can be read yet. `recorded` is a
    published dataset of past measurements: it is shown with its date and never as the present."""
    kind: Literal["pems", "field_counts", "recorded"]
    status: Literal["pending", "active"]
    note: str                    # what is missing, or where the data is
    stations: Optional[str]      # where the station positions come from, when the source has stations
    dataset: Optional[str] = None    # for `recorded`: the reader in app/data/recorded/ that knows this dataset
    citation: Optional[str] = None   # the credit the dataset's licence requires, shown beside its data
    licence: Optional[str] = None


class VehicleShare(_Strict):
    name: str                    # the class as its source names it
    share_pct: float
    sumo_class: str              # the SUMO vehicle class it is simulated as; SUMO's own defaults for that class are used


class VehicleMix(_Strict):
    """Which kinds of vehicle are on this city's roads and in what shares, with where that was counted."""
    source: str
    citation: str
    counted: str                 # what was counted, where and when, and by what
    simulated_as: str            # how the classes are turned into SUMO vehicles, and what is not modelled
    classes: list[VehicleShare]

    @model_validator(mode="after")
    def _whole(self):
        if abs(sum(c.share_pct for c in self.classes) - 100.0) > 0.1:
            raise ValueError("vehicle_mix shares must sum to 100")
        return self


class Calibration(_Strict):
    """Which recorded counts this city's generated demand is fitted to with SUMO's routeSampler, and for which
    clock window. Only the road sections the dataset's located sites measure are fitted; the rest stays uncalibrated."""
    dataset: str                 # a reader in app/data/recorded/ that publishes counts per site and interval
    window_start: str            # "HH:MM" on each site's own recording day
    duration_s: int
    interval_s: int              # the dataset's counting interval
    seed: int
    pool_period_s: float         # one candidate route every this many seconds from randomTrips.py, for routeSampler to choose from
    pool_fringe_factor: str      # randomTrips --fringe-factor for the candidates: how strongly they start and end at the network's edge ("max": only there)


class Place(_Strict):
    lat: float
    lon: float
    source: str                  # what the place is and where its position was read


class Emergency(_Strict):
    """The one ambulance trip the alert experiments drive on this city's twin. A city without it has no such run."""
    origin: Place
    destination: Place


class Live(_Strict):
    real_sources: Optional[list[RealSource]]


class Routing(_Strict):
    """Whole-city routing on our own Valhalla server built from an OpenStreetMap extract (third_party/SOURCES.md,
    "Whole-city routing"). The server's address comes from the environment variable `url_env`, never from this file."""
    engine: Literal["valhalla"]
    url_env: str
    extract: str                 # the Geofabrik path, e.g. asia/bangladesh
    extract_date: str            # the data date the download page stated
    credit: str                  # shown with every route
    travelmux_url_env: str | None = None   # the map app's directions (Headway's travelmux, unchanged, in front of url_env's Valhalla); the address is in the environment


class ForecastLayer(_Strict):
    """The map's forecast layer (core/ml/forecasting/layer/service.py). `replay`: recorded sensor speeds replayed at the same
    weekday and time, with a trained model's forecast made at that moment (`file`, built by layer/build_la.py). `recorded_day`:
    each recorded site at this hour on its one recorded day (DhaTraX). Absent or null: "no data for this city"."""
    kind: Literal["replay", "recorded_day"]
    dataset: str
    file: Optional[str] = None           # replay only: the built layer file, relative to the repository
    summary: Optional[str] = None        # the results file that holds the layer's model card


class LiveTwin(_Strict):
    """The live twin with forecasters in the loop (core/simulation/live_twin). Paths relative to the repository. Detectors (E1 loops)
    are generated on every lane of the roads of these OpenStreetMap types at least `detector_min_edge_m` long. Absent or null:
    "no data for this city"."""
    net: str
    routes: str
    demand_label: str                     # what the demand is, said with every result
    detector_road_types: list[str]        # OSM highway types, e.g. [trunk, primary, secondary]
    detector_min_edge_m: float = 50.0
    demand_scale: float = 1.0             # the base SUMO --scale; the viewer's slider multiplies it


class CityConfig(_Strict):
    city_id: str
    display_name: dict[str, str]
    country: Optional[str]
    bounding_box: Optional[BoundingBox]
    time_zone: Optional[str]
    default_languages: Optional[list[str]]
    emergency_numbers: Optional[dict[str, Optional[str]]]
    units: Optional[Units]
    drive_side: Optional[Literal["left", "right"]]
    vehicle_classes: Optional[list[str]]
    plugins: list[str]
    datasets: list[Dataset]
    sumo: Sumo
    vehicle_mix: Optional[VehicleMix] = None     # absent or null: no mix has been sourced; every vehicle is one class
    calibration: Optional[Calibration] = None    # absent or null: the demand is uncalibrated
    emergency: Optional[Emergency] = None        # absent or null: no ambulance trip is defined, so the alert experiments refuse this city
    live: Optional[Live] = None     # absent or null: no real source beyond opt-in phones is declared for this city
    routing: Optional[Routing] = None    # absent or null: no whole-city routing; trips run on the SUMO box only
    forecast_layer: Optional[ForecastLayer] = None    # absent or null: the map says "no data for this city"
    live_twin: Optional[LiveTwin] = None      # absent or null: the live twin says "no data for this city"

    @property
    def center(self) -> tuple[float, float] | None:
        """(lon, lat) of the middle of the box, or None when the box is unknown."""
        b = self.bounding_box
        return None if b is None else (round((b.west + b.east) / 2, 6), round((b.south + b.north) / 2, 6))

    def label(self, language: str = "en") -> str:
        return self.display_name.get(language) or next(iter(self.display_name.values()))


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def list_ids(directory: Path = CONFIG_DIR) -> list[str]:
    return sorted(p.stem for p in Path(directory).glob("*.yaml"))


def load(city_id: str, directory: Path = CONFIG_DIR) -> CityConfig:
    path = Path(directory) / f"{city_id}.yaml"
    if not path.exists():
        raise KeyError(f"no config for city {city_id!r}: expected {path}; configured: {list_ids(directory)}")
    cfg = CityConfig(**yaml.safe_load(path.read_text()))
    if cfg.city_id != city_id:
        raise ValueError(f"{path.name} declares city_id {cfg.city_id!r}")
    return cfg


def default() -> CityConfig:
    """The deployment's default city (TRAFFICTWIN_DEFAULT_CITY), through its config."""
    from core.common.settings import DEFAULT_CITY
    return load(slug(DEFAULT_CITY))
