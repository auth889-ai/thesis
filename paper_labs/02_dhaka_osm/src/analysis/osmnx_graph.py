"""Branch A — OSMnx analysis graph built from the SAME archived snapshot.

Reference: Boeing (2025), Geographical Analysis 57(4):567-577, DOI
10.1111/gean.70009. Pinned osmnx==2.1.1 (v2.1.1 = 2fc39cb2…).

The graph is built with `graph_from_xml` on the archived .osm file — never a
fresh download — enforcing the single-snapshot rule of DESIGN_V2 §2.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

#: vehicular highway classes used for the cross-comparison on BOTH branches
VEHICULAR = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified",
    "residential", "living_street", "service",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary_link",
}


def _tag(data: dict, key: str) -> str | None:
    v = data.get(key)
    if isinstance(v, list):
        v = v[0] if v else None
    return v


def build_graph(osm_file: Path, keep_largest_wcc: bool = True):
    """Archived snapshot -> simplified directed vehicular graph.

    With `keep_largest_wcc` the graph is pruned to its largest weakly connected
    component, mirroring netconvert's `--keep-edges.components 1` so the two
    branches compare the SAME universe (X1/X7 would otherwise measure the
    deliberate pruning, not construction disagreement). The pruned share is
    recorded on the graph as `G.graph["component_prune"]`.
    """
    import networkx as nx
    import osmnx as ox

    G = ox.graph_from_xml(str(osm_file), simplify=True, retain_all=True)
    drop = [
        (u, v, k) for u, v, k, d in G.edges(keys=True, data=True)
        if _tag(d, "highway") not in VEHICULAR
    ]
    G.remove_edges_from(drop)
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    if keep_largest_wcc and G.number_of_nodes():
        wccs = sorted(nx.weakly_connected_components(G), key=len, reverse=True)
        n_edges_before = G.number_of_edges()
        keep = wccs[0]
        G.remove_nodes_from([n for n in list(G.nodes) if n not in keep])
        G.graph["component_prune"] = {
            "n_components_raw": len(wccs),
            "edges_dropped": n_edges_before - G.number_of_edges(),
            "edges_dropped_fraction": round(
                (n_edges_before - G.number_of_edges()) / max(n_edges_before, 1), 4),
            "mirrors": "netconvert --keep-edges.components 1",
        }
    return G


def graph_metrics(G, osm_file: Path, out_path: Path | None = None) -> dict:
    """Topology + attribute metrics for cross-validation and region scoring."""
    import networkx as nx

    n_edges = G.number_of_edges()
    length_km = sum(d.get("length", 0.0) for _, _, d in G.edges(data=True)) / 1000.0

    hier = Counter()
    lane_km = 0.0
    tagged = {"lanes": 0, "maxspeed": 0, "name": 0}
    oneway_edges = 0
    for _, _, d in G.edges(data=True):
        hw = _tag(d, "highway") or "unknown"
        hier[hw] += d.get("length", 0.0)
        lanes = _tag(d, "lanes")
        if lanes is not None:
            tagged["lanes"] += 1
            try:
                lane_km += d.get("length", 0.0) * max(int(str(lanes)), 1) / 1000.0
            except ValueError:
                lane_km += d.get("length", 0.0) / 1000.0
        if _tag(d, "maxspeed") is not None:
            tagged["maxspeed"] += 1
        if _tag(d, "name") is not None:
            tagged["name"] += 1
        ow = d.get("oneway")
        if ow is True or (isinstance(ow, str) and ow.lower() in ("yes", "true", "1", "-1")):
            oneway_edges += 1

    total_len = sum(hier.values()) or 1.0
    hierarchy_share = {k: round(v / total_len, 4) for k, v in hier.most_common()}

    sccs = list(nx.strongly_connected_components(G))
    wccs = list(nx.weakly_connected_components(G))
    largest_scc = max(sccs, key=len) if sccs else set()
    scc_sub = G.subgraph(largest_scc)
    scc_edge_fraction = scc_sub.number_of_edges() / n_edges if n_edges else 0.0

    und = G.to_undirected()
    dead_ends = sum(1 for n in und.nodes if und.degree(n) == 1)

    # signalised nodes straight from the snapshot (exact, parser-independent)
    signals = set()
    for _, elem in ET.iterparse(str(osm_file), events=("end",)):
        if elem.tag == "node":
            for t in elem.findall("tag"):
                if t.get("k") == "highway" and t.get("v") == "traffic_signals":
                    signals.add(int(elem.get("id")))
            elem.clear()

    report = {
        "osmnx_version": __import__("osmnx").__version__,
        "n_nodes": G.number_of_nodes(),
        "n_edges": n_edges,
        "length_km": round(length_km, 2),
        "lane_km_tagged_only": round(lane_km, 2),
        "hierarchy_length_share": hierarchy_share,
        "oneway_edge_fraction": round(oneway_edges / n_edges, 4) if n_edges else None,
        "attribute_completeness": {
            k: round(v / n_edges, 4) if n_edges else None for k, v in tagged.items()},
        "n_scc": len(sccs),
        "n_wcc": len(wccs),
        "largest_scc_nodes": len(largest_scc),
        "largest_scc_edge_fraction": round(scc_edge_fraction, 4),
        "dead_end_nodes": dead_ends,
        "osm_traffic_signal_nodes": len(signals),
        "component_prune": G.graph.get("component_prune"),
    }
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2))
    report["_signal_node_ids"] = signals          # for cross-validation, not serialized
    return report


def shortest_and_k_paths(G, od_lonlat_pairs: list[tuple[tuple[float, float], tuple[float, float]]],
                         k: int = 3) -> list[dict]:
    """Shortest length + k-shortest distinctness for fixed O-D pairs (lon, lat)."""
    import networkx as nx
    import osmnx as ox

    Gp = ox.project_graph(G)
    results = []
    for (olon, olat), (dlon, dlat) in od_lonlat_pairs:
        try:
            o = ox.distance.nearest_nodes(G, olon, olat)
            d = ox.distance.nearest_nodes(G, dlon, dlat)
        except Exception as exc:                    # noqa: BLE001
            results.append({"error": f"nearest_nodes: {exc}"})
            continue
        entry: dict = {"o_node": int(o), "d_node": int(d)}
        try:
            path = nx.shortest_path(G, o, d, weight="length")
            entry["shortest_length_m"] = float(round(sum(
                min(dd.get("length", 0.0) for dd in G[u][v].values())
                for u, v in zip(path[:-1], path[1:])), 1))
            entry["routable"] = True
        except nx.NetworkXNoPath:
            entry.update(routable=False, shortest_length_m=None)
            results.append(entry)
            continue
        try:
            kpaths = []
            for p in ox.routing.k_shortest_paths(G, o, d, k=k, weight="length"):
                kpaths.append(tuple(p))
                if len(kpaths) >= k:
                    break
            distinct = len({p for p in kpaths})
            entry["k_paths_found"] = len(kpaths)
            entry["k_paths_distinct"] = distinct
        except Exception as exc:                    # noqa: BLE001
            entry["k_paths_error"] = str(exc)
        results.append(entry)
    del Gp
    return results


def top_central_junction_osmids(G, n: int = 10, sample_k: int = 500, seed: int = 42) -> list[int]:
    """Top-n betweenness-central nodes (OSM ids), sampled approximation.

    Exact betweenness is O(nm) in pure Python; a seeded k-sample keeps this
    tractable and deterministic (documented in ASSUMPTIONS).
    """
    import networkx as nx

    k = min(sample_k, G.number_of_nodes())
    bc = nx.betweenness_centrality(G, k=k, weight="length", seed=seed)
    return [int(n_) for n_, _ in sorted(bc.items(), key=lambda kv: -kv[1])[:n]]


def snapshot_context_census(osm_file: Path) -> dict:
    """Count selection-relevant context features in the SAME snapshot."""
    counts = Counter()
    for _, elem in ET.iterparse(str(osm_file), events=("end",)):
        if elem.tag == "node":
            tags = {t.get("k"): t.get("v") for t in elem.findall("tag")}
            if tags.get("highway") == "bus_stop":
                counts["bus_stops"] += 1
            if tags.get("amenity") == "hospital":
                counts["hospitals"] += 1
            if tags.get("man_made") == "surveillance":
                counts["surveillance_cameras"] += 1
            if tags.get("highway") == "crossing":
                counts["pedestrian_crossings"] += 1
            elem.clear()
        elif elem.tag == "relation":
            tags = {t.get("k"): t.get("v") for t in elem.findall("tag")}
            if tags.get("route") == "bus":
                counts["bus_route_relations"] += 1
            elem.clear()
        elif elem.tag == "way":
            tags = {t.get("k"): t.get("v") for t in elem.findall("tag")}
            if tags.get("amenity") == "hospital":
                counts["hospitals"] += 1
            elem.clear()
    return dict(counts)
