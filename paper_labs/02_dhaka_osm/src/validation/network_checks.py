"""Network validation: censuses, strong connectivity (Kosaraju), TLS safety checks.

Pure sumolib + stdlib; the SCC is computed over the directed edge graph induced
by the net's connections (edge -> outgoing edges), iteratively (no recursion
limits).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def _edge_graph(net):
    """edge id -> set of successor edge ids (via connections)."""
    fwd = defaultdict(set)
    edges = [e for e in net.getEdges()]
    for e in edges:
        for succ in e.getOutgoing().keys():
            fwd[e.getID()].add(succ.getID())
        fwd[e.getID()]  # ensure key exists
    return fwd


def _kosaraju_largest_scc(fwd: dict) -> set:
    rev = defaultdict(set)
    for u, vs in fwd.items():
        rev[u]
        for v in vs:
            rev[v].add(u)
    visited, order = set(), []
    for start in fwd:
        if start in visited:
            continue
        stack = [(start, iter(fwd[start]))]
        visited.add(start)
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append((nxt, iter(fwd.get(nxt, ()))))
                    advanced = True
                    break
            if not advanced:
                order.append(node)
                stack.pop()
    seen, best = set(), set()
    for start in reversed(order):
        if start in seen:
            continue
        comp, stack = set(), [start]
        seen.add(start)
        while stack:
            u = stack.pop()
            comp.add(u)
            for v in rev.get(u, ()):
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        if len(comp) > len(best):
            best = comp
    return best


def tls_program_checks(net) -> list[dict]:
    """Static safety screen of every TLS program in the net."""
    results = []
    for tls in net.getTrafficLights():
        progs = tls.getPrograms()
        for pid, prog in progs.items():
            phases = prog.getPhases()
            states = [p.state for p in phases]
            n_green = sum(1 for s in states
                          if ("G" in s or "g" in s) and "y" not in s.lower())
            has_yellow = any("y" in s.lower() for s in states)
            all_green = any(set(s) <= {"G", "g"} and len(s) > 0 for s in states)
            results.append({
                "tls_id": tls.getID(), "program": pid, "n_phases": len(phases),
                "n_green_phases": n_green, "has_yellow_phase": has_yellow,
                "has_all_green_phase": bool(all_green),
                "states": states[:12],
            })
    return results


def validate_network(net_file: Path, out_dir: Path) -> dict:
    import sumolib
    net = sumolib.net.readNet(str(net_file), withPrograms=True)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    edges = net.getEdges()
    nodes = net.getNodes()
    lane_counts = Counter(e.getLaneNumber() for e in edges)
    type_census = Counter((e.getType() or "unknown") for e in edges)
    junction_types = Counter(n.getType() for n in nodes)
    dead_ends = [n.getID() for n in nodes if n.getType() == "dead_end"]
    speeds = Counter(round(e.getSpeed(), 1) for e in edges)

    fwd = _edge_graph(net)
    scc = _kosaraju_largest_scc(fwd)
    scc_fraction = len(scc) / max(len(fwd), 1)

    tls_checks = tls_program_checks(net)
    tls_ids = sorted({t["tls_id"] for t in tls_checks})

    report = {
        "n_edges": len(edges),
        "n_lanes_total": sum(e.getLaneNumber() for e in edges),
        "n_junctions": len(nodes),
        "junction_types": dict(junction_types),
        "n_dead_ends": len(dead_ends),
        "dead_end_sample": dead_ends[:20],
        "lane_count_distribution": {str(k): v for k, v in sorted(lane_counts.items())},
        "edge_type_census": dict(type_census.most_common(20)),
        "speed_distribution_mps": {str(k): v for k, v in sorted(speeds.items())},
        "largest_scc_edges": len(scc),
        "scc_edge_fraction": round(scc_fraction, 4),
        "n_tls": len(tls_ids),
        "tls_ids_sample": tls_ids[:15],
        "tls_all_have_yellow": all(t["has_yellow_phase"] for t in tls_checks) if tls_checks else None,
        "tls_any_all_green": any(t["has_all_green_phase"] for t in tls_checks) if tls_checks else None,
        "projection": net.getLocationOffset() is not None,
    }
    (out_dir / "network_validation.json").write_text(json.dumps(report, indent=2))
    (out_dir / "tls_programs.json").write_text(json.dumps(tls_checks, indent=2))
    return report


def representative_routes(net_file: Path, out_dir: Path, n_axis_pairs: int = 4) -> dict:
    """Deterministic boundary/center O-D pairs, routed in both directions."""
    import sumolib
    net = sumolib.net.readNet(str(net_file))
    edges = [e for e in net.getEdges() if e.getLaneNumber() >= 1]

    def center(e):
        (x1, y1), (x2, y2) = e.getFromNode().getCoord(), e.getToNode().getCoord()
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    xmin, ymin, xmax, ymax = net.getBoundary()
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    picks = {
        "south": min(edges, key=lambda e: center(e)[1]),
        "north": max(edges, key=lambda e: center(e)[1]),
        "west": min(edges, key=lambda e: center(e)[0]),
        "east": max(edges, key=lambda e: center(e)[0]),
        "center": min(edges, key=lambda e: (center(e)[0] - cx) ** 2 + (center(e)[1] - cy) ** 2),
    }
    pairs = [("south", "north"), ("north", "south"), ("west", "east"),
             ("east", "west"), ("center", "north"), ("north", "center"),
             ("center", "east"), ("east", "center")]
    results = []
    for a, b in pairs:
        ea, eb = picks[a], picks[b]
        path, cost = net.getShortestPath(ea, eb)
        results.append({
            "from_role": a, "to_role": b,
            "from_edge": ea.getID(), "to_edge": eb.getID(),
            "routable": path is not None,
            "n_edges": len(path) if path else 0,
            "cost_s": round(cost, 1) if path else None,
        })
    ok = sum(1 for r in results if r["routable"])
    report = {"pairs": results, "n_ok": ok, "n_total": len(results)}
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "representative_routes.json").write_text(json.dumps(report, indent=2))
    return report
