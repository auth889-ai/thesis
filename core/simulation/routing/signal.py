"""Where a chosen route may have weak or no mobile signal, before the trip (Q3). Main reference: Bartendr (Schulman, Navda,
Ramjee, Spring, ACM MobiCom 2010; third_party/SOURCES.md "Works with weak signal"): signal is predicted along a known *track*
— here the chosen route — per direction of travel ("tracks from opposite directions may not align"), in 100 m steps.

Two sources, both named in the answer, nothing guessed:
  1. the road, from the city's own Valhalla server (trace_attributes along the route): a tunnel edge is "none"; an edge of the
     lowest road-density classes is "weak" when there is no history (open country, few masts);
  2. the recorded signal history of opted-in phones in the H3 cells the step passes, **only from cells whose heading octant
     matches the route's direction there** (probe cells are keyed h3:octant).
Each step gets a quality bin. Bartendr measured in RSSI; browsers expose no RSSI, only the Network Information API (effectiveType,
downlink; Chrome on Android only). Our mapping to Bartendr's anchors is stated with every answer:
  strong (about -70 RSSI): downlink >= 2 Mbit/s or 4g; medium (about -90): 0.5-2 Mbit/s or 3g; weak: < 0.5 Mbit/s or 2g/slow-2g;
  none: a tunnel; unknown: no history and nothing from the road.
"""
from __future__ import annotations

import math

STEP_M = 100                                           # Bartendr's step
BINS = ("none", "weak", "medium", "unknown", "strong")  # worst first
STRONG_MBPS, MEDIUM_MBPS = 2.0, 0.5
LOW_DENSITY = 2                                        # Valhalla edge.density 0..15; at or below this is open country
MIN_READINGS = 3                                       # a step needs this many matched readings before its history counts
MAPPING = ("strong ~ -70 RSSI: downlink >= 2 Mbit/s or 4g; medium ~ -90 RSSI: 0.5-2 Mbit/s or 3g; weak: < 0.5 Mbit/s or 2g; "
           "none: a tunnel. Bartendr measured RSSI; the browser reports only effectiveType and downlink, so this mapping is ours.")


def _haversine_m(a: list[float], b: list[float]) -> float:
    p = math.pi / 180
    x = math.sin((b[1] - a[1]) * p / 2) ** 2 + math.cos(a[1] * p) * math.cos(b[1] * p) * math.sin((b[0] - a[0]) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(x))


def bearing(a: list[float], b: list[float]) -> float:
    """Initial bearing from a to b ([lon, lat]), degrees clockwise from north."""
    p1, p2, dl = math.radians(a[1]), math.radians(b[1]), math.radians(b[0] - a[0])
    return math.degrees(math.atan2(math.sin(dl) * math.cos(p2), math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360


def octant(heading: float) -> str:
    """The probe cells' heading octant (app.probes.service.cell_of)."""
    return str(int(((heading % 360) + 22.5) // 45) % 8)


def steps(shape: list[list[float]], step_m: int = STEP_M) -> list[dict]:
    """The route's shape ([lon, lat]) cut into steps of about `step_m`: {i, start_m, end_m, geometry, heading}."""
    if len(shape) < 2:
        return [{"i": 0, "start_m": 0, "end_m": 0, "geometry": shape, "heading": 0.0}]
    out, acc, start, cur = [], 0.0, 0.0, [shape[0]]
    for a, b in zip(shape, shape[1:]):
        acc += _haversine_m(a, b)
        cur.append(b)
        if acc - start >= step_m:
            out.append({"i": len(out), "start_m": round(start), "end_m": round(acc), "geometry": cur, "heading": bearing(cur[0], cur[-1])})
            cur, start = [b], acc
    if len(cur) > 1:
        out.append({"i": len(out), "start_m": round(start), "end_m": round(acc), "geometry": cur, "heading": bearing(cur[0], cur[-1])})
    return out


def bin_of(net_type: str | None, downlink_mbps: float | None) -> str:
    """One reading's bin under the stated mapping; downlink wins when both are given."""
    if downlink_mbps is not None:
        return "strong" if downlink_mbps >= STRONG_MBPS else "medium" if downlink_mbps >= MEDIUM_MBPS else "weak"
    return {"4g": "strong", "3g": "medium", "2g": "weak", "slow-2g": "weak"}.get(net_type or "", "unknown")


def history_bin(cells: list[dict]) -> tuple[str, str]:
    """From the heading-matched probe cells a step passes: their mean downlink when known, else the share of weak readings."""
    n = sum(c.get("n_signal", 0) for c in cells)
    if n < MIN_READINGS:
        return "unknown", "no signal history in this direction here" if n == 0 else f"only {n} reading(s) in this direction here"
    downs = [(c["mean_downlink_mbps"], c.get("n_signal", 0)) for c in cells if c.get("mean_downlink_mbps") is not None]
    if downs:
        mean = sum(d * w for d, w in downs) / max(sum(w for _, w in downs), 1)
        return bin_of(None, mean), f"recorded history: {n} readings, mean {mean:.1f} Mbit/s"
    weak = sum(c.get("weak_signal", 0) for c in cells)
    return ("weak" if weak * 2 > n else "medium"), f"recorded history: {n} readings, {weak} weak (no downlink reported)"


def road_bin(edges: list[dict]) -> tuple[str | None, str | None]:
    """From the road edges under a step: a tunnel is none; open country is weak (used only without history); else nothing."""
    if any(e.get("tunnel") for e in edges):
        return "none", "tunnel"
    if edges and all(e.get("density") is not None and e["density"] <= LOW_DENSITY for e in edges):
        return "weak", "open country (few masts on the map's density scale)"
    return None, None


def combine(road: tuple[str | None, str | None], history: tuple[str, str]) -> dict:
    """A tunnel always wins; known history wins over the road's open-country guess; otherwise the road, else unknown."""
    r_bin, r_basis = road
    h_bin, h_basis = history
    if r_bin == "none":
        return {"bin": "none", "basis": r_basis, "history": h_basis}
    if h_bin != "unknown":
        return {"bin": h_bin, "basis": h_basis, "history": h_basis}
    if r_bin:
        return {"bin": r_bin, "basis": r_basis, "history": h_basis}
    return {"bin": "unknown", "basis": h_basis, "history": h_basis}


def refresh_points(bins: list[str]) -> list[int]:
    """Bartendr's threshold rule for small syncs, with 'strong' as the threshold: refresh alerts at the last strong step before
    each weak or none run (a run that starts the route has nothing before it)."""
    out, last_strong = [], None
    for i, b in enumerate(bins):
        if b == "strong":
            last_strong = i
        if b in ("weak", "none") and (i == 0 or bins[i - 1] not in ("weak", "none")) and last_strong is not None:
            out.append(last_strong)
    return sorted(set(out))
