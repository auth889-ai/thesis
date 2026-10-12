"""Reality labels — every observation declares which reality it came from.

The five classes (user mandate, P-LIVE):

    REAL_LIVE        current external observation, fetched moments ago
    REAL_RECORDED    real sensor/camera data captured earlier (e.g. TFP-BD video)
    REAL_HISTORICAL  real archival records (e.g. accident tables 2007-2024)
    SIMULATED        produced by SUMO or any simulator
    DERIVED          computed from other observations (must name its parents)

Mixing classes silently is the fastest way to a false claim ("live Dhaka
traffic" that is actually simulation). `assert_single_reality` makes an
aggregation over mixed classes an exception unless the caller explicitly
derives, in which case the result is DERIVED and records its parent classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


class RealityClass(str, Enum):
    REAL_LIVE = "REAL_LIVE"
    REAL_RECORDED = "REAL_RECORDED"
    REAL_HISTORICAL = "REAL_HISTORICAL"
    SIMULATED = "SIMULATED"
    DERIVED = "DERIVED"


@dataclass(frozen=True)
class Provenance:
    """Who produced an observation, when, and from what."""

    provider: str                       # e.g. "google_routes", "sumo_twin"
    reality: RealityClass
    captured_utc: str                   # ISO 8601
    request_latency_ms: float | None = None
    parent_realities: tuple[RealityClass, ...] = ()   # DERIVED only
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.reality is RealityClass.DERIVED and not self.parent_realities:
            raise ValueError(
                "DERIVED observations must name their parent reality classes — "
                "otherwise the derivation chain is untraceable")
        if self.reality is not RealityClass.DERIVED and self.parent_realities:
            raise ValueError(
                f"{self.reality.value} must not carry parent_realities; "
                "only DERIVED records a derivation chain")


def assert_single_reality(items: Sequence[Provenance]) -> RealityClass:
    """All items must share one reality class; mixing raises."""
    classes = {p.reality for p in items}
    if len(classes) > 1:
        raise ValueError(
            f"REALITY MIX: aggregation spans {sorted(c.value for c in classes)} — "
            "combine explicitly via derive() so the result is labelled DERIVED, "
            "never silently")
    if not classes:
        raise ValueError("no observations to aggregate")
    return classes.pop()


def derive(provider: str, captured_utc: str,
           parents: Sequence[Provenance], **metadata: str) -> Provenance:
    """The one legal way to combine reality classes: an explicit derivation."""
    if not parents:
        raise ValueError("a derivation needs at least one parent")
    return Provenance(
        provider=provider,
        reality=RealityClass.DERIVED,
        captured_utc=captured_utc,
        parent_realities=tuple(sorted({p.reality for p in parents},
                                      key=lambda r: r.value)),
        metadata=dict(metadata),
    )
