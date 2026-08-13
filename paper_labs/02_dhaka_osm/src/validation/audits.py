"""Lane-direction, traffic-light and turn-connection audits of the built network.

These answer the Lab 02 questions that a bare edge count cannot: are lane counts
plausible, is one-way direction preserved, do signalized junctions carry usable
programs, and can vehicles actually turn where the geometry says they should?

Timing provenance is explicit: netconvert SYNTHESISES signal programs for OSM
junctions (the OSM node only says "there is a signal here"). Those timings are
therefore labelled IMPORTED_HEURISTIC and must never be presented as Dhaka's
real signal plans.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

#: netconvert-synthesised programs — heuristic, NOT observed Dhaka timings.
TLS_TIMING_PROVENANCE = "IMPORTED_HEURISTIC"
TLS_TIMING_NOTE = (
    "Signal programs were synthesised by netconvert from OSM "
    "`highway=traffic_signals` nodes, which carry position only — no phase or "
    "timing data. Values are heuristic defaults, NOT observed Dhaka signal "
    "plans, and must be replaced with field/DMP timings before any calibrated "
    "control claim (Lab 13+)."
)


def audit_lanes_and_direction(net_file: Path, out_dir: Path) -> dict:
    """Lane counts, speeds, one-way share and direction consistency."""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    edges = net.getEdges()

    lane_hist = Counter(e.getLaneNumber() for e in edges)
    speed_hist = Counter(round(e.getSpeed() * 3.6) for e in edges)   # km/h buckets
    type_hist = Counter((e.getType() or "unknown") for e in edges)

    # one-way detection: an edge whose reverse direction is absent
    node_pairs = {(e.getFromNode().getID(), e.getToNode().getID()) for e in edges}
    oneway, twoway = 0, 0
    for e in edges:
        rev = (e.getToNode().getID(), e.getFromNode().getID())
        if rev in node_pairs:
            twoway += 1
        else:
            oneway += 1

    # lane-count plausibility per road class (implausible = 0 lanes, or >6 on a
    # residential road) — surfaces defaulted/garbage tags rather than hiding them
    implausible = []
    for e in edges:
        n = e.getLaneNumber()
        t = (e.getType() or "")
        if n <= 0 or (n > 6 and "residential" in t) or n > 10:
            implausible.append({"edge": e.getID(), "type": t, "lanes": n})

    total_length_m = sum(e.getLength() for e in edges)
    lane_length_m = sum(e.getLength() * e.getLaneNumber() for e in edges)

    report = {
        "n_edges": len(edges),
        "n_lanes_total": sum(e.getLaneNumber() for e in edges),
        "edge_length_km": round(total_length_m / 1000.0, 2),
        "lane_km": round(lane_length_m / 1000.0, 2),
        "lane_count_distribution": {str(k): v for k, v in sorted(lane_hist.items())},
        "speed_kmh_distribution": {str(k): v for k, v in sorted(speed_hist.items())},
        "edge_type_census": dict(type_hist.most_common(25)),
        "oneway_edges": oneway,
        "twoway_edge_halves": twoway,
        "oneway_fraction": round(oneway / len(edges), 4) if edges else None,
        "implausible_lane_counts": implausible[:25],
        "n_implausible_lane_counts": len(implausible),
        "note": ("lane counts come from OSM `lanes` tags where present, otherwise "
                 "from the netconvert typemap default for the road class; the "
                 "distribution above shows exactly what the network contains."),
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "lane_direction_audit.json").write_text(json.dumps(report, indent=2))
    return report


def _conflicting_green_map(net_file: Path) -> dict:
    """Map each TLS to the pairs of tls-link indices that are mutual foes.

    Uses SUMO's own right-of-way data rather than a guess: every junction stores
    <request index=… foes="bitstring">, where character (len-1-j) of `foes` is 1
    when internal link j conflicts with link `index`. Connections carry both the
    TLS link index (`linkIndex`) and the internal lane (`via`, of the form
    `:junction_<requestIndex>_<lane>`), which lets us translate foes into TLS
    state-string positions.

    An "all-green" phase is only a defect when two *conflicting* links are green
    at the same time. A signal controlling a single approach or a pedestrian
    crossing legitimately shows green on all of its links simultaneously.
    """
    root = ET.parse(net_file).getroot()

    foes_by_junction: dict[str, list[str]] = {}
    for junction in root.findall("junction"):
        jid = junction.get("id")
        foes_by_junction[jid] = [r.get("foes", "") for r in junction.findall("request")]

    # tls -> {tls_link_index -> (junction_id, request_index)}
    link_map: dict[str, dict[int, tuple[str, int]]] = {}
    for conn in root.findall("connection"):
        tl = conn.get("tl")
        via = conn.get("via")
        if not tl or not via or conn.get("linkIndex") is None:
            continue
        # via looks like ":<junctionId>_<requestIndex>_<laneIndex>"
        body = via[1:] if via.startswith(":") else via
        try:
            jid, req_idx = body.rsplit("_", 2)[0], int(body.rsplit("_", 2)[1])
        except (ValueError, IndexError):
            continue
        link_map.setdefault(tl, {})[int(conn.get("linkIndex"))] = (jid, req_idx)

    conflicts: dict[str, set[tuple[int, int]]] = {}
    for tl, links in link_map.items():
        pairs: set[tuple[int, int]] = set()
        for k1, (j1, r1) in links.items():
            foes_rows = foes_by_junction.get(j1, [])
            if r1 >= len(foes_rows):
                continue
            row = foes_rows[r1]
            for k2, (j2, r2) in links.items():
                if k2 <= k1 or j2 != j1:
                    continue
                pos = len(row) - 1 - r2          # SUMO bitstrings read right-to-left
                if 0 <= pos < len(row) and row[pos] == "1":
                    pairs.add((k1, k2))
        conflicts[tl] = pairs
    return conflicts


def audit_traffic_lights(net_file: Path, out_dir: Path, sample_size: int = 8) -> dict:
    """TLS census + real conflicting-green safety screen + named manual sample."""
    import sumolib

    net = sumolib.net.readNet(str(net_file), withPrograms=True)
    tls_list = net.getTrafficLights()
    conflict_map = _conflicting_green_map(Path(net_file))

    programs, unsafe = [], []
    for tls in tls_list:
        for pid, prog in tls.getPrograms().items():
            phases = prog.getPhases()
            states = [p.state for p in phases]
            greens = [s for s in states if ("G" in s or "g" in s) and "y" not in s.lower()]
            yellows = [s for s in states if "y" in s.lower()]
            all_green = [s for s in states if s and set(s) <= {"G", "g"}]
            # real safety test: are two CONFLICTING links ever green together?
            foe_pairs = conflict_map.get(tls.getID(), set())
            violations = []
            for pi, state in enumerate(states):
                green_idx = {i for i, ch in enumerate(state) if ch in ("G", "g")}
                for (a, b) in foe_pairs:
                    if a in green_idx and b in green_idx:
                        violations.append({"phase": pi, "state": state, "links": [a, b]})
            entry = {
                "tls_id": tls.getID(),
                "program": pid,
                "n_phases": len(phases),
                "n_green_phases": len(greens),
                "has_yellow_phase": bool(yellows),
                "has_all_green_state": bool(all_green),
                "n_conflicting_link_pairs": len(foe_pairs),
                "conflicting_green_violations": violations[:5],
                "n_conflicting_green_violations": len(violations),
                "cycle_time_s": sum(p.duration for p in phases),
                "phase_durations_s": [p.duration for p in phases],
                "n_controlled_links": len(states[0]) if states else 0,
            }
            programs.append(entry)
            # unsafe = conflicting greens, or a signal with conflicts but no yellow
            if violations or (foe_pairs and not yellows):
                unsafe.append(entry)

    # name the sampled junctions from OSM street names where available
    sample = []
    for tls in tls_list[:sample_size]:
        node = net.getNode(tls.getID()) if net.hasNode(tls.getID()) else None
        names = set()
        if node is not None:
            for e in list(node.getIncoming()) + list(node.getOutgoing()):
                nm = e.getName() if hasattr(e, "getName") else ""
                if nm:
                    names.add(nm)
        progs = [p for p in programs if p["tls_id"] == tls.getID()]
        sample.append({
            "tls_id": tls.getID(),
            "street_names": sorted(names)[:6],
            "n_incoming_edges": len(node.getIncoming()) if node else None,
            "programs": progs,
        })

    with_conflicts = [p for p in programs if p["n_conflicting_link_pairs"] > 0]
    report = {
        "n_tls": len(tls_list),
        "n_programs": len(programs),
        "n_programs_with_conflicting_movements": len(with_conflicts),
        "all_conflicted_programs_have_yellow": (
            all(p["has_yellow_phase"] for p in with_conflicts) if with_conflicts else None),
        "total_conflicting_green_violations": sum(
            p["n_conflicting_green_violations"] for p in programs),
        "n_all_green_states_without_conflicts": sum(
            1 for p in programs if p["has_all_green_state"]
            and p["n_conflicting_link_pairs"] == 0),
        "all_green_note": ("an all-green state is legitimate where the signal's links "
                           "do not conflict (single approach / pedestrian crossing); "
                           "only conflicting greens are a safety defect"),
        "n_unsafe_programs": len(unsafe),
        "unsafe_programs": unsafe[:10],
        "timing_provenance": TLS_TIMING_PROVENANCE,
        "timing_note": TLS_TIMING_NOTE,
        "manual_sample": sample,
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "traffic_light_audit.json").write_text(json.dumps(report, indent=2))
    return report


def audit_turn_connections(net_file: Path, out_dir: Path) -> dict:
    """Do junctions offer the turning movements their geometry implies?"""
    import sumolib

    net = sumolib.net.readNet(str(net_file))
    dir_hist: Counter = Counter()
    no_outgoing, missing_turns = [], []

    for node in net.getNodes():
        incoming = node.getIncoming()
        outgoing = node.getOutgoing()
        for e in incoming:
            conns = e.getOutgoing()          # {to_edge: [connections]}
            if not conns and outgoing:
                # incoming edge with no permitted movement at a junction that has exits
                if node.getType() != "dead_end":
                    no_outgoing.append({"edge": e.getID(), "junction": node.getID(),
                                        "junction_type": node.getType(),
                                        "n_junction_exits": len(outgoing)})
            for to_edge, connlist in conns.items():
                for c in connlist:
                    d = c.getDirection() if hasattr(c, "getDirection") else "?"
                    dir_hist[d] += 1
        # a 4-arm junction should offer at least 3 distinct exits per approach
        if len(incoming) >= 3 and len(outgoing) >= 3 and node.getType() != "dead_end":
            for e in incoming:
                exits = len(e.getOutgoing())
                if exits <= 1:
                    missing_turns.append({"junction": node.getID(), "approach": e.getID(),
                                          "exits_offered": exits,
                                          "junction_exits": len(outgoing)})

    report = {
        "connection_direction_census": dict(dir_hist),
        "direction_legend": {"s": "straight", "l": "left", "r": "right",
                             "L": "partially left", "R": "partially right",
                             "t": "turnaround", "i": "internal"},
        "n_incoming_edges_without_movements": len(no_outgoing),
        "incoming_without_movements_sample": no_outgoing[:20],
        "n_approaches_with_single_exit_at_multiarm_junctions": len(missing_turns),
        "single_exit_sample": missing_turns[:20],
    }
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "turn_connection_audit.json").write_text(json.dumps(report, indent=2))
    return report
