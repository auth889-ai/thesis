"""Traffic-science foundation — GRADUATED FROM LAB 00 (UTD19 / Loder et al. 2019).

Lab 00 established, on real UTD19 data, the concepts every later evaluation
depends on: flow, occupancy/density, accumulation, production, the Macroscopic
Fundamental Diagram and its critical point (n*, P*, v* = P*/n*).

This module carries the *definitions and invariants* into the platform. It does
NOT recompute or restate Lab 00's frozen torino numbers — those live in
paper_labs/00_utd19/outputs/ and are cited, never duplicated.

Role of the critical point in DhakaFlow — read this before using it
-------------------------------------------------------------------
Loder et al. observe that, for maximising *travel production alone*, an ideal
control would act near n ≈ n* (their §Introduction). That is a statement about
one macroscopic quantity in their study networks. It is **not** the DhakaFlow
control objective, and no controller in this project is required or expected to
hold n ≈ n*.

Within DhakaFlow the critical point is used only as:
  * a **traffic-science diagnostic** (is this network in its free-flow or
    congested branch?);
  * a **congestion/capacity reference** for interpreting results;
  * an optional **state feature** for a controller or forecaster;
  * an optional **reward-shaping feature** whose usefulness must be established
    by ablation, never assumed;
  * an optional **constraint / risk signal** (e.g. over-saturation warning).

Controllers in Labs 14-21 optimise broader, multi-objective outcomes — travel
time, waiting time, queue length, pressure, spillback, throughput, downstream
capacity, person-delay, pedestrian delay, emergency delay, forecast risk and
safety. The congested branch also explains why routing more vehicles into a
saturated region lowers total throughput (Lab 22).

Transferability warning: critical values are network-specific. A value measured
on one city's network (e.g. Lab 00's torino estimate) must never be transferred
as an operating threshold for Dhaka; Dhaka's own critical behaviour has to be
estimated from Dhaka data (Labs 06/13).
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

    NETWORK-SPECIFIC. A critical point belongs to the network and observation
    period it was estimated from (`source_lab`). Values are not portable between
    cities: Lab 00's torino estimate is a reproduction artifact, never a Dhaka
    operating threshold, control target or calibration input.
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
    """Signed gap n - n*: negative = below the critical point, positive = beyond it.

    A DIAGNOSTIC scalar, not a control target. It may be offered to a controller
    as a state feature, a reward-shaping term or a risk/constraint signal, but
    any such use must be justified by ablation (Lab 20) against the broader
    objective set (travel time, waiting, queue, pressure, spillback, throughput,
    downstream capacity, person/pedestrian/emergency delay, forecast risk,
    safety). Nothing in the platform drives the network toward n = n*.

    `critical` must have been estimated on the SAME network being measured.
    """
    if critical.units != "per_km2" and critical.units != "per_lane":
        raise ValueError(f"unknown units {critical.units!r}")
    return current_accumulation - critical.critical_density
