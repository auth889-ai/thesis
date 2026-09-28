"""Canonical units for the whole platform. One unit per quantity, no exceptions.

Unit confusion is the most common silent defect in traffic research code (Lab 00
already hit it: UTD19 occupancy arrives as 0-100 percent while the MFD theory
needs a 0-1 fraction). Every interface in dhakaflow/ therefore names its unit in
the field name or docstring, and conversions live here rather than inline.
"""
from __future__ import annotations

# ---------------------------------------------------------------- canonical units
# time            : seconds (s)          — simulation time and durations
# distance        : meters (m)           — geometry, queue lengths, route length
# speed           : m/s                  — INTERNAL canonical speed
# flow            : vehicles/hour (veh/h)
# density         : vehicles/km          (per lane unless stated)
# occupancy       : fraction in [0, 1]   (never percent)
# accumulation    : vehicles             (network-level; per km^2 when normalized)
# production      : vehicle-km/hour      (network-level; per km^2 when normalized)
# angle           : degrees
# coordinates     : (lon, lat) WGS84 degrees for geo; (x, y) meters for projected

SECONDS_PER_HOUR = 3600.0
METERS_PER_KM = 1000.0


def kmh_to_ms(kmh: float) -> float:
    """km/h -> m/s (canonical speed unit)."""
    return kmh * METERS_PER_KM / SECONDS_PER_HOUR


def ms_to_kmh(ms: float) -> float:
    """m/s -> km/h (reporting/plotting unit)."""
    return ms * SECONDS_PER_HOUR / METERS_PER_KM


def percent_to_fraction(percent: float) -> float:
    """Occupancy 0-100 percent -> 0-1 fraction. See Lab 00 DATA_SPEC (torino)."""
    return percent / 100.0


def flow_per_interval_to_vph(count: float, interval_s: float) -> float:
    """Vehicle count observed over `interval_s` seconds -> veh/h."""
    if interval_s <= 0:
        raise ValueError("interval_s must be > 0")
    return count * SECONDS_PER_HOUR / interval_s


def speed_from_flow_density(flow_vph: float, density_veh_km: float) -> float:
    """Fundamental traffic relation v = q / k, returned in km/h.

    Raises on zero density: an undefined speed must never be silently reported
    as 0 (Lab 00 lesson — that would corrupt any MFD aggregate).
    """
    if density_veh_km <= 0:
        raise ValueError("density must be > 0 to derive speed (q = k * v)")
    return flow_vph / density_veh_km
