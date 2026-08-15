"""P-LIVE provider contracts — traffic, weather, camera. Provider-neutral.

Hard rules encoded here:

* Every observation carries a `Provenance` with a `RealityClass` — an unlabelled
  observation cannot be constructed.
* Google traffic data is an EXTERNAL_LIVE_REFERENCE: travel times and delays on
  routes. It is never a vehicle count, a queue length, or CV ground truth, and
  `TrafficEdgeState` has no fields that could be mistaken for those.
* Raw provider payloads and normalised states are persisted SEPARATELY — raw
  under `raw/`, normalised under `normalized/` — so reprocessing never requires
  a re-fetch and normalisation bugs are recoverable.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, Sequence, runtime_checkable

from ..common.reality import Provenance, RealityClass


# ---------------------------------------------------------------------------
# Normalised observation types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TrafficEdgeState:
    """Traffic-aware travel state on one OD corridor (NOT a count, NOT a queue)."""

    corridor_id: str
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    duration_s: float                    # traffic-aware
    static_duration_s: float             # free-flow per provider
    distance_m: float | None
    traffic_delay_s: float               # duration - static_duration
    speed_intervals: tuple = ()          # provider speed-reading intervals, verbatim
    route_ref: str = ""                  # polyline reference/hash, NOT the geometry
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            raise ValueError("TrafficEdgeState requires provenance — no unlabelled data")


@dataclass(frozen=True)
class WeatherState:
    """Current weather at a point — candidate exogenous forecasting variable.

    Stored now; may only be CLAIMED to help forecasting after an ablation
    (user mandate #2)."""

    lat: float
    lng: float
    temperature_c: float | None = None
    humidity_pct: float | None = None
    precipitation_mm: float | None = None
    precipitation_probability_pct: float | None = None
    precipitation_type: str | None = None
    visibility_km: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    cloud_cover_pct: float | None = None
    condition: str | None = None
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            raise ValueError("WeatherState requires provenance — no unlabelled data")


@dataclass(frozen=True)
class CameraFeedStatus:
    """Status of one camera feed from any commercial/public provider."""

    camera_id: str
    provider: str
    lat: float | None
    lng: float | None
    has_stream: bool
    freshness_s: float | None            # age of latest frame, None if unknown
    rights: Mapping[str, bool] = field(default_factory=dict)  # cv_processing, retention, public_demo
    provenance: Provenance | None = None

    def __post_init__(self) -> None:
        if self.provenance is None:
            raise ValueError("CameraFeedStatus requires provenance")


# ---------------------------------------------------------------------------
# Provider protocols
# ---------------------------------------------------------------------------

@runtime_checkable
class TrafficProvider(Protocol):
    def edge_state(self, corridor_id: str, origin: tuple[float, float],
                   dest: tuple[float, float]) -> TrafficEdgeState: ...
    @property
    def name(self) -> str: ...
    @property
    def enabled(self) -> bool: ...


@runtime_checkable
class WeatherProvider(Protocol):
    def current(self, lat: float, lng: float) -> WeatherState: ...
    @property
    def name(self) -> str: ...
    @property
    def enabled(self) -> bool: ...


@runtime_checkable
class CameraProvider(Protocol):
    def list_cameras(self, bbox: tuple[float, float, float, float]
                     ) -> Sequence[CameraFeedStatus]: ...
    @property
    def name(self) -> str: ...
    @property
    def enabled(self) -> bool: ...


# ---------------------------------------------------------------------------
# Split persistence: raw payloads and normalised states never share a file
# ---------------------------------------------------------------------------

class ObservationStore:
    """Append-only JSONL store, raw and normalised strictly separated."""

    def __init__(self, root: Path):
        self.raw_dir = root / "raw"
        self.norm_dir = root / "normalized"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.norm_dir.mkdir(parents=True, exist_ok=True)

    def append_raw(self, provider: str, payload: dict, captured_utc: str) -> Path:
        f = self.raw_dir / f"{provider}.jsonl"
        with open(f, "a") as fh:
            fh.write(json.dumps({"captured_utc": captured_utc,
                                 "payload": payload}) + "\n")
        return f

    def append_normalized(self, state) -> Path:
        d = asdict(state)
        d["_type"] = type(state).__name__
        f = self.norm_dir / f"{state.provenance.provider}.jsonl"
        with open(f, "a") as fh:
            fh.write(json.dumps(d, default=str) + "\n")
        return f


# ---------------------------------------------------------------------------
# Dhaka R1 corridors — real intersections of the frozen network
# ---------------------------------------------------------------------------

# OD pairs across the verified R1 region (bbox 23.723-23.762 / 90.372-90.408),
# named by the real places they connect. Coordinates are the public road
# junctions, not private locations.
DHAKA_R1_CORRIDORS: tuple[dict, ...] = (
    {"corridor_id": "farmgate_to_shahbagh",
     "origin": (23.7573, 90.3854), "dest": (23.7389, 90.3958)},
    {"corridor_id": "shahbagh_to_farmgate",
     "origin": (23.7389, 90.3958), "dest": (23.7573, 90.3854)},
    {"corridor_id": "karwanbazar_to_banglamotor",
     "origin": (23.7508, 90.3928), "dest": (23.7457, 90.3941)},
    {"corridor_id": "banglamotor_to_karwanbazar",
     "origin": (23.7457, 90.3941), "dest": (23.7508, 90.3928)},
    {"corridor_id": "farmgate_to_banglamotor",
     "origin": (23.7573, 90.3854), "dest": (23.7457, 90.3941)},
    {"corridor_id": "karwanbazar_to_shahbagh",
     "origin": (23.7508, 90.3928), "dest": (23.7389, 90.3958)},
)
