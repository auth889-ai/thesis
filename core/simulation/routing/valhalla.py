"""Whole-city routes from our own Valhalla server (MIT; third_party/SOURCES.md, "Whole-city routing").

Valhalla runs unchanged on a server built from an OpenStreetMap extract (ODbL). This module only calls its HTTP API and
reads the answer: alternatives, turn-by-turn maneuvers, the shape (its polyline at precision 6). Travel times are from
map speeds, never live traffic, and every route says so. Where a recorded site (a fixed camera of a published dataset)
lies on the route, the stretch it measured is re-timed with the speed recorded there at the requested clock time, and the
route says which stretch and which recording. The server's address is an environment variable named in the city's config;
a city without that section has no whole-city routing, and a server that does not answer is reported, never guessed around.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from core.common import credentials
from core.common.data import city_config, real_speeds

TIMEOUT_S = 15
MATRIX_TIMEOUT_S = 120                             # a grid of a few hundred targets takes the server a few seconds
MATRIX_PAIRS = 2500                                # the server refuses more than this many source x target pairs in one call (probed 2026-10-06: 50x50 passed, 45x500 refused)
MATRIX_SOURCES = 50                                # sources per request
PROFILES = {"car": "auto", "motorcycle": "motorcycle"}
TIME_SOURCE = "map speeds, not live traffic"
ENGINE = "Valhalla"


def decode_polyline6(text: str) -> list[list[float]]:
    """Valhalla's shape: Google's polyline encoding at precision 6 → [[lon, lat], …]."""
    out, index, lat, lon = [], 0, 0, 0
    while index < len(text):
        for which in (0, 1):
            result, shift = 0, 0
            while True:
                b = ord(text[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lon += delta
        out.append([lon / 1e6, lat / 1e6])
    return out


def _call(url: str, body: dict, action: str = "route", timeout: float = TIMEOUT_S) -> dict:
    """One request to the server's `action` (route, isochrone, sources_to_targets, trace_attributes), read as JSON."""
    req = urllib.request.Request(url.rstrip("/") + "/" + action, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "dhakaflow/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _server(city_id: str, profile: str = "car") -> tuple[dict | None, str, str]:
    """(refusal, url, costing): the city's routing server and costing, or the honest refusal when there is none."""
    try:
        cfg = city_config.load(city_id)
    except KeyError:
        return {"city_id": city_id, "available": False, "code": "no_city", "note": "no data for this city: it has no config file"}, "", ""
    if not cfg.routing:
        return {"city_id": city_id, "available": False, "code": "no_engine", "note": "no data for this city: no whole-city routing server is declared for it"}, "", ""
    url = credentials.load(cfg.routing.url_env)
    if not url:
        return {"city_id": city_id, "available": False, "code": "engine_not_configured", "note": f"the routing server's address ({cfg.routing.url_env}) is not set on this machine"}, "", ""
    costing = PROFILES.get(profile)
    if not costing:
        return {"city_id": city_id, "available": False, "code": "bad_profile", "note": f"profile must be one of {sorted(PROFILES)}"}, "", ""
    return None, url, costing


def _ask(city_id: str, url: str, body: dict, action: str, timeout: float = TIMEOUT_S) -> tuple[dict | None, dict]:
    """(refusal, answer): the server's answer to `action`, or the refusal that says how it failed."""
    try:
        return None, _call(url, body, action, timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        return {"city_id": city_id, "available": False, "code": "no_path" if exc.code == 400 else "engine_error", "note": f"the routing server answered {exc.code}: {detail}"}, {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {"city_id": city_id, "available": False, "code": "engine_down", "note": f"the routing server did not answer: {exc}"}, {}


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _nearest_on_shape(shape: list[list[float]], lat: float, lon: float) -> tuple[float, float]:
    """(distance in metres to the nearest vertex, the heading of the shape there in degrees)."""
    best, at = float("inf"), 0
    for i, (x, y) in enumerate(shape):
        d = _haversine_m(lat, lon, y, x)
        if d < best:
            best, at = d, i
    j = min(at + 1, len(shape) - 1) if at + 1 < len(shape) else at
    i = at if j != at else max(at - 1, 0)
    (x1, y1), (x2, y2) = shape[i], shape[j]
    heading = math.degrees(math.atan2((x2 - x1) * math.cos(math.radians((y1 + y2) / 2)), y2 - y1)) % 360
    return best, heading


def recorded_stretches(city_id: str, shape: list[list[float]], at: str, length_m: float, time_s: float) -> tuple[list[dict], float]:
    """The recorded sites a route passes (within the dataset-matching thresholds of real_speeds, by position and heading)
    and the route's time after their stretches are re-timed with the speed recorded at `at` on the site's own day."""
    out, new_time = [], time_s
    map_speed_mps = length_m / time_s if time_s > 0 else None
    for src in real_speeds.recorded_sources(city_id):
        if "sites" not in src:
            continue                                   # the researcher's own device is a source of readings, not a recorded site
        reader = next(r for r in real_speeds._readers().values() if r.NAME == src["dataset"])
        for st in src["sites"]:
            if not st.get("located"):
                continue
            d, h = _nearest_on_shape(shape, st["lat"], st["lon"])
            if d > real_speeds.RECORDED_MATCH_M or real_speeds._turn(h, st["bearing_deg"]) > real_speeds.RECORDED_HEADING_DEG:
                continue
            got = reader.reading_at(st["site"], at)
            if not got or not map_speed_mps:
                continue
            stretch = float(got["stretch_m"])
            before = stretch / map_speed_mps
            after = stretch / (got["median_kmh"] / 3.6)
            new_time += after - before
            out.append({"site": st["site"], "day": st["day"], "at": got["start"], "median_kmh": got["median_kmh"], "vehicles": got["vehicles"], "stretch_m": stretch,
                        "time_s_before": round(before, 1), "time_s_after": round(after, 1), "dataset": src["dataset"], "citation": src["citation"], "licence": src["licence"]})
    return out, new_time


def local_hhmm(cfg) -> str:
    tz = ZoneInfo(cfg.time_zone) if cfg.time_zone else None
    now = datetime.now(tz)
    return f"{now.hour:02d}:{now.minute - now.minute % 5:02d}"


def isochrone(city_id: str, lat: float, lon: float, minutes: tuple[int, ...] = (10, 20, 30), profile: str = "car") -> dict:
    """How far the map's speeds carry a vehicle from one point in each of `minutes`: polygons (GeoJSON, the server's own
    contours; the request shape follows the Valhalla web app, gis-ops/valhalla-app MIT: polygons, denoise, generalize)."""
    refused, url, costing = _server(city_id, profile)
    if refused:
        return refused
    body = {"locations": [{"lat": lat, "lon": lon}], "costing": costing, "contours": [{"time": m} for m in sorted(minutes)], "polygons": True,
            "denoise": 0.5, "generalize": 50, "show_locations": False}
    refused, raw = _ask(city_id, url, body, "isochrone")
    if refused:
        return refused
    feats = [{"minutes": int(round(f["properties"].get("contour", 0))), "geometry": f["geometry"]} for f in raw.get("features", []) if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")]
    return {"city_id": city_id, "available": True, "engine": ENGINE, "profile": profile, "time_source": TIME_SOURCE, "origin": {"lat": lat, "lon": lon}, "contours": sorted(feats, key=lambda f: f["minutes"])}


def matrix(city_id: str, sources: list[tuple[float, float]], targets: list[tuple[float, float]], profile: str = "car") -> dict:
    """Drive time and distance at map speeds from every source to every target (the server's sources_to_targets).
    `times_s[i][j]` is None where the server found no path. Big grids are sent in slices of at most MATRIX_PAIRS pairs."""
    refused, url, costing = _server(city_id, profile)
    if refused:
        return refused
    times = [[None] * len(targets) for _ in sources]
    dists = [[None] * len(targets) for _ in sources]
    for s0 in range(0, len(sources), MATRIX_SOURCES):
        src = sources[s0:s0 + MATRIX_SOURCES]
        per_call = max(1, MATRIX_PAIRS // len(src))
        for start in range(0, len(targets), per_call):
            chunk = targets[start:start + per_call]
            body = {"sources": [{"lat": a, "lon": b} for a, b in src], "targets": [{"lat": a, "lon": b} for a, b in chunk], "costing": costing, "units": "kilometers"}
            refused, raw = _ask(city_id, url, body, "sources_to_targets", timeout=MATRIX_TIMEOUT_S)
            if refused:
                return refused
            for i, row in enumerate(raw.get("sources_to_targets", [])):
                for cell in row:
                    j = start + cell["to_index"]
                    times[s0 + i][j] = cell.get("time")
                    dists[s0 + i][j] = round(1000 * cell["distance"]) if cell.get("distance") is not None else None
    return {"city_id": city_id, "available": True, "engine": ENGINE, "profile": profile, "time_source": TIME_SOURCE, "times_s": times, "distances_m": dists}


def trace(city_id: str, points: list[dict], profile: str = "car", attributes: bool = False) -> dict:
    """Phone fixes matched to the road (the server's trace_attributes, map_snap): for each input point its matched
    position, the OpenStreetMap way it was matched to, and the distance it was moved; an unmatched point stays None.
    With `attributes`, also each matched edge's tunnel flag, density class, road class and length, with its start along the trace."""
    refused, url, costing = _server(city_id, profile)
    if refused:
        return refused
    shape = [{"lat": p["lat"], "lon": p["lng"], **({"time": p["time"]} if p.get("time") is not None else {})} for p in points]
    wanted = ["edge.way_id", "edge.names", "matched.point", "matched.type", "matched.edge_index", "matched.distance_from_trace_point"]
    if attributes:
        wanted += ["edge.tunnel", "edge.bridge", "edge.density", "edge.road_class", "edge.length"]
    body = {"shape": shape, "costing": costing, "shape_match": "map_snap", "units": "kilometers", "filters": {"attributes": wanted, "action": "include"}}
    refused, raw = _ask(city_id, url, body, "trace_attributes")
    if refused:
        return refused
    edges = raw.get("edges", [])
    at = 0.0
    edge_facts = []
    for e in edges:                                      # each edge's start along the matched path, from the lengths before it
        edge_facts.append({"at_m": round(at), "length_m": round(1000 * e.get("length", 0)), "tunnel": bool(e.get("tunnel")), "bridge": bool(e.get("bridge")), "density": e.get("density"), "road_class": e.get("road_class"), "way_id": e.get("way_id")})
        at += 1000 * e.get("length", 0)
    out = []
    for m in raw.get("matched_points", []):
        e = edges[m["edge_index"]] if m.get("edge_index") is not None and m["edge_index"] < len(edges) else {}
        matched = m.get("type") in ("matched", "interpolated")
        out.append({"lat": m.get("lat") if matched else None, "lng": m.get("lon") if matched else None, "type": m.get("type"),
                    "way_id": e.get("way_id") if matched else None, "name": (e.get("names") or [None])[0] if matched else None,
                    "moved_m": round(m["distance_from_trace_point"], 1) if matched and m.get("distance_from_trace_point") is not None else None})
    return {"city_id": city_id, "available": True, "engine": ENGINE, "matched": out, **({"edges": edge_facts} if attributes else {})}


def route(city_id: str, origin: tuple[float, float], destination: tuple[float, float], profile: str = "car", at: str | None = None, alternates: int = 2) -> dict:
    """Routes between two points anywhere the city's server covers. {available, routes: [...]} or an honest refusal."""
    refused, url, costing = _server(city_id, profile)
    if refused:
        return refused
    cfg = city_config.load(city_id)
    body = {"locations": [{"lat": origin[0], "lon": origin[1]}, {"lat": destination[0], "lon": destination[1]}], "costing": costing, "alternates": alternates,
            "units": "kilometers", "language": "en-US", "directions_type": "maneuvers"}
    refused, raw = _ask(city_id, url, body, "route")
    if refused:
        return refused
    at = at or local_hhmm(cfg)
    routes = []
    for trip in [raw.get("trip")] + [a.get("trip") for a in raw.get("alternates", [])]:
        if not trip:
            continue
        shape, maneuvers, length_m, time_s = [], [], 0.0, 0.0
        for leg in trip.get("legs", []):
            shape += decode_polyline6(leg.get("shape", ""))
            for m in leg.get("maneuvers", []):
                maneuvers.append({"instruction": m.get("instruction", ""), "length_m": round(1000 * m.get("length", 0)), "time_s": round(m.get("time", 0)), "type": m.get("type"),
                                  "street_names": m.get("street_names", [])})
            length_m += 1000 * leg.get("summary", {}).get("length", 0)
            time_s += leg.get("summary", {}).get("time", 0)
        stretches, time_recorded = recorded_stretches(city_id, shape, at, length_m, time_s)
        routes.append({"summary": {"length_m": round(length_m), "time_s": round(time_s), "time_source": TIME_SOURCE,
                                   "time_with_recorded_s": round(time_recorded) if stretches else None,
                                   "recorded_note": f"on {len(stretches)} stretch(es) the speed recorded there at {at} replaces the map speed" if stretches else None},
                       "geometry": shape, "maneuvers": maneuvers, "recorded": stretches})
    if not routes:
        return {"city_id": city_id, "available": False, "code": "no_path", "note": "the routing server found no route between these points"}
    return {"city_id": city_id, "available": True, "label": "ROUTE", "engine": ENGINE, "profile": profile, "at": at, "credit": cfg.routing.credit,
            "extract": {"path": cfg.routing.extract, "date": cfg.routing.extract_date}, "time_source": TIME_SOURCE, "routes": routes}
