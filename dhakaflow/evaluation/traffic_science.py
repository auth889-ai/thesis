"""Traffic-science foundation — GRADUATED FROM LAB 00 (UTD19 / Loder et al. 2019).

Lab 00 established, on real UTD19 data, the concepts every later evaluation
depends on: flow, occupancy/density, accumulation, production, the Macroscopic
Fundamental Diagram and its critical point (n*, P*, v* = P*/n*).

This module carries the *definitions and invariants* into the platform. It does
NOT recompute or restate Lab 00's frozen torino numbers — those live in
paper_labs/00_utd19/outputs/ and are cited, never duplicated.

Why the platform needs it: the paper's operating principle is that an ideal
control keeps the network near n ≈ n* (Loder et al. §Introduction). That makes
the critical point the set-point/reference against which Labs 14-21 controllers
are judged, and the congested branch is why routing more vehicles into a
saturated region lowers total throughput (Lab 22).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class MFDPoint:
    """One network state: accumulation/density vs production/flow.

    Two unit conventions are supported and must never be mixed in one diagram:
      * per-lane   : density veh/km/lane, flow veh/h/lane   (Lab 00 Stage 1)
      * normalized : accumulation veh/km^2, production veh-km/h/km^2 (paper)
    """

    density: float
    flow: float
    time_s: float | None = None
    n_detectors: int | None = None
    units: str = "per_lane"        # "per_lane" | "per_km2"

    def speed(self) -> float:
        """v = q / k. Undefined at zero density — raises rather than returning 0."""
        if self.density <= 0:
            raise ValueError("speed undefined at zero density")
        return self.flow / self.density


@dataclass(frozen=True)
class CriticalPoint:
    """The MFD maximum: capacity and the accumulation at which it occurs.

    `interior_maximum` is a required honesty flag, learned from Lab 00: when the
    fitted maximum sits at the edge of the observed range (whole-city torino
    never entered deep congestion) the critical point is a lower bound, not a
    peak, and must not be reported as a capacity estimate without that caveat.
    """

    critical_density: float          # n* or k*
    critical_flow: float             # P* or q*
    units: str = "per_lane"
    interior_maximum: bool = False
    jam_density: float | None = None
    free_flow_speed: float | None = None
    fit_method: str = "unknown"      # e.g. "lsq_logsumexp_upper_bound_q95"
    calibrated: bool = False         # False => UNCALIBRATED_ANALYSIS
    source_lab: str = "00_utd19"
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def critical_speed(self) -> float:
        """v* = P*/n* — the speed at which congestion begins."""
        if self.critical_density <= 0:
            raise ValueError("critical_density must be > 0")
        return self.critical_flow / self.critical_density

    def sanity_check_vs_jam(self, max_ratio: float = 1 / 3) -> bool:
        """Traffic-physics consistency: n* should not exceed ~1/3 of jam density.

        Stated in Loder et al. (2019) Results, citing the statistical-physics
        literature. Returns True when unknown jam density makes the check
        inapplicable — an unavailable check is not a failed check.
        """
        if self.jam_density is None or self.jam_density <= 0:
            return True
        return (self.critical_density / self.jam_density) <= max_ratio

    def congestion_state(self, current_density: float) -> str:
        """Where the network sits relative to the critical point."""
        if current_density < self.critical_density:
            return "free_flow"
        if current_density > self.critical_density:
            return "congested"
        return "critical"


def network_speed(production: float, accumulation: float) -> float:
    """Fundamental network relation v = P / n (Loder et al. §Introduction)."""
    if accumulation <= 0:
        raise ValueError("accumulation must be > 0")
    return production / accumulation


def distance_to_critical(current_accumulation: float, critical: CriticalPoint) -> float:
    """Signed gap n - n*: negative = spare capacity, positive = over-saturated.

    This is the control-relevant scalar for perimeter/pressure strategies and a
    natural reward-shaping term for Lab 20 — hence its home in the platform.
    """
    return current_accumulation - critical.critical_density
