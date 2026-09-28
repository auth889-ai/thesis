"""Schemas and compliance helpers for the real-time route-advice pilot."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GOOGLE_DATA_MODE = "RUNTIME_REFERENCE"
ROUTE_CONTENT_PERSISTED = False
GOOGLE_CONTENT_KEYS = {
    "duration",
    "duration_s",
    "staticDuration",
    "static_duration_s",
    "distanceMeters",
    "distance_m",
    "polyline",
    "encodedPolyline",
    "speedReadingIntervals",
    "route_geometry",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_ref(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def coord_ref(lat: float, lng: float) -> str:
    """Hash rounded public-road coordinates for privacy-preserving persistence."""
    return stable_ref(f"{lat:.5f},{lng:.5f}")


def parse_lat_lng(value: str) -> tuple[float, float]:
    try:
        lat_s, lng_s = value.split(",", 1)
        lat, lng = float(lat_s.strip()), float(lng_s.strip())
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"expected 'lat,lng', got {value!r}") from exc
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise ValueError(f"coordinate out of range: {value!r}")
    return lat, lng


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def assert_no_google_content(row: dict[str, Any]) -> None:
    text = json.dumps(row, sort_keys=True)
    bad = [key for key in GOOGLE_CONTENT_KEYS if key in row or key in text]
    if bad:
        raise ValueError(f"persisted Google route content keys are forbidden: {bad}")
    if row.get("route_content_persisted") is not False:
        raise ValueError("route_content_persisted must be false")
    if row.get("google_data_mode") != GOOGLE_DATA_MODE:
        raise ValueError(f"google_data_mode must be {GOOGLE_DATA_MODE}")


@dataclass(frozen=True)
class RouteQuery:
    origin: tuple[float, float]
    dest: tuple[float, float]
    label: str = "custom"

    @property
    def origin_ref(self) -> str:
        return coord_ref(*self.origin)

    @property
    def dest_ref(self) -> str:
        return coord_ref(*self.dest)


@dataclass(frozen=True)
class RuntimeRouteOption:
    """Transient route option. Do not serialize this object to evidence files."""

    rank: int
    duration_s: float
    static_duration_s: float
    distance_m: float | None
    route_ref: str
    congestion_state: str


@dataclass(frozen=True)
class AdviceRecord:
    advice_id: str
    captured_utc: str
    provider: str
    reality: str
    query_label: str
    origin_ref: str
    dest_ref: str
    route_count: int
    recommended_rank: int
    recommended_congestion_state: str
    scoring_policy: str
    google_data_mode: str = GOOGLE_DATA_MODE
    route_content_persisted: bool = ROUTE_CONTENT_PERSISTED
    honesty_label: str = "REAL_RUNTIME_ADVICE_NO_GOOGLE_ROUTE_CONTENT_STORED"

    def persistable(self) -> dict[str, Any]:
        row = asdict(self)
        assert_no_google_content(row)
        return row

