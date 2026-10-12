"""Core data types shared by every DhakaFlow subsystem.

These are deliberately *data*, not behaviour: any official paper implementation
(SUMO-RL, PressLight, CoLight, MAPPO, DCRNN, RT-DETR, ByteTrack, ...) can be
adapted to produce/consume these without inheriting from us.

Design rules
------------
1. Frozen dataclasses — observations and actions are values, never mutated in
   place by a controller.
2. Units are canonical (see units.py) and named in the field.
3. Every record carries enough provenance to be traceable to a run.
4. Nothing here imports SUMO, torch, or any heavy dependency.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

# Identifier aliases — plain strings, but named so signatures stay readable.
EdgeId = str
LaneId = str
JunctionId = str
DetectorId = str
VehicleId = str
RouteId = str


class VehicleClass(str, Enum):
    """Bangladesh-relevant fleet taxonomy.

    Chosen for Dhaka's heterogeneous traffic; the exact perception class list is
    fixed in Lab 03 (dataset audit) and mapped onto these classes by adapters.
    """

    CAR = "car"
    BUS = "bus"
    TRUCK = "truck"
    MOTORCYCLE = "motorcycle"
    CNG_AUTORICKSHAW = "cng_autorickshaw"
    RICKSHAW = "rickshaw"
    BICYCLE = "bicycle"
    PEDESTRIAN = "pedestrian"
    EMERGENCY = "emergency"
    OTHER = "other"


@dataclass(frozen=True)
class TrafficScenario:
    """A runnable scenario: network + infrastructure + demand + execution settings.

    Mirrors the scenario triple of Alvarez Lopez et al. (2018) §II, plus the
    reproducibility fields that make a run citable.
    """

    scenario_id: str
    network_path: str                      # SUMO .net.xml (or backend equivalent)
    route_path: str | None = None          # demand; None for demand-free checks
    additional_paths: Sequence[str] = ()   # detectors, bus stops, TLS overrides
    begin_s: float = 0.0
    end_s: float = 3600.0
    step_length_s: float = 1.0
    seed: int = 42
    warmup_s: float = 0.0                  # excluded from evaluation (Bologna §1.5)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.end_s <= self.begin_s:
            raise ValueError("end_s must be greater than begin_s")
        if self.step_length_s <= 0:
            raise ValueError("step_length_s must be > 0")
        if self.warmup_s < 0 or self.warmup_s >= (self.end_s - self.begin_s):
            raise ValueError("warmup_s must be >= 0 and shorter than the run")

    @property
    def evaluation_window_s(self) -> tuple[float, float]:
        """(start, end) of the window that counts scientifically."""
        return (self.begin_s + self.warmup_s, self.end_s)


@dataclass(frozen=True)
class LaneState:
    """Per-lane instantaneous state — the atom of every observation."""

    lane_id: LaneId
    queue_length_veh: float = 0.0        # halting vehicles
    queue_length_m: float = 0.0
    vehicle_count: int = 0
    mean_speed_ms: float = 0.0
    occupancy: float = 0.0               # fraction [0, 1]
    waiting_time_s: float = 0.0
    class_counts: Mapping[VehicleClass, int] = field(default_factory=dict)


@dataclass(frozen=True)
class TrafficObservation:
    """What any sensor or simulator reports at one instant.

    The same type is produced by the SUMO backend (Lab 01) and by the
    camera-derived sensor layer (Lab 06), which is what makes sim-vs-real
    comparison (Lab 13) and sim2real controller transfer (Lab 21) meaningful.
    """

    time_s: float
    lanes: Mapping[LaneId, LaneState] = field(default_factory=dict)
    signal_states: Mapping[JunctionId, str] = field(default_factory=dict)  # e.g. "GGrr"
    vehicles_running: int = 0
    vehicles_arrived: int = 0
    source: str = "unknown"              # "sumo" | "camera" | "detector" | ...
    metadata: Mapping[str, str] = field(default_factory=dict)

    def queue_total(self) -> float:
        """Total halting vehicles across observed lanes."""
        return sum(l.queue_length_veh for l in self.lanes.values())

    def lanes_of(self, lane_ids: Sequence[LaneId]) -> list[LaneState]:
        """Subset helper for controllers that own specific approaches."""
        return [self.lanes[l] for l in lane_ids if l in self.lanes]


@dataclass(frozen=True)
class TrafficMetrics:
    """Outcome metrics for one evaluated run.

    The transport metrics — not ML accuracy — are how the final system is judged.
    Optional fields stay None when a run cannot observe them; a missing metric is
    never silently reported as 0.
    """

    scenario_id: str
    seed: int
    # core transport outcomes
    throughput_veh: int = 0
    avg_travel_time_s: float | None = None
    p95_travel_time_s: float | None = None
    avg_waiting_time_s: float | None = None
    avg_time_loss_s: float | None = None
    mean_queue_veh: float | None = None
    p95_queue_veh: float | None = None
    max_queue_veh: float | None = None
    avg_stops: float | None = None
    spillback_fraction: float | None = None
    emissions_co2_mg: float | None = None
    # multi-modal / equity outcomes
    bus_passenger_delay_s: float | None = None
    pedestrian_delay_s: float | None = None
    emergency_response_time_s: float | None = None
    # integrity counters — a run with these non-zero is suspect, not a result
    collisions: int = 0
    teleports: int = 0
    safety_violations: int = 0
    # provenance
    proxy_metrics: Sequence[str] = ()     # names above that are proxies, not exact
    metadata: Mapping[str, str] = field(default_factory=dict)

    def is_clean(self) -> bool:
        """True when nothing invalidates the run (Lab 01 acceptance rule)."""
        return self.collisions == 0 and self.safety_violations == 0
