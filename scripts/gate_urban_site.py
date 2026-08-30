#!/usr/bin/env python3
"""GATE: URBAN_REAL_TRAJECTORY_SITE — real pNEUMA vehicles on real Athens roads.

Data: official pNEUMA d8 2018-10-29 08:00-08:30 (open-traffic.epfl.ch).
Map-matching: leuvenmapmatching (upstream, DistanceMatcher) on the OSM road
graph of the data's own bounding box. No SUMO, no control, no forecasting.
Outputs: artifacts/urban_real_site/real_trajectory_state.json + PNG evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SP = Path("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad/urban")
CSV = SP / "d8.csv"
OSM = SP / "athens_d8.osm"
OUT = REPO / "artifacts/urban_real_site"
DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary",
            "unclassified", "residential", "living_street", "primary_link",
            "secondary_link", "tertiary_link", "trunk_link", "motorway_link"}
MATCH_T0, MATCH_T1 = 300.0, 480.0        # 3-minute matching interval (in A)
SPLITS = {"A_calibration": [0, 600], "B_validation": [600, 1200],
          "C_sealed_test": [1200, 1800]}


def load_osm():
    root = ET.parse(str(OSM)).getroot()
    nodes, ways, signals, names = {}, [], set(), {}
    for n in root.iter("node"):
        nodes[n.get("id")] = (float(n.get("lat")), float(n.get("lon")))
        for tg in n.iter("tag"):
            if tg.get("k") == "highway" and tg.get("v") == "traffic_signals":
                signals.add(n.get("id"))
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        if tags.get("highway") in DRIVABLE:
            nds = [nd.get("ref") for nd in w.iter("nd") if nd.get("ref") in nodes]
            if len(nds) >= 2:
                ways.append((w.get("id"), nds, tags))
                names[w.get("id")] = tags.get("name", "")
    return nodes, ways, signals, names


def build_map(nodes, ways):
    from leuvenmapmatching.map.inmem import InMemMap
    m = InMemMap("athens_d8", use_latlon=True, use_rtree=False, index_edges=True)
    used = set()
    for _, nds, tags in ways:
        oneway = tags.get("oneway") in ("yes", "true", "1")
        for nid in nds:
            if nid not in used:
                la, lo = nodes[nid]
                m.add_node(nid, (la, lo))
                used.add(nid)
        for a, b in zip(nds, nds[1:]):
            m.add_edge(a, b)
            if not oneway:
                m.add_edge(b, a)
    m.purge()
    return m


def main() -> None:
    t_wall = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    from research.urban.pneuma_provider import parse
    from leuvenmapmatching.matcher.distance import DistanceMatcher

    data_hash = hashlib.sha256(CSV.read_bytes()).hexdigest()
    print("[1/5] parsing real trajectories …")
    tracks = list(parse(str(CSV), hz=1.0))
    lats = [s.lat for tr in tracks for s in tr.samples[::10]]
    lons = [s.lon for tr in tracks for s in tr.samples[::10]]
    bbox = (min(lats), min(lons), max(lats), max(lons))
    dur = max(s.t for tr in tracks for s in (tr.samples[-1],))
    types = defaultdict(int)
    for tr in tracks:
        types[tr.vtype] += 1

    print("[2/5] OSM graph + upstream matcher …")
    nodes, ways, signals, names = load_osm()
    mmap = build_map(nodes, ways)
    matcher_conf = dict(max_dist=45, max_dist_init=60, obs_noise=8,
                        obs_noise_ne=25, min_prob_norm=0.001,
                        non_emitting_states=True)

    print("[3/5] map-matching the interval "
          f"{MATCH_T0:.0f}-{MATCH_T1:.0f}s (upstream DistanceMatcher) …")
    seg_speeds = defaultdict(list)
    matched_rows, n_matched, n_tried = [], 0, 0
    node_way = defaultdict(set)
    for wid, nds, _ in ways:
        for nid in nds:
            node_way[nid].add(wid)
    for tr in tracks:
        pts = [(s.lat, s.lon, s.t, s.speed_kmh) for s in tr.samples
               if MATCH_T0 <= s.t <= MATCH_T1]
        if len(pts) < 12:
            continue
        n_tried += 1
        if n_tried > 400:
            break
        path = [(p[0], p[1]) for p in pts]
        matcher = DistanceMatcher(mmap, **matcher_conf)
        try:
            states, _ = matcher.match(path)
        except Exception:
            continue
        if not states or len(states) < len(path) * 0.5:
            continue
        n_matched += 1
        for (la, lo, t, sp), st in zip(pts, states):
            a, b = st
            seg_speeds[(a, b)].append(sp)
            wids = node_way[a] & node_way[b]
            wid = sorted(wids)[0] if wids else ""
            matched_rows.append(
                {"vehicle_id": tr.vid, "type": tr.vtype,
                 "timestamp_s": round(t, 2), "lat": la, "lon": lo,
                 "speed_kmh": round(sp, 1),
                 "matched_road": {"osm_way": wid,
                                  "name": names.get(wid, ""),
                                  "node_a": a, "node_b": b}})
    print(f"    matched {n_matched}/{n_tried} vehicles, "
          f"{len(matched_rows)} samples, {len(seg_speeds)} segments")

    # signalized intersections touched by matched segments
    matched_nodes = {n for ab in seg_speeds for n in ab}
    sig_hit = sorted(matched_nodes & signals)

    # congestion evidence: slowest matched segments
    cong = sorted(((sum(v) / len(v), len(v), ab)
                   for ab, v in seg_speeds.items() if len(v) >= 30))[:10]

    # alternative paths on the drivable graph between two far-apart
    # signalized junctions actually used by traffic
    import networkx as nx
    G = nx.DiGraph()
    for _, nds, tags in ways:
        ow = tags.get("oneway") in ("yes", "true", "1")
        for a, b in zip(nds, nds[1:]):
            d = math.dist(nodes[a], nodes[b])
            G.add_edge(a, b, w=d)
            if not ow:
                G.add_edge(b, a, w=d)
    alt_paths = []
    if len(sig_hit) >= 2:
        import itertools
        best = max(itertools.combinations(sig_hit[:12], 2),
                   key=lambda p: math.dist(nodes[p[0]], nodes[p[1]]))
        try:
            ps = list(nx.shortest_simple_paths(G, best[0], best[1],
                                               weight="w"))
            seen_sets = []
            for p in ps:
                if all(len(set(p) & s) < 0.7 * len(p) for s in seen_sets):
                    alt_paths.append(p)
                    seen_sets.append(set(p))
                if len(alt_paths) >= 3 or len(seen_sets) > 40:
                    break
        except Exception as e:                     # noqa: BLE001
            print("paths:", e)

    # sealed splits: hash C samples WITHOUT analysis
    def interval_hash(t0, t1):
        h = hashlib.sha256()
        for tr in tracks:
            for s in tr.samples:
                if t0 <= s.t < t1:
                    h.update(f"{tr.vid}:{s.t}:{s.lat}:{s.lon}".encode())
        return h.hexdigest()
    splits = {k: {"t_range_s": v, "sha256": interval_hash(*v)}
              for k, v in SPLITS.items()}

    print("[4/5] visualization (evidence, not UI) …")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 7))
    for _, nds, _ in ways:
        xs = [nodes[n][1] for n in nds]
        ys = [nodes[n][0] for n in nds]
        ax.plot(xs, ys, color="#cccccc", lw=0.8, zorder=1)
    for nid in sig_hit:
        ax.scatter([nodes[nid][1]], [nodes[nid][0]], marker="s", s=42,
                   c="#d9a23a", zorder=4)
    shown = 0
    for tr in tracks:
        pts = [(s.lon, s.lat, s.speed_kmh) for s in tr.samples
               if MATCH_T0 <= s.t <= MATCH_T1]
        if len(pts) < 12:
            continue
        xs, ys, sp = zip(*pts)
        ax.scatter(xs, ys, c=sp, cmap="RdYlGn", vmin=0, vmax=50, s=2, zorder=3)
        shown += 1
        if shown >= 120:
            break
    for p in alt_paths[:3]:
        xs = [nodes[n][1] for n in p]
        ys = [nodes[n][0] for n in p]
        ax.plot(xs, ys, lw=2.2, alpha=0.7, zorder=2)
    ax.set_title("pNEUMA d8 (Athens) — REAL measured vehicles "
                 f"{MATCH_T0:.0f}-{MATCH_T1:.0f}s · squares=signals · "
                 "colored dots=real positions (green=fast, red=stopped)")
    ax.set_aspect(1 / math.cos(math.radians(37.99)))
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(OUT / "real_trajectories.png", dpi=150)

    print("[5/5] artifact …")
    art = {
        "gate": "URBAN_REAL_TRAJECTORY_SITE",
        "dataset": "pNEUMA (Barmpounakis & Geroliminis 2020, TR-C) d8 "
                   "2018-10-29 08:00-08:30",
        "source": "open-traffic.epfl.ch official downloader endpoint",
        "data_sha256": data_hash,
        "bbox": bbox, "duration_s": dur,
        "vehicles_parsed": len(tracks), "vehicle_types": dict(types),
        "matching": {"tool": "leuvenmapmatching 1.1.4 DistanceMatcher",
                     "interval_s": [MATCH_T0, MATCH_T1],
                     "vehicles_matched": n_matched,
                     "vehicles_tried": n_tried,
                     "samples_matched": len(matched_rows),
                     "segments_matched": len(seg_speeds)},
        "signalized_intersections_in_matched_area": len(sig_hit),
        "congested_segments_evidence":
            [{"mean_kmh": round(m, 1), "n": n,
              "nodes": ab} for m, n, ab in cong[:6]],
        "alternative_paths": [{"n_nodes": len(p), "from": p[0], "to": p[-1]}
                              for p in alt_paths],
        "splits": splits,
        "sample_measurements": matched_rows[:400],
    }
    (OUT / "real_trajectory_state.json").write_text(json.dumps(art, indent=1))
    print(json.dumps({k: art[k] for k in
                      ("vehicles_parsed", "vehicle_types", "matching",
                       "signalized_intersections_in_matched_area",
                       "alternative_paths")}, indent=1))
    print("congested:", art["congested_segments_evidence"][:3])
    print("wall", round(time.time() - t_wall, 1), "s")
    ok = (len(tracks) > 0 and n_matched > 0 and len(seg_speeds) > 0
          and len(sig_hit) >= 2 and len(alt_paths) >= 2)
    print("RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
