"""Route-to-corridor geometry, and the congestion-band multiplier shared with the local router."""
from __future__ import annotations

import math

HORIZONS = [15, 30, 60]
NEAR_M = 300              # a route "runs along" a corridor if it passes this close to its axis
MIN_POINTS = 3
BAND = {0: 1.08, 1: 1.33, 2: 1.75, 3: 2.50}


def _m(lat1, lng1, lat2, lng2) -> float:
    dy = (lat2 - lat1) * 111_000
    dx = (lng2 - lng1) * 111_000 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _dist_to_segment(p, a, b) -> tuple[float, float]:
    """(metres from point p to segment a-b, position t along it), all (lat, lng), flat frame."""
    ky = 111_000; kx = 111_000 * math.cos(math.radians(a[0]))
    px, py = (p[1] - a[1]) * kx, (p[0] - a[0]) * ky
    bx, by = (b[1] - a[1]) * kx, (b[0] - a[0]) * ky
    L2 = bx * bx + by * by
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, (px * bx + py * by) / L2))
    return math.hypot(px - t * bx, py - t * by), t


def _min_dist(p, line) -> float:
    return min(_dist_to_segment(p, line[k], line[k + 1])[0] for k in range(len(line) - 1))


def runs_along(pts, poly, near_m: float = NEAR_M, min_cover: float = 0.5) -> bool:
    """A route runs along a corridor when at least `min_cover` of the corridor's own polyline
    vertices lie within `near_m` of the route — the live geometry, not a straight axis, so a
    curved road counts and a junction touch does not."""
    if len(poly) < 2 or len(pts) < 2:
        return False
    covered = sum(1 for v in poly if _min_dist(v, pts) <= near_m)
    return covered / len(poly) >= min_cover


def multiplier(level: float) -> float:
    lo, hi = int(max(0, min(3, math.floor(level)))), int(max(0, min(3, math.ceil(level))))
    return BAND[lo] if lo == hi else BAND[lo] + (level - lo) * (BAND[hi] - BAND[lo])
