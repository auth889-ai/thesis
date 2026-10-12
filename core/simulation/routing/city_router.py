"""A route on a city's own road network, for any city that has been built (`data/cities/<city_id>/sumo/`).

The network is the OpenStreetMap geometry SUMO's netconvert produced for the city's box; nothing here names a city and
no map provider is asked. The path is the fastest one at the network's speed limits (sumolib's own search, which
follows the network's turn connections). It follows the method of `routing/local_router.py`, which serves one frozen
network only and is left as it is.

A point outside the city's box, or with no drivable road within SNAP_RADIUS_M, is refused: the city is built for its
box only, and the page then offers to build a larger one.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

from core.common.paths import REPO

CITY_DIR = REPO / "data/cities"
SNAP_RADIUS_M = 150.0
VCLASS = "passenger"
SAME_ROAD_M = 10.0
MAX_CANDIDATES = 4


class Refused(Exception):
    """Why no route is given. `code` is one of no_network, outside_area, no_road_near, no_path."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@lru_cache(maxsize=2)
def network(city_id: str, city_dir: str = str(CITY_DIR)):
    """(sumolib network, manifest) of a built city, or None when it has not been built."""
    folder = Path(city_dir) / city_id / "sumo"
    if not (folder / "MANIFEST.json").exists():
        return None
    import sumolib
    man = json.loads((folder / "MANIFEST.json").read_text())
    return sumolib.net.readNet(str(REPO / man["files"]["net"])), man


def nearest(net, lat: float, lon: float, radius_m: float = SNAP_RADIUS_M) -> list:
    """The drivable sections a point may stand on: the nearest one and any other within SAME_ROAD_M of that distance.
    The two directions of a two-way road lie side by side, so the point alone cannot say which one is meant; the
    route search tries each and keeps the fastest."""
    x, y = net.convertLonLat2XY(lon, lat)
    near = sorted((d, e.getID(), e) for e, d in net.getNeighboringEdges(x, y, r=radius_m) if e.allows(VCLASS) and not e.isSpecial())
    return [e for d, _, e in near if d <= near[0][0] + SAME_ROAD_M][:MAX_CANDIDATES]


def heading(shape) -> float:
    """Degrees clockwise from north, from the first to the last point of a shape in network metres."""
    (x0, y0), (x1, y1) = shape[0][:2], shape[-1][:2]
    return round(math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360, 1)


def section(net, e) -> dict:
    return {"id": e.getID(), "geometry": [[round(lon, 6), round(lat, 6)] for lon, lat in (net.convertXY2LonLat(x, y) for x, y in e.getShape())],
            "length_m": round(e.getLength(), 1), "limit_kmh": round(e.getSpeed() * 3.6, 1), "heading_deg": heading(e.getShape())}


def route(city_id: str, origin: tuple[float, float], dest: tuple[float, float], city_dir: Path = CITY_DIR) -> dict:
    """The fastest path at speed limits between two (lat, lon) points, section by section. Raises Refused."""
    built = network(city_id, str(city_dir))
    if built is None:
        raise Refused("no_network", "no data for this city: no road network has been built for it")
    net, man = built
    s, w, n, e = man["bbox"]
    ends = []
    for name, (lat, lon) in (("start", origin), ("destination", dest)):
        if not (s <= lat <= n and w <= lon <= e):
            raise Refused("outside_area", f"the {name} is outside this city's built area")
        found = nearest(net, lat, lon)
        if not found:
            raise Refused("no_road_near", f"no drivable road within {SNAP_RADIUS_M:.0f} m of the {name}")
        ends.append(found)
    paths = [net.getOptimalPath(a, b, vClass=VCLASS) for a in ends[0] for b in ends[1]]
    paths = sorted(((cost, [e.getID() for e in p], p) for p, cost in paths if p), key=lambda t: t[:2])
    if not paths:
        raise Refused("no_path", "no drivable path joins these two points on this city's network")
    path = paths[0][2]
    sections = [section(net, e) for e in path]
    return {"city_id": city_id, "sections": sections, "length_m": round(sum(x["length_m"] for x in sections), 1),
            "network": {"source": man["network_reality"], "built_utc": man["generated_utc"], "bbox": man["bbox"],
                        "limits": "each section's speed limit is the OpenStreetMap maxspeed tag where there is one, otherwise netconvert's default for the road class; the network does not record which"}}
