#!/usr/bin/env python3
"""Render every Lab 02 v2 figure from the machine-readable audit artifacts.

DESIGN_V2 §7 artifact plan. `live_external_reference.png` is produced ONLY if
the live reference was executed (it was not: READY_NOT_EXECUTED, DECISION 1).
`sumo_gui_dhaka.png` is captured separately by scripts/capture_sumo_gui.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "outputs" / "lab02_v2"
FIG = OUT / "figures"
CAND = ROOT / "outputs" / "lab02_candidates"

from src.regions import CANDIDATES  # noqa: E402
from src.visualization.plot_net import CLASS_STYLE, DEFAULT_STYLE, plot_network  # noqa: E402

NET = OUT / "network" / "dhaka_r1.net.xml"
made: list[str] = []


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / name
    fig.tight_layout()
    fig.savefig(p, dpi=160)
    plt.close(fig)
    made.append(str(p))
    print("  wrote", p.name)


def fig_selected_region():
    rows = json.load(open(CAND / "decision_table.json"))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 6),
                                  gridspec_kw={"width_ratios": [1.1, 1]})
    for rid, spec in CANDIDATES.items():
        b = spec["bbox"]
        sel = rid == "R1"
        ax.add_patch(plt.Rectangle((b["west"], b["south"]), b["east"] - b["west"],
                                   b["north"] - b["south"],
                                   fill=sel, alpha=0.35 if sel else 1.0,
                                   facecolor="#2a9d8f" if sel else "none",
                                   edgecolor="#2a9d8f" if sel else "#888",
                                   lw=2.5 if sel else 1.2))
        ax.annotate(rid, ((b["west"] + b["east"]) / 2, (b["south"] + b["north"]) / 2),
                    ha="center", fontsize=11, fontweight="bold" if sel else "normal",
                    color="#1b6ca8" if sel else "#555")
    ax.set(xlim=(90.36, 90.44), ylim=(23.70, 23.84),
           title="Candidate regions (KEEP: R1, measured selection)",
           xlabel="longitude", ylabel="latitude")
    scores = {"R1": 22, "R2": 12, "R3": 15, "R4": 17, "R5": 16}   # REGION_SELECTION.md
    tls = {r["region"]: r["C1_n_tls"] for r in rows}
    ids = list(scores)
    bars = ax2.bar(ids, [scores[i] for i in ids],
                   color=["#2a9d8f" if i == "R1" else "#bbb" for i in ids])
    for i, b in zip(ids, bars):
        ax2.annotate(f"{tls[i]} TLS", (b.get_x() + b.get_width() / 2, b.get_height()),
                     ha="center", va="bottom", fontsize=9)
    ax2.set(title="Pre-registered C1–C8 total score (max 24)", ylabel="score")
    save(fig, "selected_dhaka_region.png")


def fig_raw_osm_graph():
    from src.analysis.osmnx_graph import build_graph
    import osmnx as ox
    G = build_graph(CAND / "R1" / "R1.osm", keep_largest_wcc=False)
    fig, ax = plt.subplots(figsize=(10, 11))
    ox.plot_graph(G, ax=ax, node_size=1.5, node_color="#1b6ca8",
                  edge_color="#999", edge_linewidth=0.4, show=False, close=False)
    ax.set_title(f"Branch A — OSMnx 2.1.1 graph from frozen snapshot "
                 f"({G.number_of_nodes()} nodes, {G.number_of_edges()} edges)")
    save(fig, "raw_osm_graph.png")


def fig_sumo_network():
    figs = plot_network(NET, FIG / "sumo_network.png",
                        title="Branch B — SUMO --lefthand network (R1)")
    made.extend(figs)
    print("  wrote sumo_network.png (+ zooms)")


def fig_topology_compare():
    am = json.load(open(OUT / "analysis" / "osmnx_metrics.json"))
    xv = json.load(open(OUT / "analysis" / "cross_validation.json"))
    x1 = next(c for c in xv["checks"] if c["id"] == "X1")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    axes[0].bar(["OSMnx", "SUMO"], [x1["osmnx"], x1["sumo"]], color=["#1b6ca8", "#d95f02"])
    axes[0].set_title("X1 total drive length (km)\n(gap = junction-interior lanes; explained)")
    x5 = next(c for c in xv["checks"] if c["id"] == "X5")
    axes[1].bar(["OSMnx", "SUMO"], [x5["osmnx"], x5["sumo"]], color=["#1b6ca8", "#d95f02"])
    axes[1].axhline(0.90, ls="--", color="k", lw=1)
    axes[1].set_title("X5 largest-SCC edge fraction\n(bar = 0.90 health floor)")
    axes[1].set_ylim(0, 1.05)
    statuses = [c["status"] for c in xv["checks"]]
    axes[2].bar(["PASS", "REVIEW\n(explained)"],
                [statuses.count("PASS"), statuses.count("REVIEW")],
                color=["#2a9d8f", "#e9c46a"])
    axes[2].set_title(f"X1–X12 cross-validation → {xv['verdict']}")
    save(fig, "osmnx_vs_sumo_topology.png")


def fig_components():
    am = json.load(open(OUT / "analysis" / "osmnx_metrics.json"))
    val = json.load(open(OUT / "validation" / "network_validation.json"))
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["OSMnx raw WCCs", "OSMnx SCCs", "SUMO largest-SCC\nedge fraction",
              "OSMnx largest-SCC\nedge fraction"]
    prune = am.get("component_prune") or {}
    vals = [prune.get("n_components_raw", am["n_wcc"]), am["n_scc"],
            val["scc_edge_fraction"], am["largest_scc_edge_fraction"]]
    ax.bar(labels[:2], vals[:2], color="#1b6ca8")
    ax2 = ax.twinx()
    ax2.bar(labels[2:], vals[2:], color="#d95f02")
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.90, ls="--", color="k", lw=1)
    ax.set_title("Connected components (counts left, edge fractions right)")
    save(fig, "connected_components.png")


def fig_hierarchy():
    am = json.load(open(OUT / "analysis" / "osmnx_metrics.json"))
    import sumolib  # noqa
    from src.analysis.cross_validate import sumo_vehicular_metrics
    bm = sumo_vehicular_metrics(NET)
    classes = sorted(set(am["hierarchy_length_share"]) | set(bm["hierarchy_length_share"]),
                     key=lambda c: -am["hierarchy_length_share"].get(c, 0))
    xs = range(len(classes))
    fig, ax = plt.subplots(figsize=(11, 5))
    w = 0.4
    ax.bar([x - w / 2 for x in xs],
           [am["hierarchy_length_share"].get(c, 0) for c in classes], w, label="OSMnx", color="#1b6ca8")
    ax.bar([x + w / 2 for x in xs],
           [bm["hierarchy_length_share"].get(c, 0) for c in classes], w, label="SUMO", color="#d95f02")
    ax.set_xticks(list(xs), classes, rotation=40, ha="right")
    ax.set(title="X3 road-hierarchy length shares (both branches)", ylabel="share of length")
    ax.legend()
    save(fig, "road_hierarchy.png")


def fig_lane_completeness():
    am = json.load(open(OUT / "analysis" / "osmnx_metrics.json"))
    la = json.load(open(OUT / "validation" / "lane_direction_audit.json"))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    comp = am["attribute_completeness"]
    ax.bar(list(comp), [v * 100 for v in comp.values()], color="#1b6ca8")
    ax.set(title="X12 OSM attribute completeness (R1)", ylabel="% of edges tagged")
    for i, v in enumerate(comp.values()):
        ax.annotate(f"{v*100:.1f}%", (i, v * 100), ha="center", va="bottom")
    dist = la["lane_count_distribution"]
    ax2.bar(list(dist), list(dist.values()), color="#d95f02")
    ax2.set(title="SUMO lane-count distribution (typemap defaults fill untagged)",
            xlabel="lanes per edge", ylabel="edges")
    save(fig, "lane_completeness.png")


def fig_tls_audit():
    ta = json.load(open(OUT / "validation" / "traffic_light_audit.json"))
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    ax.bar(["TLS", "programs", "with conflicting\nmovements", "G/G safety\nviolations"],
           [ta["n_tls"], ta["n_programs"],
            ta["n_programs_with_conflicting_movements"],
            ta["total_conflicting_green_violations"]],
           color=["#1b6ca8", "#1b6ca8", "#e9c46a", "#c1121f"])
    ax.set_title(f"Signal audit — timing provenance: {ta['timing_provenance']}")
    ax2.bar(["permissive G/g conflicts\n(yield inside junction — legal)",
             "all-green states\n(non-conflicting links)"],
            [ta.get("total_permissive_green_conflicts", 0),
             ta["n_all_green_states_without_conflicts"]], color="#2a9d8f")
    ax2.set_title("Legitimate cases censused separately")
    save(fig, "tls_audit.png")


def fig_turns():
    tc = json.load(open(OUT / "validation" / "turn_connection_audit.json"))
    cen = tc["connection_direction_census"]
    leg = tc["direction_legend"]
    keys = sorted(cen, key=lambda k: -cen[k])
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar([leg.get(k, k) for k in keys], [cen[k] for k in keys], color="#1b6ca8")
    ax.set_title(f"Turn-connection census — vehicular approaches without movements: "
                 f"{tc['n_incoming_edges_without_movements']} "
                 f"(non-vehicular excluded: {tc['n_nonvehicular_approaches_excluded']})")
    ax.set_ylabel("connections")
    save(fig, "turn_connection_audit.png")


def _plot_edges_bg(ax, net):
    for e in net.getEdges():
        color, lw = CLASS_STYLE.get(e.getType(), DEFAULT_STYLE)
        xs, ys = zip(*e.getShape())
        ax.plot(xs, ys, color=color, lw=lw * 0.7, alpha=0.5, zorder=1)


def fig_representative_routes():
    import sumolib
    rep = json.load(open(OUT / "validation" / "representative_routes.json"))
    net = sumolib.net.readNet(str(NET))
    fig, ax = plt.subplots(figsize=(10, 11))
    _plot_edges_bg(ax, net)
    colors = plt.cm.tab10.colors
    for i, r in enumerate(rep["pairs"]):
        if not r.get("routable"):
            continue
        # deterministically re-derive the recorded route from its endpoints
        path, _ = net.getShortestPath(net.getEdge(r["from_edge"]),
                                      net.getEdge(r["to_edge"]))
        for e in path or []:
            xs, ys = zip(*e.getShape())
            ax.plot(xs, ys, color=colors[i % 10], lw=2.2, zorder=2)
    ax.set_title(f"Representative O-D routes on the SCC core "
                 f"({rep['n_ok']}/{rep['n_total']} routable, both directions)")
    ax.set_aspect("equal")
    save(fig, "representative_routes.png")


def fig_k_shortest():
    ar = json.load(open(OUT / "analysis" / "osmnx_routes.json"))
    rows = ar["routes"]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    idx = [f"OD{i}" for i in range(len(rows))]
    found = [r.get("k_paths_found", 0) for r in rows]
    distinct = [r.get("k_paths_distinct", 0) for r in rows]
    w = 0.4
    ax.bar([i - w / 2 for i in range(len(rows))], found, w, label="k paths found", color="#1b6ca8")
    ax.bar([i + w / 2 for i in range(len(rows))], distinct, w, label="distinct", color="#2a9d8f")
    ax.axhline(2, ls="--", color="k", lw=1)
    ax.set_xticks(range(len(rows)), idx)
    ax.set(title="X10 k=3 shortest-path alternatives per fixed O-D pair",
           ylabel="paths")
    ax.legend()
    save(fig, "k_shortest_routes.png")


def fig_reachability():
    import sumolib
    rep = json.load(open(OUT / "validation" / "representative_routes.json"))
    roles = ["south", "north", "west", "east", "center"]
    net = sumolib.net.readNet(str(NET))
    # build matrix from picked role edges
    picks = {r["from_role"]: r["from_edge"] for r in rep["pairs"]}
    picks.update({r["to_role"]: r["to_edge"] for r in rep["pairs"]})
    import numpy as np
    M = np.full((5, 5), np.nan)
    for i, a in enumerate(roles):
        for j, b in enumerate(roles):
            if a == b or a not in picks or b not in picks:
                continue
            path, _ = net.getShortestPath(net.getEdge(picks[a]), net.getEdge(picks[b]))
            M[i, j] = 1.0 if path else 0.0
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(M, cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(5), roles)
    ax.set_yticks(range(5), roles)
    ok = int(np.nansum(M))
    tot = int(np.sum(~np.isnan(M)))
    ax.set_title(f"O-D reachability matrix (role edges): {ok}/{tot} routable")
    for i in range(5):
        for j in range(5):
            if not np.isnan(M[i, j]):
                ax.annotate("✓" if M[i, j] else "✗", (j, i), ha="center", va="center")
    save(fig, "route_reachability_matrix.png")


def fig_dashboard():
    g = json.load(open(OUT / "gate_record.json"))
    gates = {k: v for k, v in g.items() if k.isupper() and isinstance(v, str)}
    fig, ax = plt.subplots(figsize=(9, 7))
    ax.axis("off")
    colors = {"PASS": "#2a9d8f", "FAIL": "#c1121f", "REVIEW": "#e9c46a",
              "READY_NOT_EXECUTED": "#888"}
    for i, (k, v) in enumerate(gates.items()):
        y = 1 - i * (1 / (len(gates) + 1)) - 0.05
        ax.add_patch(mpatches.FancyBboxPatch((0.02, y - 0.03), 0.55, 0.055,
                                             boxstyle="round,pad=0.01",
                                             facecolor="#f2f2f2", edgecolor="none"))
        ax.text(0.04, y, k, fontsize=10, va="center", family="monospace")
        ax.text(0.62, y, v, fontsize=10, va="center", fontweight="bold",
                color=colors.get(v, "#333"))
    ax.set_title(f"Lab 02 v2 validation dashboard — region {g['selected_region']} "
                 f"({g['region_name']})", fontsize=11)
    save(fig, "validation_dashboard.png")


def fig_dhakaflow_connection():
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.axis("off")
    boxes = [
        (0.03, 0.62, "Frozen OSM snapshot\nR1.osm + sha256\n(ODbL, Overpass)", "#f4a26122"),
        (0.03, 0.18, "netconvert --lefthand\ndhaka_r1.net.xml\n+ audits (X1–X12)", "#f4a26122"),
        (0.38, 0.62, "TrafficScenario\n(SYNTHETIC_VALIDATION_DEMAND,\ntraffic_side=left_hand)", "#1b6ca822"),
        (0.38, 0.18, "SumoDhakaBackend\n(SimulationBackend protocol,\nTraCI)", "#1b6ca822"),
        (0.72, 0.62, "LiveTrafficReference\nGoogleRoutesReference\nREADY_NOT_EXECUTED", "#2a9d8f22"),
        (0.72, 0.18, "Labs 13+\ncalibrated twin, control,\nrouting (Lab 22)", "#2a9d8f22"),
    ]
    for x, y, txt, fc in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), 0.25, 0.2,
                                             boxstyle="round,pad=0.02",
                                             facecolor=fc[:7], alpha=0.35,
                                             edgecolor="#333"))
        ax.text(x + 0.125, y + 0.1, txt, ha="center", va="center", fontsize=9)
    for (x1, y1), (x2, y2) in [((0.28, 0.72), (0.38, 0.72)), ((0.28, 0.28), (0.38, 0.28)),
                               ((0.155, 0.62), (0.155, 0.38)), ((0.63, 0.72), (0.72, 0.72)),
                               ((0.63, 0.28), (0.72, 0.28)), ((0.845, 0.62), (0.845, 0.38))]:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#333"))
    ax.set_title("Lab 02 products wired into the dhakaflow platform (Sprint A interfaces)")
    save(fig, "dhakaflow_connection.png")


if __name__ == "__main__":
    for fn in (fig_selected_region, fig_raw_osm_graph, fig_sumo_network,
               fig_topology_compare, fig_components, fig_hierarchy,
               fig_lane_completeness, fig_tls_audit, fig_turns,
               fig_representative_routes, fig_k_shortest, fig_reachability,
               fig_dashboard, fig_dhakaflow_connection):
        print("[figures]", fn.__name__)
        fn()
    (FIG / "figure_manifest.json").write_text(json.dumps(made, indent=2))
    print(f"[figures] {len(made)} files")
