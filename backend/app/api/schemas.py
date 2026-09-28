"""Response contracts for the whole API (Pydantic v2).

One file because the models are small and mutually referential; splitting seven of them
across seven packages made the import graph harder to read than the models themselves.
"""



from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field



Reality = Literal["REAL_LIVE", "REAL", "SIMULATED", "SYNTHETIC_WHAT_IF", "UNKNOWN"]


class Provenance(BaseModel):
    """Attached to every payload so the UI can never imply more than the evidence supports."""
    source_file: str = Field(description="repo-relative file this was read from")
    command: str = Field(description="the command that regenerates it")
    reality: Reality = "UNKNOWN"
    note: str | None = None


class Envelope(BaseModel):
    """Base of every response: either data with provenance, or an honest, actionable empty state."""
    available: bool
    provenance: Provenance | None = None
    missing: str | None = None
    command: str | None = None


CongestionState = Literal["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE", "NO DATA"]


class Corridor(BaseModel):
    id: str
    name: str
    level: float | None
    state: CongestionState
    edges: int = 0
    path_km: float | None = None
    origin: tuple[float, float] | None = None
    dest: tuple[float, float] | None = None


class SeriesPoint(BaseModel):
    t: int
    v: float | None


class CorridorSeries(BaseModel):
    name: str
    points: list[SeriesPoint]


class RecorderHealth(BaseModel):
    """Freshness is part of the data. A dashboard showing stale numbers as live is worse than a blank one."""
    ticks: int = 0
    rows_ok: int = 0
    rows_failed: int = 0
    last_tick_utc: str | None = None
    interval_s: int | None = None
    age_minutes: float | None = None
    healthy: bool = False


class TrafficResponse(Envelope):
    corridors: list[Corridor] = []
    series: list[CorridorSeries] = []
    level_counts: dict[str, int] = {}
    bins: int = 0
    coverage: float = 0.0
    span_hours: float | None = None
    recorder: RecorderHealth | None = None


class HorizonMetric(BaseModel):
    minutes: int
    mae: float
    rmse: float
    mape_pct: float
    published_mae: float | None = None
    diff_pct: float | None = None


class TrainedModel(BaseModel):
    model: str
    dataset: str
    paper: str | None = None
    epochs: int | None = None
    gpu: str | None = None
    horizons: list[HorizonMetric]


class Verification(BaseModel):
    """Proof the saved checkpoint IS the model that was scored."""
    minutes: int
    reloaded_mae: float
    reported_mae: float | None
    diff_pct: float | None
    windows: int


class InferenceSample(BaseModel):
    horizon_min: int
    sensor_index: int | str
    actual_mph: float | None
    predicted_mph: float | None
    abs_error_mph: float | None


class InferenceRun(BaseModel):
    model: str
    dataset: str
    checkpoint: str
    verification: list[Verification] = []
    samples: list[InferenceSample] = []


class FieldPosition(BaseModel):
    key: str
    band: str
    gap_to_sota_pct: float
    beats: list[str]


class ForecastResponse(Envelope):
    models: list[TrainedModel] = []
    inference: list[InferenceRun] = []
    floors: dict[str, dict[str, dict[str, float]]] = {}
    field_position: list[FieldPosition] = []
    gate_passed: bool | None = None


class RoutingArm(BaseModel):
    arm: str
    vehicle_hours: float
    sd: float = 0.0
    seeds: int | None = None
    arrived: float | None = None
    teleports: float | None = None
    change_pct: float | None = None


class Decision(BaseModel):
    decision: str
    reason: str
    rule: str | None = None
    per_seed_pct: list[float] = []
    reality: Reality = "UNKNOWN"


class SweepPoint(BaseModel):
    compliance: float
    decision: str
    mean_pct: float | None


class RoutingResponse(Envelope):
    arms: list[RoutingArm] = []
    baseline: float | None = None
    horizon_s: int | None = None
    decision: Decision | None = None
    sweep: list[SweepPoint] = []
    demand_label: str | None = None


class IncidentArm(BaseModel):
    arm: str
    vehicle_hours_pct: float | None = None
    affected_travel_time_pct: float | None = None
    seeds_improved: str | None = None


class SimulationResponse(Envelope):
    verdict: str | None = None
    event: str | None = None
    arms: list[IncidentArm] = []
    media: list[str] = []


class PenetrationPoint(BaseModel):
    penetration: float
    seeds: int
    delivery_ratio: float | None
    latency_ms: float | None
    route_switches: float | None
    travel_time_s: float | None


class NetworkResponse(Envelope):
    stack: str | None = None
    penetration: list[PenetrationPoint] = []
    latency_loss: list[dict] = []


class GateCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class EvidenceResponse(Envelope):
    git: str | None = None
    sections: int = 0
    unproduced: int = 0
    titles: list[str] = []
    gate_passed: bool | None = None
    checks: list[GateCheck] = []
    generated_utc: str | None = None
