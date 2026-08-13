"""Live external traffic reference — platform-level contract (Lab 02+).

An external routing provider (e.g. Google Routes API) used ONLY as
``EXTERNAL_LIVE_REFERENCE``: an independent, non-authoritative signal for
plausibility checks. It is never ground truth, never a calibration target by
itself, and never compared against uncalibrated simulation travel times to
claim realism.

Data-retention policy (user DECISION 1, 2026-08, conservative):
    Raw provider responses, route polylines, durations, distances, or other
    provider Content are NOT persisted in git or as permanent research
    evidence. The storage location does not override provider terms.
    Observations live in memory for the duration of a sanity check; only
    request metadata (timestamps, status, preference used) and derived
    boolean verdicts may be recorded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

CLASSIFICATION = "EXTERNAL_LIVE_REFERENCE"


@dataclass(frozen=True)
class LiveRouteRequest:
    """One origin→destination query, WGS84 coordinates."""

    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    routing_preference: str = "TRAFFIC_AWARE"   # or TRAFFIC_AWARE_OPTIMAL / TRAFFIC_UNAWARE
    label: str | None = None                    # e.g. "OD3_center_to_north"

    def __post_init__(self) -> None:
        allowed = {"TRAFFIC_UNAWARE", "TRAFFIC_AWARE", "TRAFFIC_AWARE_OPTIMAL"}
        if self.routing_preference not in allowed:
            raise ValueError(f"routing_preference must be one of {sorted(allowed)}")


@dataclass(frozen=True)
class LiveRouteObservation:
    """In-memory result of one live query. NOT for persistence (see module doc).

    ``duration_s``/``static_duration_s``/``distance_m`` are ``None`` whenever the
    provider did not answer (disabled, error) — missing is None, never 0.
    """

    request: LiveRouteRequest
    provider: str
    status: str                                  # "OK" | "DISABLED_NO_KEY" | "ERROR:<...>"
    requested_at_utc: str | None = None
    duration_s: float | None = None
    static_duration_s: float | None = None
    distance_m: float | None = None
    classification: str = CLASSIFICATION
    diagnostics: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "OK"

    def persistable_metadata(self) -> dict:
        """The ONLY part of an observation that may be written to disk."""
        return {
            "label": self.request.label,
            "routing_preference": self.request.routing_preference,
            "provider": self.provider,
            "status": self.status,
            "requested_at_utc": self.requested_at_utc,
            "classification": self.classification,
        }


@runtime_checkable
class LiveTrafficReference(Protocol):
    """Uniform contract for any live external routing reference."""

    def travel_time(self, req: LiveRouteRequest) -> LiveRouteObservation: ...

    @property
    def provider(self) -> str: ...

    @property
    def enabled(self) -> bool: ...
