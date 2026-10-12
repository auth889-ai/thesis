"""What the 3D view draws for a city: its roads, its building outlines with a height, and where its signals stand.

Everything comes from files the city pipeline wrote for that city (`data/cities/<city_id>/sumo/`); nothing here names
a city. The scene is the stage of a SIMULATION: the roads and buildings are OpenStreetMap geometry, the traffic that
moves on them is generated demand, and the payload says so.

Building heights, in this order: the OSM `height` tag; else `building:levels` x LEVEL_M; else DEFAULT_M. LEVEL_M and
DEFAULT_M are assumptions, not measurements, and every building says which of the three rules gave its height.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from core.common.paths import REPO

CITY_DIR = REPO / "data/cities"
LEVEL_M = 3.0            # ASSUMED storey height when only `building:levels` is tagged
DEFAULT_M = 6.0          # ASSUMED height of a building with neither tag
NO_DATA = "no data for this city"
LANES_OSM, LANES_DEFAULT, LANES_UNKNOWN = "OpenStreetMap", "default", "not recorded"


def building_height(tags: dict) -> tuple[float, str]:
    m = re.match(r"\s*(\d+(?:\.\d+)?)", str(tags.get("height", "")))
    if m and float(m.group(1)) > 0:
        return float(m.group(1)), "osm height tag"
    lv = re.match(r"\s*(\d+(?:\.\d+)?)", str(tags.get("building:levels", "")))
    if lv and float(lv.group(1)) > 0:
        return round(float(lv.group(1)) * LEVEL_M, 1), "osm levels tag x assumed storey height"
    return DEFAULT_M, "assumed default"


def _buildings(path: Path) -> list[dict]:
    feats = []
    for el in json.loads(path.read_text()).get("elements", []):
        ring = [[round(p["lon"], 6), round(p["lat"], 6)] for p in el.get("geometry") or []]
        if el.get("type") != "way" or len(ring) < 4 or ring[0] != ring[-1]:
            continue                                    # not a closed outline
        h, rule = building_height(el.get("tags") or {})
        feats.append({"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [ring]}, "properties": {"height": h, "height_from": rule}})
    return feats


def tagged_ways(osm: Path) -> set[str] | None:
    """Ids of the ways in an OpenStreetMap extract that carry a `lanes` tag; None when there is no extract."""
    if not osm.exists():
        return None
    import xml.etree.ElementTree as ET
    found = set()
    for _, el in ET.iterparse(str(osm), events=("end",)):
        if el.tag == "way":
            if any(t.get("k") == "lanes" for t in el.iter("tag")):
                found.add(el.get("id"))
            el.clear()
    return found


def lanes_source(origin: str | None, tagged: set[str] | None) -> str:
    """Where a section's lane count comes from. `origin` is the way id (or ids) netconvert recorded on the section;
    a section joined from several ways counts as OpenStreetMap only when every one of them is tagged."""
    if tagged is None or not origin:
        return LANES_UNKNOWN
    return LANES_OSM if all(w in tagged for w in origin.split()) else LANES_DEFAULT


def _centre(net, e) -> list[list[float]]:
    """The middle of the carriageway: the mean of the lane centre lines, which is where a line as wide as all lanes
    must be drawn. SUMO's own edge line is one border of a two-way road, so it is used only when lanes differ in shape."""
    shapes = [l.getShape() for l in e.getLanes()]
    if len({len(sh) for sh in shapes}) == 1:
        pts = [(sum(p[0] for p in ps) / len(ps), sum(p[1] for p in ps) / len(ps)) for ps in zip(*shapes)]
    else:
        pts = [p[:2] for p in e.getShape()]
    return [[round(lon, 6), round(lat, 6)] for lon, lat in (net.convertXY2LonLat(x, y) for x, y in pts)]


@lru_cache(maxsize=4)
def _scene(city_id: str, city_dir: str) -> dict | None:
    import sumolib
    folder = Path(city_dir) / city_id / "sumo"
    if not (folder / "MANIFEST.json").exists():
        return None
    man = json.loads((folder / "MANIFEST.json").read_text())
    net_file = REPO / man["files"]["net"]
    net = sumolib.net.readNet(str(net_file))
    tagged = tagged_ways(net_file.with_name(net_file.name.split(".net.xml")[0] + ".osm.xml"))
    roads, by_source = [], {LANES_OSM: 0, LANES_DEFAULT: 0, LANES_UNKNOWN: 0}
    for e in net.getEdges():
        src = lanes_source(e.getLanes()[0].getParam("origId"), tagged)
        by_source[src] += 1
        roads.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": _centre(net, e)},
                      "properties": {"id": e.getID(), "lanes": e.getLaneNumber(), "width_m": round(sum(l.getWidth() for l in e.getLanes()), 2),
                                     "lanes_source": src, "kind": (e.getType() or "").replace("highway.", "")}})
    signals, seen = [], set()
    for tls in net.getTrafficLights():
        for in_lane, _out, link in tls.getConnections():
            if (tls.getID(), in_lane.getID()) in seen:
                continue                                # one marker per approach lane, at its stop line
            seen.add((tls.getID(), in_lane.getID()))
            lon, lat = net.convertXY2LonLat(*in_lane.getShape()[-1][:2])
            signals.append({"tls": tls.getID(), "link": link, "lon": round(lon, 6), "lat": round(lat, 6)})
    bfile = man["files"].get("buildings")
    buildings = _buildings(REPO / bfile) if bfile and (REPO / bfile).exists() else []
    s, w, n, e = man["bbox"]
    rules = {}
    for b in buildings:
        rules[b["properties"]["height_from"]] = rules.get(b["properties"]["height_from"], 0) + 1
    return {"available": True, "city_id": city_id, "label": "SIMULATED", "bbox": man["bbox"], "center": [round((w + e) / 2, 6), round((s + n) / 2, 6)],
            "network": {"edges": len(roads), "traffic_lights": man["traffic_lights"], "reality": man["network_reality"]},
            "demand": {"label": man["demand_reality"], "note": man["warning"], "seed": man.get("seed"), "horizon_s": man.get("horizon_s"), "calibrated_to": man.get("calibrated_to")},
            "lanes": {"sections_by_source": by_source, "width_rule": "lane count x SUMO lane width"},
            "roads": {"type": "FeatureCollection", "features": roads}, "buildings": {"type": "FeatureCollection", "features": buildings}, "signals": signals,
            "heights": {"rule": "OSM height tag; else building:levels x storey height; else a default", "assumed_storey_m": LEVEL_M, "assumed_default_m": DEFAULT_M, "buildings_by_rule": rules},
            "attribution": "© OpenStreetMap contributors (ODbL)"}


def build(city_id: str, city_dir: Path = CITY_DIR) -> dict:
    """The scene of a city that has been built, or a plain statement that it has none."""
    return _scene(city_id, str(city_dir)) or {"available": False, "city_id": city_id, "note": f"{NO_DATA}: no network has been built for it"}
