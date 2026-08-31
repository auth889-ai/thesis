#!/usr/bin/env python3
"""Step 1b — per-cycle calibration tree for the d8 junction (authors' format).

A-window ONLY. For each trajectory-inferred cycle: vehicles near the junction
at cycle start become SUMO initial states (real pos/speed/lane), real exit
times become Data/Info_Cycle_N.csv, detectors mirror the authors' d1..d4
layout, TLS = trajectory-inferred two-phase program. Output tree is then run
by the authors' optimizer UNMODIFIED.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SP = Path("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad/urban")
W = SP / "d8_calib"
J = "6694885345"
A1 = 372.5
R_INIT = 420.0          # m: full feeding vicinity (one cycle of travel)
VTYPE = {"Car": "Car", "Taxi": "Taxi", "Motorcycle": "Motorcycle",
         "Bus": "Bus", "Medium Vehicle": "Medium", "Heavy Vehicle": "Heavy"}


def main() -> None:
    import sumolib
    from research.urban.pneuma_provider import parse
    from scripts.gate_urban_site import build_map, load_osm
    from leuvenmapmatching.matcher.distance import DistanceMatcher

    net = sumolib.net.readNet(str(SP / "athens_d8.net.xml"))
    node = net.getNode(J)
    jx, jy = node.getCoord()
    inc = [e for e in node.getIncoming() if e.getFunction() == ""]
    out = [e for e in node.getOutgoing() if e.getFunction() == ""]
    print("incoming:", [(e.getID(), e.getLaneNumber()) for e in inc])
    print("outgoing:", [(e.getID(), e.getLaneNumber()) for e in out])

    # ---- cycles from the inference file (long-window starts) -------------
    inf = json.loads((REPO / "artifacts/urban_real_site/d8_cycle_inference.json"
                      ).read_text())
    cand = next(c for c in inf["candidates"] if c["junction"] == J)
    wins = cand["green_windows"]
    durs = [b - a for a, b in wins]
    long_starts = [a for (a, b), d in zip(wins, durs) if d >= max(durs) * 0.5]
    cycles = [(s0, s1) for s0, s1 in zip(long_starts, long_starts[1:])
              if s1 - s0 > 40 and s1 <= A1]
    print("cycles:", cycles)
    # phase break within each cycle = start of the following short window
    def phase_break(c0, c1):
        shorts = [a for (a, b), d in zip(wins, durs)
                  if d < max(durs) * 0.5 and c0 < a < c1]
        return shorts[0] if shorts else c0 + 0.66 * (c1 - c0)

    # ---- match A vehicles once (1 Hz positions + node-pair states) -------
    tracks = list(parse(str(SP / "d8.csv"), hz=1.0))
    nodes_osm, ways, signals, _ = load_osm()
    mmap = build_map(nodes_osm, ways)
    vehs = {}
    for tr in tracks:
        pts = [(s.t, s.lat, s.lon, s.speed_kmh) for s in tr.samples
               if s.t <= A1]
        if len(pts) < 10 or len(vehs) >= 550:
            continue
        m = DistanceMatcher(mmap, max_dist=45, max_dist_init=60, obs_noise=8,
                            obs_noise_ne=25, min_prob_norm=0.001,
                            non_emitting_states=True)
        try:
            st, _ = m.match([(p[1], p[2]) for p in pts])
        except Exception:
            continue
        if not st or len(st) < 0.5 * len(pts):
            continue
        vehs[tr.vid] = {"type": tr.vtype,
                        "rows": [(p[0], p[1], p[2], p[3], s)
                                 for p, s in zip(pts, st)]}
    print("A vehicles matched:", len(vehs))

    # exit events INTO outgoing edges of J (real exit times + direction)
    out_start = {e.getID(): e for e in out}
    # direction buckets: d3 = outgoing with most traffic, d4 = rest
    exit_counts = defaultdict(int)
    veh_exits = {}
    for vid, d in vehs.items():
        prev = None
        for (t, la, lo, kmh, (a, b)) in d["rows"]:
            pair = (a, b)
            if prev is not None and pair != prev and a == J:
                # crossed junction into edge starting at J toward node b:
                for eid, e in out_start.items():
                    if e.getToNode().getID() == b or \
                       any(n == b for n in [e.getToNode().getID()]):
                        veh_exits[vid] = (t, eid)
                        exit_counts[eid] += 1
                        break
                else:
                    veh_exits.setdefault(vid, (t, None))
            prev = pair
    ranked_out = sorted(exit_counts.items(), key=lambda kv: -kv[1])
    print("exit edge volumes:", ranked_out)
    d3_edge = ranked_out[0][0]
    d4_edges = [e for e, _ in ranked_out[1:3]]

    # main incoming edge = feeds d3 most
    main_in = max(inc, key=lambda e: e.getLaneNumber()).getID()

    # feeding corridor: walk upstream from the approach (~450 m)
    corridor = [main_in]
    cur = net.getEdge(main_in)
    dist = cur.getLength()
    while dist < 450.0:
        preds = [e for e in cur.getFromNode().getIncoming()
                 if e.getFunction() == ""]
        if not preds:
            break
        cur = max(preds, key=lambda e: e.getLaneNumber())
        if cur.getID() in corridor:
            break
        corridor.append(cur.getID())
        dist += cur.getLength()
    corridor_set = set(corridor) | {e.getID() for e in out}
    # ordered driving chain: upstream-most -> ... -> approach -> exit (+1)
    chain = list(reversed(corridor)) + [d3_edge]
    nxt_after = [e.getID() for e in net.getEdge(d3_edge).getOutgoing()][:1]
    chain += nxt_after
    print("corridor chain:", chain)

    # ---- write the tree ---------------------------------------------------
    import shutil
    import xml.sax.saxutils as sx
    if W.exists():
        shutil.rmtree(W)
    W.mkdir(parents=True)
    shutil.copy(SP / "athens_d8.net.xml", W / "osm.net.xml")
    shutil.copy(Path.home() / ".dhakaflow/upstream/"
                "phase-relative-sumo-calibration/parameters_results_material/"
                "osm.type.xml", W / "osm.type.xml")
    shutil.copy(Path.home() / ".dhakaflow/upstream/"
                "phase-relative-sumo-calibration/calibration_codes/"
                "optimization_process_nevergrad.py", W)
    shutil.copy(SP / "repro/work/InfoProcess.py", W)
    (W / "osm.view.xml").write_text("<viewsettings/>")
    (W / "Data").mkdir()

    # TLS: trajectory-inferred two-phase program at J (per connection)
    tls = None
    for t in net.getTrafficLights():
        for c in t.getConnections():
            if c[0].getEdge().getToNode().getID() == J or \
               c[0].getEdge().getID() in [e.getID() for e in inc]:
                tls = t
                break
        if tls:
            break
    conns = tls.getConnections()
    n = max(c[2] for c in conns) + 1
    cyc_len = round(sum(c1 - c0 for c0, c1 in cycles) / len(cycles))
    p1_len = round(sum(phase_break(c0, c1) - c0 for c0, c1 in cycles)
                   / len(cycles))
    p1 = ["r"] * n
    p2 = ["r"] * n
    for (inl, _o, idx) in conns:
        if inl.getEdge().getID() == main_in:
            p1[idx] = "G"
        else:
            p2[idx] = "G"
    y1 = ["y" if s == "G" else "r" for s in p1]
    y2 = ["y" if s == "G" else "r" for s in p2]
    tls_xml = [f'<additional>',
               f'  <tlLogic id="{tls.getID()}" type="static" '
               f'programID="inferred" offset="0">',
               f'    <phase duration="{max(p1_len-3,5)}" state="{"".join(p1)}"/>',
               f'    <phase duration="3" state="{"".join(y1)}"/>',
               f'    <phase duration="{max(cyc_len-p1_len-3,5)}" state="{"".join(p2)}"/>',
               f'    <phase duration="3" state="{"".join(y2)}"/>',
               '  </tlLogic>', '</additional>']
    (W / "paper_tls.add.xml").write_text("\n".join(tls_xml))

    # detectors add-file (shared): entries on incoming, exits on outgoing
    add = ['<additional '
           'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">']
    def loops(prefix, edge_id, pos_from_end=None, pos=5.0):
        e = net.getEdge(edge_id)
        for li in range(e.getLaneNumber()):
            p = (e.getLength() - pos_from_end) if pos_from_end else pos
            p = max(min(p, e.getLength() - 1), 1)
            add.append(f'  <instantInductionLoop id="{prefix}_{li}" '
                       f'lane="{edge_id}_{li}" pos="{p:.2f}" '
                       f'file="info.xml"/>')
    loops("d1", main_in, pos_from_end=8.0)
    others_in = [e.getID() for e in inc if e.getID() != main_in]
    for k, eid in enumerate(others_in[:1]):
        loops("d2", eid, pos_from_end=8.0)
    loops("d3", d3_edge, pos=6.0)
    for k, eid in enumerate(d4_edges[:1]):
        loops("d4", eid, pos=6.0)
    add.append("</additional>")

    # per-cycle dirs
    tl_rows = ["Start;Break;Continuation;Stop"]
    for ci, (c0, c1) in enumerate(cycles, 1):
        cd = W / f"Info_Cycle_{ci}"
        cd.mkdir()
        (cd / "osm.add.xml").write_text("\n".join(add))
        pb = phase_break(c0, c1)
        tl_rows.append(f"0;{pb-c0:.1f};{pb-c0:.1f};{c1-c0:.1f}")
        # initial vehicles: near J at c0
        vlines = []
        for vid, d in vehs.items():
            # present at cycle start OR first observed mid-cycle (real
            # arrival) — always the vehicle's own real time/state
            t_first = d["rows"][0][0]
            if t_first <= c0 + 1.5:
                near = min(d["rows"], key=lambda r: abs(r[0] - c0))
                if abs(near[0] - c0) > 1.5:
                    continue
                dep = 0.0
            elif t_first < c1 - 2.0:
                near = d["rows"][0]
                dep = t_first - c0
            else:
                continue
            t, la, lo, kmh, (a, b) = near
            x, y = net.convertLonLat2XY(lo, la)
            # matched edge = a->b if exists in net, and ON the corridor
            eid = None
            if net.hasNode(a):
                for cand_e in net.getNode(a).getOutgoing():
                    if cand_e.getToNode().getID() == b:
                        eid = cand_e.getID()
                        break
            if eid is None or eid not in corridor_set:
                continue
            e = net.getEdge(eid)
            lane = e.getLanes()[0]
            lpos, _dist = lane.getClosestLanePosAndDist((x, y))
            # one-way corridor: the physical path IS the corridor chain
            # (measured exits: all through, none diverge)
            if eid not in chain:
                continue
            seq = chain[chain.index(eid):]
            if len(seq) < 2:
                continue
            typ = VTYPE.get(d["type"], "Car")
            vlines.append(
                f'    <vehicle id="{vid}" depart="{dep:.1f}" type="{typ}" '
                f'departLane="best" departSpeed="{kmh/3.6:.2f}" '
                f'departPos="{max(min(lpos, e.getLength()-2), 1):.1f}">\n'
                f'        <route edges="{" ".join(seq)}"/>\n    </vehicle>')
        (cd / "routes.rou.xml").write_text(
            "<routes>\n" + "\n".join(vlines) + "\n</routes>\n")
        # real exits for this cycle
        rows = ["id;class;length;entry_time;exit_time;entry_detector;"
                "exit_detector;entry_speed;exit_speed;d_from_road_start; "]
        for vid, (t, eid) in veh_exits.items():
            if not (c0 <= t < c1) or eid is None:
                continue
            det = "d3_0" if eid == d3_edge else "d4_0"
            rows.append(f"{vid};{VTYPE.get(vehs[vid]['type'],'Car')};5.0;"
                        f"0.0;{t-c0:.1f};d1_0;{det};0.0;0.0;0.0; ")
        (cd / "Data_row_count").write_text(str(len(rows) - 1))
        (W / "Data" / f"Info_Cycle_{ci}.csv").write_text("\n".join(rows) + "\n")
        # sumocfg
        (cd / "osm.sumocfg").write_text(f"""<sumoConfiguration>
    <input>
        <net-file value="../osm.net.xml"/>
        <route-files value="routes.rou.xml"/>
        <additional-files value="osm.add.xml,../osm.type.xml,../paper_tls.add.xml"/>
    </input>
    <time><begin value="0.0"/><end value="{c1-c0:.0f}"/></time>
    <processing>
        <time-to-teleport value="-1"/>
        <eager-insert value="true"/>
        <lateral-resolution value="1.0"/>
        <step-length value="0.1"/>
    </processing>
    <report><no-step-log value="true"/></report>
    <output><tripinfo-output value="tripinfo.xml"/></output>
</sumoConfiguration>
""")
        print(f"cycle {ci}: init vehicles {len(vlines)}, real exits "
              f"{len(rows)-1}, len {c1-c0:.0f}s")
    (W / "Data/TrafficLightCycles.csv").write_text("\n".join(tl_rows) + "\n")
    print("tree at", W)


if __name__ == "__main__":
    main()
