"""Perception interfaces — camera → detections → tracks → traffic measurements.

Targets Labs 04 (detection), 05 (tracking) and 06 (sensor layer). Official
implementations (RT-DETR family, ByteTrack) are wrapped by adapters that satisfy
these protocols; no algorithm lives here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

from app.common.types import LaneId, TrafficObservation, VehicleClass


@dataclass(frozen=True)
class BoundingBox:
    """Pixel-space box, top-left origin."""

    x: float
    y: float
    width: float
    height: float

    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)


@dataclass(frozen=True)
class Detection:
    """One detected object in one frame."""

    box: BoundingBox
    vehicle_class: VehicleClass
    confidence: float
    frame_index: int
    timestamp_s: float
    class_name_raw: str = ""      # dataset-native label before taxonomy mapping


@dataclass(frozen=True)
class Track:
    """A detection sequence associated over time by a tracker."""

    track_id: int
    vehicle_class: VehicleClass
    detections: Sequence[Detection] = ()
    first_seen_s: float = 0.0
    last_seen_s: float = 0.0
    lane_id: LaneId | None = None          # after homography/lane assignment
    mean_speed_ms: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def duration_s(self) -> float:
        return max(self.last_seen_s - self.first_seen_s, 0.0)


@runtime_checkable
class Detector(Protocol):
    """Frame → detections (Lab 04)."""

    def detect(self, frame, frame_index: int, timestamp_s: float) -> Sequence[Detection]: ...

    @property
    def class_names(self) -> Sequence[str]: ...


@runtime_checkable
class Tracker(Protocol):
    """Detections → persistent tracks (Lab 05)."""

    def update(self, detections: Sequence[Detection], timestamp_s: float) -> Sequence[Track]: ...

    def reset(self) -> None: ...


@runtime_checkable
class TrafficSensor(Protocol):
    """Tracks → traffic measurements (Lab 06).

    This is the bridge that makes camera data comparable with simulator output:
    it emits the SAME TrafficObservation type the SUMO backend emits, so the
    digital twin (Lab 13) can compare real vs simulated directly.
    """

    def observe(self, tracks: Sequence[Track], window_start_s: float,
                window_end_s: float) -> TrafficObservation: ...

    def turning_movements(self, tracks: Sequence[Track]) -> Mapping[tuple[str, str], int]: ...
