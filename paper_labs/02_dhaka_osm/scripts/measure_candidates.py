#!/usr/bin/env python3
"""Measure all five pre-registered candidate regions with the SAME pipeline.

For each candidate (src/regions.py, frozen before measurement):
  1. one Overpass snapshot (network + context features) + sha256
  2. Branch A: OSMnx graph from that exact snapshot
  3. Branch B: SUMO network via netconvert --lefthand from that exact snapshot
  4. C1–C8 criterion metrics -> outputs/lab02_candidates/decision_table.{json,csv}

No candidate is skipped and no criterion is applied selectively (DECISION 2).
Selection itself happens afterwards in REGION_SELECTION.md with the recorded
numbers; tie-break C1 -> C3 -> C5 -> C2, with future real camera/data
availability (C5) as the stated tie-breaker.
"""
from __future__ import annotations

import csv
import json
import random
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB))

from src.regions import CANDIDATES                              # noqa: E402
from src.osm.download import download_osm, sha256_file          # noqa: E402
from src.network.build import build_network                     # noqa: E402
from src.analysis.osmnx_graph import (                          # noqa: E402
    build_graph, graph_metrics, shortest_and_k_paths, snapshot_context_census)
from src.analysis.cross_validate import sumo_vehicular_metrics  # noqa: E402
from src.validation.network_checks import validate_network      # noqa: E402

OUT = LAB / "outputs" / "lab02_candidates"

MAJOR = {"motorway", "trunk", "primary", "secondary",
         "motorway_link", "trunk_link", "primary_link", "secondary_link"}


def _od_pairs_for(bbox: dict, n: int = 6, seed: int = 42):
    """Deterministic O-D sample: corners + midpoints inset 15% into the bbox."""
    rng = random.Random(seed)
    s, w, no, e = bbox["south"], bbox["west"], bbox["north"], bbox["east"]
    dy, dx = (no - s) * 0.15, (e - w) * 0.15
    pts = [(w + dx, s + dy), (e - dx, no - dy), (w + dx, no - dy),
           (e - dx, s + dy), ((w + e) / 2, s + dy), ((w + e) / 2, no - dy)]
    pairs = []
    for i in range(n):
        o = pts[i % len(pts)]
        d = pts[(i + 1 + rng.randrange(2)) % len(pts)]
        if o == d:
            d = pts[(i + 3) % len(pts)]
        pairs.append((o, d))
    return pairs


def measure(rid: str, spec: dict, workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    osm_file = workdir / f"{rid}.osm"
    t0 = time.time()

    # 1. snapshot (skip re-download if archived + checksummed already)
    manifest_p = workdir / f"{rid}_manifest.json"
    if osm_file.exists() and manifest_p.exists():
        manifest = json.loads(manifest_p.read_text())
        if manifest.get("sha256") == sha256_file(osm_file):
            print(f"  [{rid}] snapshot already archived, checksum verified")
        else:
            manifest = download_osm(spec["bbox"], osm_file, manifest_p,
                                    include_context=True)
    else:
        manifest = download_osm(spec["bbox"], osm_file, manifest_p,
                                include_context=True)
    print(f"  [{rid}] snapshot {manifest['bytes']/1e6:.1f} MB sha256={manifest['sha256'][:12]}…")

    # 2. Branch A — OSMnx from the SAME file
    G = build_graph(osm_file)
    am = graph_metrics(G, osm_file, workdir / f"{rid}_osmnx_metrics.json")
    context = snapshot_context_census(osm_file)
    routes = shortest_and_k_paths(G, _od_pairs_for(spec["bbox"]), k=3)

    # 3. Branch B — SUMO from the SAME file
    net_file = workdir / f"{rid}.net.xml"
    build = build_network(osm_file, net_file, workdir / "netconvert")
    bm = sumo_vehicular_metrics(net_file)
    vres = validate_network(net_file, workdir / "validation")

    # 4. C1–C8
    major_share_len = sum(v for k, v in bm["hierarchy_length_share"].items()
                          if k in MAJOR)
    routable = [r for r in routes if r.get("routable")]
    with_alts = sum(1 for r in routes if r.get("k_paths_distinct", 0) >= 2)
    evaluated = sum(1 for r in routes if "k_paths_distinct" in r)

    row = {
        "region": rid,
        "name": spec["name"],
        "snapshot_sha256": manifest["sha256"],
        "snapshot_bytes": manifest["bytes"],
        "endpoint": manifest["endpoint"],
        # C1 control usefulness
        "C1_n_tls": vres["n_tls"],
        "C1_osm_signal_nodes": am["osm_traffic_signal_nodes"],
        # C2 hierarchy
        "C2_major_road_length_share": round(major_share_len, 4),
        "C2_lane_km": bm["lane_km"],
        # C3 route choice
        "C3_od_pairs_with_2plus_alternatives": f"{with_alts}/{evaluated}",
        "C3_alt_fraction": round(with_alts / evaluated, 3) if evaluated else None,
        # C4 connectivity
        "C4_scc_edge_fraction_sumo": vres["scc_edge_fraction"],
        "C4_scc_edge_fraction_osmnx": am["largest_scc_edge_fraction"],
        "C4_dead_end_fraction": round(
            vres["n_dead_ends"] / max(vres["n_junctions"], 1), 4),
        # C5 camera feasibility (tie-breaker)
        "C5_surveillance_nodes": context.get("surveillance_cameras", 0),
        "C5_signalised_major_proxy": vres["n_tls"] if major_share_len >= 0.15 else 0,
        # C6 public transport
        "C6_bus_stops": context.get("bus_stops", 0),
        "C6_bus_route_relations": context.get("bus_route_relations", 0),
        # C7 emergency / pedestrian
        "C7_hospitals": context.get("hospitals", 0),
        "C7_pedestrian_crossings": context.get("pedestrian_crossings", 0),
        # C8 auditability
        "C8_n_edges": vres["n_edges"],
        "C8_n_junctions": vres["n_junctions"],
        "C8_length_km": bm["length_km"],
        # extras for the report
        "osmnx_n_edges": am["n_edges"],
        "oneway_fraction_sumo": bm["oneway_edge_fraction"],
        "routable_od": f"{len(routable)}/{len(routes)}",
        "netconvert_warnings": build["warnings"],
        "measure_seconds": round(time.time() - t0, 1),
    }
    (workdir / f"{rid}_row.json").write_text(json.dumps(row, indent=2, default=str))
    return row


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for rid, spec in CANDIDATES.items():
        print(f"[measure] {rid}: {spec['name']}")
        rows.append(measure(rid, spec, OUT / rid))

    (OUT / "decision_table.json").write_text(json.dumps(rows, indent=2, default=str))
    with open(OUT / "decision_table.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        for r in rows:
            wr.writerow({k: (json.dumps(v) if isinstance(v, dict) else v)
                         for k, v in r.items()})
    print(f"[measure] decision table -> {OUT / 'decision_table.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
