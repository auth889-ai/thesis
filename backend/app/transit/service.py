"""Door to door by rail: walk to the nearest stop, wait half a headway, ride, walk. Every number states
whether it is measured (OSM geometry), published (operator headway and hours) or estimated."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from core.common.data import osm

from app.transit import schedule

WALK_MPS = 1.34                 # average adult walking speed (Bohannon 1997)
WALK_DETOUR = 1.3               # street distance over straight-line distance, typical urban grid
MAX_WALK_M = 1500.0
BOX_PAD_DEG = 0.06


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def walk_s(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    d = haversine_m(a, b) * WALK_DETOUR
    return d, d / WALK_MPS


def _nearest(stops: list[dict], p: tuple[float, float]) -> tuple[int, float]:
    i, d = min(((k, haversine_m((s["lat"], s["lon"]), p)) for k, s in enumerate(stops)), key=lambda x: x[1])
    return i, d


def ride(line: dict, i: int, j: int, facts: dict) -> tuple[float, float, int]:
    """(ride seconds, ride metres, stops passed) between stop indexes i and j along the line's own stop order."""
    a, b = (i, j) if i < j else (j, i)
    stops = line["stops"]
    metres = sum(haversine_m((stops[k]["lat"], stops[k]["lon"]), (stops[k + 1]["lat"], stops[k + 1]["lon"])) for k in range(a, b))
    n = b - a
    return metres / (facts["commercial_speed_kmh"] / 3.6) + max(n - 1, 0) * schedule.DWELL_S, metres, n


def options(origin: tuple[float, float], dest: tuple[float, float], depart_utc: datetime, local_offset_h: float, lines: list[dict] | None = None) -> list[dict]:
    """Every rail option within walking reach of both ends, best first. `lines` may be given (tests); else OSM is queried."""
    south, north = min(origin[0], dest[0]) - BOX_PAD_DEG, max(origin[0], dest[0]) + BOX_PAD_DEG
    west, east = min(origin[1], dest[1]) - BOX_PAD_DEG, max(origin[1], dest[1]) + BOX_PAD_DEG
    lines = osm.rail_lines(south, west, north, east) if lines is None else lines
    local = depart_utc + timedelta(hours=local_offset_h)
    seen, out = set(), []
    for line in lines:
        key = (line.get("name"), line.get("ref"), tuple(sorted(s["name"] for s in line["stops"])))
        if key in seen:                                  # the two directions of one line are one option
            continue
        seen.add(key)
        i, di = _nearest(line["stops"], origin); j, dj = _nearest(line["stops"], dest)
        if i == j or di > MAX_WALK_M or dj > MAX_WALK_M:
            continue
        facts = schedule.facts_for(line)
        w1_m, w1 = walk_s(origin, (line["stops"][i]["lat"], line["stops"][i]["lon"]))
        w2_m, w2 = walk_s((line["stops"][j]["lat"], line["stops"][j]["lon"]), dest)
        open_now = schedule.is_open(facts, local + timedelta(seconds=w1))
        hw = schedule.headway_s(facts, local + timedelta(seconds=w1))
        wait = hw / 2.0
        r_s, r_m, n = ride(line, i, j, facts)
        total = w1 + wait + r_s + w2
        out.append({"mode": line.get("mode"), "line": line.get("name"), "ref": line.get("ref"), "network": line.get("network"), "operator": line.get("operator"),
                    "board": line["stops"][i]["name"], "alight": line["stops"][j]["name"], "stops_passed": n, "open": open_now,
                    "legs": [{"kind": "walk", "to": line["stops"][i]["name"], "metres": round(w1_m), "seconds": round(w1)},
                             {"kind": "wait", "seconds": round(wait), "headway_s": hw},
                             {"kind": "ride", "from": line["stops"][i]["name"], "to": line["stops"][j]["name"], "metres": round(r_m), "seconds": round(r_s), "stops": n},
                             {"kind": "walk", "to": "destination", "metres": round(w2_m), "seconds": round(w2)}],
                    "total_s": round(total), "geometry": [[s["lat"], s["lon"]] for s in line["stops"][min(i, j):max(i, j) + 1]],
                    "provenance": {"stops": f"OpenStreetMap (data as of {line.get('osm_timestamp') or 'today'})",
                                   "schedule": ("OSM interval tag" if facts["from_osm"].get("headway") else facts["source"]),
                                   "ride": ("OSM duration tag" if facts["from_osm"].get("speed") else f"estimated from station spacing at {facts['commercial_speed_kmh']:.0f} km/h commercial speed with {schedule.DWELL_S} s per stop"),
                                   "walk": f"straight-line distance × {WALK_DETOUR} at {WALK_MPS} m/s", "wait": "half the published headway"}})
    out.sort(key=lambda o: (not o["open"], o["total_s"]))
    return out


def plan(origin: tuple[float, float], dest: tuple[float, float], depart_utc: datetime | None = None, local_offset_h: float = 6.0) -> dict:
    depart_utc = (depart_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)
    try:
        opts = options(origin, dest, depart_utc, local_offset_h)
        status = "OK" if opts else "NO_LINE_WITHIN_WALKING_REACH"
    except Exception as exc:                            # noqa: BLE001 - the page shows the real reason
        opts, status = [], f"OSM_UNAVAILABLE: {type(exc).__name__}: {str(exc)[:120]}"
    return {"depart_utc": depart_utc.isoformat(), "options": opts, "status": status, "max_walk_m": MAX_WALK_M, "source": "openstreetmap"}
