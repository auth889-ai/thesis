"""Observation corridors for ANY city — derived from its road graph, not typed in by hand.

Dhaka's twelve corridors were chosen by a person. A city sir names has no such list, so one is
built from the OpenStreetMap graph the registry already extracts: the longest major-road
segments (motorway, trunk, primary) spread across the city, each paired with a neighbouring
segment so the corridor runs a real stretch of road. The live provider then reports each one
every five minutes, the observatory keeps the derived speeds, and the same forecast interface
serves the city as soon as it has enough history. The list is written once, next to the city,
and reused.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from core.common import evidence_paths as config

sys.path.insert(0, str(config.REPO))
CLASS_RANK = {"motorway": 0, "trunk": 1, "primary": 2, "secondary": 3, "tertiary": 4}
DEFAULT_K = 12
MIN_LEN_M = 700          # a corridor shorter than this is one junction, not a stretch of road


def corridors_file(city_id: str) -> Path:
    from core.common.data.cities import CITY_DIR
    return CITY_DIR / city_id / "corridors.json"


def _dist(a, b) -> float:
    dy = (a[0] - b[0]) * 111_000; dx = (a[1] - b[1]) * 111_000 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def derive(city_id: str, k: int = DEFAULT_K) -> list[dict]:
    """Pick k corridors: major-road segments, longest first, at least 1.5 km apart, each paired
    with its farthest graph neighbour so origin and destination are distinct points on the road."""
    from core.common.data.cities import registry
    if not registry.has_graph(city_id):
        registry.build_graph(city_id, max_nodes=250)
    nodes = registry.nodes(city_id)
    by_id = {n["node_id"]: n for n in nodes}
    ranked = sorted(nodes, key=lambda n: (CLASS_RANK.get(n.get("road_class"), 9), -float(n.get("length_m") or 0)))
    picked, out = [], []
    for n in ranked:
        if len(out) >= k:
            break
        p = (n["lat"], n["lon"])
        if any(_dist(p, q) < 1500 for q in picked):
            continue
        nbrs = [by_id[x] for x in n.get("neighbors", []) if x in by_id]
        if not nbrs:
            continue
        far = max(nbrs, key=lambda m: _dist(p, (m["lat"], m["lon"])))
        if _dist(p, (far["lat"], far["lon"])) < MIN_LEN_M:
            continue
        picked.append(p)
        road = n.get("road_name") or n.get("road_class") or "road"
        out.append({"id": f"c{len(out) + 1:02d}_{''.join(ch for ch in road.lower() if ch.isalnum())[:18]}",
                    "name": f"{road} · segment {len(out) + 1}", "road": road,
                    "origin": {"lat": n["lat"], "lng": n["lon"]},
                    "destination": {"lat": far["lat"], "lng": far["lon"]},
                    "road_class": n.get("road_class"), "length_m": round(_dist(p, (far["lat"], far["lon"])))})
    return out


def ensure(city_id: str, k: int = DEFAULT_K) -> list[dict]:
    f = corridors_file(city_id)
    if f.exists():
        return json.loads(f.read_text())
    cs = derive(city_id, k)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cs, indent=1))
    return cs


def add_routes(city_id: str, routes: list[dict]) -> list[dict]:
    """The roads a user actually asked about become observation corridors: each analyzed
    route (origin -> destination) is sampled from now on, so its own history accumulates and
    the forecast covers exactly the trip sir cares about."""
    cs = load(city_id)
    have = {c["id"] for c in cs}
    for r in routes:
        o, d = r.get("origin") or {}, r.get("destination") or {}
        if not (o.get("lat") and d.get("lat")):
            continue
        rid = "route_" + "".join(ch for ch in f"{r.get('label') or ''}".lower() if ch.isalnum())[:24] or \
              f"route_{abs(hash((round(o['lat'], 4), round(o['lng'], 4), round(d['lat'], 4), round(d['lng'], 4)))) % 10**6}"
        if rid in have:
            continue
        cs.append({"id": rid, "name": r.get("label") or rid, "road": "user route",
                   "origin": {"lat": float(o["lat"]), "lng": float(o["lng"])},
                   "destination": {"lat": float(d["lat"]), "lng": float(d["lng"])},
                   "road_class": "route", "length_m": round(_dist((o["lat"], o["lng"]), (d["lat"], d["lng"])))})
        have.add(rid)
    f = corridors_file(city_id); f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(cs, indent=1))
    return cs


def load(city_id: str) -> list[dict]:
    f = corridors_file(city_id)
    return json.loads(f.read_text()) if f.exists() else []
