"""Match a list of measuring stations to the road sections of a built city, and write the result as evidence.

    PYTHONPATH=backend python -m core.common.data.station_matching --city <city_id> --stations <csv with sensor_id, latitude, longitude>

A station inside the city's box is matched to the nearest drivable section within MATCH_M and to any other section
within the same few metres of it. A station list that carries no direction of travel cannot say which carriageway a
station measures, so every candidate is kept and the match is marked unresolved; nothing is picked by guess. No
measurement is read here: this only says where a station's readings would belong once there are any.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from core.common.paths import REPO
from core.simulation.routing import city_router

MATCH_M = 60.0
EVIDENCE = REPO / "evidence/home"


def match(city_id: str, stations: list[dict], city_dir: Path = city_router.CITY_DIR) -> dict:
    built = city_router.network(city_id, str(city_dir))
    if built is None:
        raise SystemExit(f"{city_id}: no data for this city: no road network has been built for it")
    net, man = built
    s, w, n, e = man["bbox"]
    inside = [st for st in stations if s <= st["lat"] <= n and w <= st["lon"] <= e]
    rows = []
    for st in inside:
        x, y = net.convertLonLat2XY(st["lon"], st["lat"])
        near = sorted((round(d, 1), ed.getID(), ed) for ed, d in net.getNeighboringEdges(x, y, r=MATCH_M) if ed.allows(city_router.VCLASS) and not ed.isSpecial())
        cands = [{"section": i, "distance_m": d, "kind": (ed.getType() or "").replace("highway.", ""), "heading_deg": city_router.heading(ed.getShape())}
                 for d, i, ed in near if d <= near[0][0] + city_router.SAME_ROAD_M]
        rows.append({"station": st["id"], "lat": st["lat"], "lon": st["lon"], "candidates": cands,
                     "state": "no section within reach" if not cands else "one section" if len(cands) == 1 else "unresolved: the station list gives no direction of travel"})
    count = lambda state: sum(1 for r in rows if r["state"].startswith(state))
    return {"city_id": city_id, "stations_in_list": len(stations), "stations_in_the_box": len(inside), "match_radius_m": MATCH_M,
            "one_section": count("one"), "unresolved": count("unresolved"), "no_section": count("no section"), "stations": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--stations", required=True, type=Path)
    a = ap.parse_args()
    with open(a.stations) as f:
        stations = [{"id": r["sensor_id"], "lat": float(r["latitude"]), "lon": float(r["longitude"])} for r in csv.DictReader(f)]
    out = match(a.city, stations)
    out.update(generated_utc=datetime.now(timezone.utc).isoformat(), stations_file=a.stations.name, stations_sha256=hashlib.sha256(a.stations.read_bytes()).hexdigest(),
               command=f"python -m core.common.data.station_matching --city {a.city} --stations <{a.stations.name}>", readings="none: no measurement has been read from any station")
    path = EVIDENCE / a.city / "station_matching.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    print(f"{a.city}: {out['stations_in_the_box']} of {out['stations_in_list']} stations in the box; {out['one_section']} on one section, "
          f"{out['unresolved']} unresolved, {out['no_section']} with no section within {MATCH_M:.0f} m -> {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
