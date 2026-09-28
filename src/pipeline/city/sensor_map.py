#!/usr/bin/env python3
"""GENUINE DETECTOR METADATA -> SUMO EDGES, for one uploaded dataset on one generated scenario.

The uploaded Los Angeles dataset carries the first rows of METR-LA in the order of the pinned
DCRNN repository's `data/sensor_graph/graph_sensor_locations.csv` (index, sensor_id, latitude,
longitude). Each dataset node is matched to that file BY INDEX AND COORDINATE (both must agree),
so the sensor id, latitude and longitude written here are the published ones, never synthesised.

Each usable detector is snapped to the nearest passenger edge of the scenario's SUMO network:

    sensor_id · lat · lon · nearest SUMO edge · snap distance · edge type · mapping quality

    GOOD      within GOOD_M and on a motorway/trunk/primary/secondary edge (a freeway detector)
    WEAK      within MAX_M but farther, or on a minor road — priced, but flagged
    REJECTED  outside the scenario bbox, no drivable edge within MAX_M, or coordinate mismatch

Rejected detectors are listed and never priced. The opposite carriageway, when within
OPPOSITE_M, is recorded as `opposite_edge` so the direction ambiguity is visible.

    python src/pipeline/city/sensor_map.py --dataset user:los_angeles --city los_angeles_metr
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

UPSTREAM = Path.home() / ".dhakaflow/upstream/DCRNN"
LOCATIONS = UPSTREAM / "data/sensor_graph/graph_sensor_locations.csv"
GOOD_M, MAX_M, OPPOSITE_M = 60.0, 200.0, 80.0
MAJOR = {"highway.motorway", "highway.motorway_link", "highway.trunk", "highway.trunk_link", "highway.primary", "highway.primary_link", "highway.secondary"}


def sha(p: Path, n: int = 12) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:n]


def upstream_pin() -> dict:
    try:
        rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=UPSTREAM, capture_output=True, text=True).stdout.strip()
        url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=UPSTREAM, capture_output=True, text=True).stdout.strip()
    except Exception:                       # noqa: BLE001
        rev, url = None, None
    return {"repo": url, "commit": rev, "file": str(LOCATIONS), "file_sha256": sha(LOCATIONS) if LOCATIONS.exists() else None}


def genuine_rows() -> list[dict]:
    if not LOCATIONS.exists():
        raise FileNotFoundError(f"genuine detector metadata missing: {LOCATIONS} (pin the DCRNN repository first)")
    return list(csv.DictReader(open(LOCATIONS)))


def match_nodes(meta: dict, rows: list[dict], tol: float = 1e-5) -> list[dict]:
    """Dataset node i <-> published row i, accepted only when the coordinates agree."""
    out = []
    for i, (node, c) in enumerate(zip(meta["nodes"], meta["coords"])):
        r = rows[i] if i < len(rows) else None
        ok = r is not None and abs(float(r["latitude"]) - c[0]) < tol and abs(float(r["longitude"]) - c[1]) < tol
        out.append({"node": node, "node_index": i, "sensor_id": r["sensor_id"] if ok else None, "lat": float(c[0]), "lon": float(c[1]),
                    "coordinate_match": ok, "published_row": i if ok else None})
    return out


def snap(net, lat: float, lon: float):
    x, y = net.convertLonLat2XY(lon, lat)
    cands = [(e, d) for e, d in net.getNeighboringEdges(x, y, MAX_M) if e.allows("passenger") and not e.getID().startswith(":")]
    if not cands:
        return None, None, []
    cands.sort(key=lambda t: t[1])
    e, d = cands[0]
    return e, float(d), cands


def build(dataset: str, city_id: str, out: Path | None = None) -> dict:
    import sumolib
    sys.path.insert(0, str(REPO / "src/dashboard/backend"))
    import user_datasets
    from pipeline.city.sumo_scenario import scenario_dir
    meta = user_datasets.load_meta(dataset.split(":", 1)[1])
    if not meta or not meta.get("coords"):
        raise RuntimeError(f"{dataset} has no coordinates")
    man = json.loads((scenario_dir(city_id) / "MANIFEST.json").read_text())
    net_path = REPO / man["files"]["net"]
    net = sumolib.net.readNet(str(net_path))
    s, w, n, e_ = man["bbox"]
    rows = genuine_rows()
    records = []
    for m in match_nodes(meta, rows):
        rec = {**m, "edge": None, "snap_m": None, "edge_type": None, "speed_limit_mps": None, "edge_length_m": None, "opposite_edge": None, "quality": "REJECTED", "reason": None}
        if not m["coordinate_match"]:
            rec["reason"] = "coordinates do not match the published row at this index"
        elif not (s <= m["lat"] <= n and w <= m["lon"] <= e_):
            rec["reason"] = "outside the scenario bbox"
        else:
            e, d, cands = snap(net, m["lat"], m["lon"])
            if e is None:
                rec["reason"] = f"no drivable edge within {MAX_M:.0f} m"
            else:
                t = e.getType() or ""
                rec.update(edge=e.getID(), snap_m=round(d, 1), edge_type=t, speed_limit_mps=round(e.getSpeed(), 3), edge_length_m=round(e.getLength(), 1))
                opp = next((o for o, od in cands if o.getID() != e.getID() and od <= OPPOSITE_M and o.getFromNode().getID() == e.getToNode().getID() and o.getToNode().getID() == e.getFromNode().getID()), None)
                if opp is None:
                    opp = next((o for o, od in cands if o.getID() != e.getID() and od <= OPPOSITE_M and (o.getType() or "") == t), None)
                rec["opposite_edge"] = opp.getID() if opp else None
                if d <= GOOD_M and t in MAJOR:
                    rec["quality"] = "GOOD"
                elif d <= MAX_M:
                    rec["quality"] = "WEAK"; rec["reason"] = ("farther than %.0f m" % GOOD_M) if d > GOOD_M else f"nearest edge is {t or 'untyped'}, not a major road"
        records.append(rec)
    counts = {q: sum(1 for r in records if r["quality"] == q) for q in ("GOOD", "WEAK", "REJECTED")}
    result = {"dataset": dataset, "city_id": city_id, "network": str(net_path.relative_to(REPO)), "network_hash": sha(net_path), "bbox": man["bbox"],
              "source": upstream_pin(), "matching": "dataset node i <-> published row i, accepted only when latitude and longitude agree within 1e-5",
              "thresholds": {"good_m": GOOD_M, "max_m": MAX_M, "opposite_m": OPPOSITE_M, "major_types": sorted(MAJOR)},
              "counts": counts, "records": records, "generated_utc": datetime.now(timezone.utc).isoformat()}
    out = out or (scenario_dir(city_id) / "sensor_to_edge.json")
    out.write_text(json.dumps(result, indent=1))
    result["file"] = str(out.relative_to(REPO)) if out.is_relative_to(REPO) else str(out)
    return result


def find_for_dataset(dataset: str) -> dict | None:
    """The mapping file that links this dataset to a generated scenario, if one exists."""
    from pipeline.city.registry import CITY_DIR
    if not CITY_DIR.exists():
        return None
    for f in sorted(CITY_DIR.glob("*/sumo/sensor_to_edge.json")):
        try:
            d = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if d.get("dataset") == dataset:
            d["file"] = str(f.relative_to(REPO)); d["file_hash"] = sha(f)
            return d
    return None


def corridor_map(mapping: dict, include_weak: bool = True) -> tuple[dict, dict, dict]:
    """corridor_map {node: {edges}}, free speed per node (the edge's speed limit, m/s), and the
    per-node detector facts for provenance — only GOOD (and optionally WEAK) detectors."""
    cmap, free, facts = {}, {}, {}
    for r in mapping.get("records", []):
        if r["quality"] == "GOOD" or (include_weak and r["quality"] == "WEAK"):
            cmap[r["node"]] = {"edges": [r["edge"]], "sensor_id": r["sensor_id"], "quality": r["quality"]}
            free[r["node"]] = float(r["speed_limit_mps"])
            facts[r["node"]] = {k: r[k] for k in ("sensor_id", "lat", "lon", "edge", "snap_m", "edge_type", "edge_length_m", "speed_limit_mps", "quality", "opposite_edge")}
    return cmap, free, facts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="user:los_angeles")
    p.add_argument("--city", default="los_angeles_metr")
    a = p.parse_args()
    r = build(a.dataset, a.city)
    print(f"[sensor_map] {a.dataset} on {a.city}: {r['counts']} -> {r['file']}")
    for rec in r["records"]:
        print(f"  {rec['node']:<10} {rec['sensor_id'] or '—':<8} {rec['lat']:.5f},{rec['lon']:.5f}  {rec['quality']:<8} edge={rec['edge']} snap={rec['snap_m']} m type={rec['edge_type']} {rec['reason'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
