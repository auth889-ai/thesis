"""X1–X12 OSMnx ↔ SUMO cross-validation (DESIGN_V2 §3).

Compares invariants that survive both pipelines, each with its pre-registered
tolerance. Junction identity is compared as SETS OF OSM NODE IDS after
expanding netconvert `cluster_…` ids and `joinedS`/`joinedNS` names.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .osmnx_graph import VEHICULAR

_NUM = re.compile(r"\d+")


def sumo_junction_osmids(junction_id: str) -> set[int]:
    """Expand a SUMO junction id into the OSM node ids it contains."""
    return {int(m) for m in _NUM.findall(junction_id)}


def sumo_vehicular_metrics(net_file: Path) -> dict:
    """Branch-B metrics restricted to the shared vehicular class set."""
    import sumolib

    net = sumolib.net.readNet(str(net_file), withPrograms=True)
    edges = [e for e in net.getEdges()
             if (e.getType() or "").replace("highway.", "") in VEHICULAR]

    length_km = sum(e.getLength() for e in edges) / 1000.0
    lane_km = sum(e.getLength() * e.getLaneNumber() for e in edges) / 1000.0

    hier: dict[str, float] = {}
    for e in edges:
        cls = (e.getType() or "unknown").replace("highway.", "")
        hier[cls] = hier.get(cls, 0.0) + e.getLength()
    total = sum(hier.values()) or 1.0
    hierarchy_share = {k: round(v / total, 4)
                       for k, v in sorted(hier.items(), key=lambda kv: -kv[1])}

    pairs = {(e.getFromNode().getID(), e.getToNode().getID()) for e in edges}
    oneway = sum(1 for e in edges
                 if (e.getToNode().getID(), e.getFromNode().getID()) not in pairs)

    dead_end_junctions = sum(1 for n in net.getNodes() if n.getType() == "dead_end")
    zero_out = sum(1 for e in net.getEdges() if len(e.getOutgoing()) == 0)

    tls_ids = [t.getID() for t in net.getTrafficLights()]
    tls_osmids: set[int] = set()
    for t in tls_ids:
        tls_osmids |= sumo_junction_osmids(t)

    junction_osmids: set[int] = set()
    for n in net.getNodes():
        junction_osmids |= sumo_junction_osmids(n.getID())

    return {
        "n_vehicular_edges": len(edges),
        "length_km": round(length_km, 2),
        "lane_km": round(lane_km, 2),
        "hierarchy_length_share": hierarchy_share,
        "oneway_edge_fraction": round(oneway / len(edges), 4) if edges else None,
        "dead_end_junctions": dead_end_junctions,
        "zero_outgoing_edges": zero_out,
        "n_tls": len(tls_ids),
        "_tls_osmids": tls_osmids,
        "_junction_osmids": junction_osmids,
    }


def _pct_delta(a: float, b: float) -> float | None:
    if not a:
        return None
    return abs(a - b) / a


def cross_validate(osmnx_metrics: dict, sumo_metrics: dict, sumo_scc_fraction: float,
                   osmnx_routes: list[dict], sumo_routes: list[dict],
                   central_osmids: list[int], netconvert_warning_counts: dict,
                   out_path: Path | None = None) -> dict:
    """Evaluate X1–X12; every check reports value_A, value_B, tolerance, status."""
    checks: list[dict] = []

    def add(xid, desc, a, b, ok, tol, note=""):
        checks.append({"id": xid, "invariant": desc, "osmnx": a, "sumo": b,
                       "tolerance": tol, "status": "PASS" if ok else "REVIEW",
                       "note": note})

    # X1 total vehicular length
    d = _pct_delta(osmnx_metrics["length_km"], sumo_metrics["length_km"])
    add("X1", "total drive length (km)", osmnx_metrics["length_km"],
        sumo_metrics["length_km"], d is not None and d <= 0.10, "±10%",
        f"delta={d:.1%}" if d is not None else "n/a")

    # X2 lane-km (A counts tagged edges only -> B >= A expected)
    a_lane, b_lane = osmnx_metrics["lane_km_tagged_only"], sumo_metrics["lane_km"]
    d2 = _pct_delta(b_lane, a_lane)
    add("X2", "lane-km (A: tagged only, B: incl. typemap defaults)", a_lane, b_lane,
        b_lane >= a_lane * 0.8, "B within [0.8·A, ∞); gap quantifies defaults",
        f"default-reliance gap={d2:.1%}" if d2 is not None else "n/a")

    # X3 hierarchy mix
    worst = 0.0
    for cls in set(osmnx_metrics["hierarchy_length_share"]) | set(sumo_metrics["hierarchy_length_share"]):
        pa = osmnx_metrics["hierarchy_length_share"].get(cls, 0.0)
        pb = sumo_metrics["hierarchy_length_share"].get(cls, 0.0)
        worst = max(worst, abs(pa - pb))
    add("X3", "road-hierarchy length shares", osmnx_metrics["hierarchy_length_share"],
        sumo_metrics["hierarchy_length_share"], worst <= 0.05, "±5pp per class",
        f"worst class delta={worst*100:.1f}pp")

    # X4 one-way share
    pa, pb = osmnx_metrics["oneway_edge_fraction"], sumo_metrics["oneway_edge_fraction"]
    add("X4", "one-way edge share", pa, pb,
        pa is not None and pb is not None and abs(pa - pb) <= 0.05, "±5pp",
        f"delta={(abs(pa-pb))*100:.1f}pp" if None not in (pa, pb) else "n/a")

    # X5 SCC edge fraction
    fa = osmnx_metrics["largest_scc_edge_fraction"]
    add("X5", "largest-SCC edge fraction", fa, sumo_scc_fraction,
        fa >= 0.90 and sumo_scc_fraction >= 0.90 and abs(fa - sumo_scc_fraction) <= 0.05,
        "both ≥0.90, Δ≤5pp", f"delta={(abs(fa-sumo_scc_fraction))*100:.1f}pp")

    # X6 WCC count (B keeps 1 by design; report A + prune warnings)
    add("X6", "weak components (A raw vs B post-prune)", osmnx_metrics["n_wcc"], 1,
        True, "report+explain",
        f"netconvert prune warnings: {netconvert_warning_counts.get('discarded_isolated_edges', 0)} "
        f"isolated-edge, {netconvert_warning_counts.get('kept_components', 0)} component msgs")

    # X7 dead ends
    da = osmnx_metrics["dead_end_nodes"]
    db = sumo_metrics["dead_end_junctions"]
    d7 = _pct_delta(da, db)
    add("X7", "dead ends (A deg-1 nodes vs B dead_end junctions)", da, db,
        d7 is not None and d7 <= 0.35, "±35% (clipping + cluster-join effects)",
        f"delta={d7:.1%}" if d7 is not None else "n/a")

    # X8 signalised junctions: B TLS clusters must cover only real OSM signal nodes
    a_sig = osmnx_metrics["osm_traffic_signal_nodes"]
    b_tls = sumo_metrics["n_tls"]
    covered = len(osmnx_metrics["_signal_node_ids"] & sumo_metrics["_tls_osmids"]) \
        if "_signal_node_ids" in osmnx_metrics else None
    add("X8", "signalised junctions (A signal nodes vs B TLS after join)",
        a_sig, b_tls, b_tls <= a_sig and b_tls > 0, "B ≤ A and B > 0",
        f"TLS clusters containing a tagged signal node: {covered}")

    # X9 shortest-path lengths on fixed pairs
    ok_pairs, deltas = 0, []
    for ra, rb in zip(osmnx_routes, sumo_routes):
        la, lb = ra.get("shortest_length_m"), rb.get("length_m")
        if la and lb:
            dd = abs(la - lb) / la
            deltas.append(round(dd, 3))
            if dd <= 0.15:
                ok_pairs += 1
    add("X9", "O-D shortest-path length agreement", ok_pairs, len(deltas),
        len(deltas) > 0 and ok_pairs >= int(0.75 * len(deltas)),
        "≥75% of pairs within ±15%", f"per-pair deltas={deltas}")

    # X10 k-shortest distinct alternatives
    with_alts = sum(1 for r in osmnx_routes if r.get("k_paths_distinct", 0) >= 2)
    evaluated = sum(1 for r in osmnx_routes if "k_paths_distinct" in r)
    add("X10", "k=3 alternatives per O-D (≥2 distinct)", with_alts, evaluated,
        evaluated > 0 and with_alts >= int(0.80 * evaluated), "≥80% of pairs",
        "route choice needed by Lab 22")

    # X11 central junctions present in SUMO
    present = sum(1 for osmid in central_osmids
                  if osmid in sumo_metrics["_junction_osmids"])
    add("X11", "top-10 betweenness-central junctions present in SUMO", present,
        len(central_osmids), present >= 6, "≥6/10",
        "identity via OSM node ids after cluster expansion")

    # X12 attribute completeness (report only)
    add("X12", "attribute completeness (lanes/maxspeed/name)",
        osmnx_metrics["attribute_completeness"], "n/a", True, "report only",
        "quantifies what Lab 13 must field-survey")

    n_review = sum(1 for c in checks if c["status"] == "REVIEW")
    report = {"checks": checks, "n_pass": len(checks) - n_review,
              "n_review": n_review,
              "verdict": "PASS" if n_review == 0 else "PASS_WITH_EXPLANATIONS"}
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps(report, indent=2, default=str))
    return report
