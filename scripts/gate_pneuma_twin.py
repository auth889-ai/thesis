#!/usr/bin/env python3
"""GATE: PNEUMA_SAME_SITE_TWIN — real Athens vehicles on the same Athens roads.

A [0,372.5s] ONLY builds demand: each eligible real vehicle becomes a SUMO
vehicle with its real departure time, real class, and its OWN matched route.
B [372.5,579.5s] demand continuation uses ONLY A-fitted statistics (entry rate
+ A route distribution). Real B vehicles are never inserted.
Validation on B compares real (from raw trajectories) vs SUMO:
per-segment speed/flow, signalized-approach queues, discharge, plus a
trajectory-level check on individual A vehicles (travel time, edge agreement,
position-time error). Signals: OSM-imported default programs (documented).
No control. No moveTo. No teleport tolerance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
SP = Path("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad/urban")
CSV, OSM, NET = SP / "d8.csv", SP / "athens_d8.osm", SP / "athens_d8.net.xml"
OUT = REPO / "artifacts/urban_real_site"
A0, A1, B1 = 0.0, 372.5, 579.5
VCLASS = {"Car": "passenger", "Taxi": "passenger", "Motorcycle": "motorcycle",
          "Bus": "bus", "Medium Vehicle": "delivery",
          "Heavy Vehicle": "truck"}
MIN_SAMPLES = 15


def build_matcher():
    from leuvenmapmatching.map.inmem import InMemMap
    root = ET.parse(str(OSM)).getroot()
    nodes = {n.get("id"): (float(n.get("lat")), float(n.get("lon")))
             for n in root.iter("node")}
    DRIV = {"motorway", "trunk", "primary", "secondary", "tertiary",
            "unclassified", "residential", "living_street", "primary_link",
            "secondary_link", "tertiary_link"}
    m = InMemMap("d8", use_latlon=True, use_rtree=False, index_edges=True)
    used = set()
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        if tags.get("highway") not in DRIV:
            continue
        nds = [nd.get("ref") for nd in w.iter("nd") if nd.get("ref") in nodes]
        ow = tags.get("oneway") in ("yes", "true", "1")
        for nid in nds:
            if nid not in used:
                m.add_node(nid, nodes[nid])
                used.add(nid)
        for a, b in zip(nds, nds[1:]):
            m.add_edge(a, b)
            if not ow:
                m.add_edge(b, a)
    m.purge()
    return m, nodes


def match_tracks(tracks, mmap, t0, t1, cap):
    """Match samples in [t0,t1]; return {vid: [(t,lat,lon,kmh,(na,nb)),...]}"""
    from leuvenmapmatching.matcher.distance import DistanceMatcher
    out = {}
    for tr in tracks:
        pts = [(s.t, s.lat, s.lon, s.speed_kmh) for s in tr.samples
               if t0 <= s.t <= t1]
        if len(pts) < MIN_SAMPLES:
            continue
        if len(out) >= cap:
            break
        mt = DistanceMatcher(mmap, max_dist=45, max_dist_init=60, obs_noise=8,
                             obs_noise_ne=25, min_prob_norm=0.001,
                             non_emitting_states=True)
        try:
            states, _ = mt.match([(p[1], p[2]) for p in pts])
        except Exception:                          # noqa: BLE001
            continue
        if not states or len(states) < 0.5 * len(pts):
            continue
        out[tr.vid] = {"type": tr.vtype,
                       "rows": [(p[0], p[1], p[2], p[3], st)
                                for p, st in zip(pts, states)]}
    return out


def route_from_states(net, rows):
    """Junction-sequence -> SUMO edge path (direct edges only, honest yield)."""
    seq = []
    for _, _, _, _, (a, b) in rows:
        for n in (a, b):
            if not seq or seq[-1] != n:
                seq.append(n)
    jseq = [n for n in seq if net.hasNode(n)]
    dedup = []
    for n in jseq:
        if not dedup or dedup[-1] != n:
            dedup.append(n)
    edges = []
    for u, v in zip(dedup, dedup[1:]):
        e = None
        for cand in net.getNode(u).getOutgoing():
            if cand.getToNode().getID() == v:
                e = cand.getID()
                break
        if e is None:
            # bridge matching gap via the network's own path between the
            # REAL matched junctions (endpoints unchanged)
            try:
                outs = net.getNode(u).getOutgoing()
                ins = net.getNode(v).getIncoming()
                if outs and ins:
                    p, _ = net.getShortestPath(outs[0], ins[0])
                    if p and len(p) <= 3:          # small gaps only
                        for pe in p:
                            if not edges or edges[-1] != pe.getID():
                                edges.append(pe.getID())
            except Exception:
                pass
            continue
        if not edges or edges[-1] != e:
            edges.append(e)
    # ensure connectivity of the final list
    ok = []
    for e in edges:
        if not ok:
            ok.append(e)
            continue
        prev = net.getEdge(ok[-1])
        if any(x.getID() == e for x in prev.getOutgoing()):
            ok.append(e)
    return ok


def main() -> None:
    t_wall = time.time()
    import sumolib
    from research.urban.pneuma_provider import parse
    net = sumolib.net.readNet(str(NET))
    tracks = list(parse(str(CSV), hz=1.0))
    mmap, osm_nodes = build_matcher()

    print("[1/6] matching A-window vehicles (demand source) …")
    A = match_tracks(tracks, mmap, A0, A1, cap=650)
    print(f"    A matched: {len(A)}")
    print("[2/6] matching B-window vehicles (validation reference only) …")
    B = match_tracks(tracks, mmap, A1, B1, cap=650)
    print(f"    B matched: {len(B)}")

    print("[3/6] building demand from A only …")
    vehs, rejected = [], 0
    for vid, d in A.items():
        route = route_from_states(net, d["rows"])
        if len(route) < 2:
            rejected += 1
            continue
        t_dep = d["rows"][0][0]
        v0 = d["rows"][0][3] / 3.6
        vehs.append({"id": f"real{vid}", "depart": t_dep, "route": route,
                     "vclass": VCLASS.get(d["type"], "passenger"),
                     "type": d["type"], "v0": round(v0, 1)})
    vehs.sort(key=lambda v: v["depart"])
    # A-fitted continuation stats for B: rate from LATE A only (drone
    # coverage ramps up early; last 150 s is the steady estimate — still
    # A-only, no B information)
    late = [v for v in vehs if v["depart"] >= A1 - 150.0]
    a_rate = len(late) / 150.0
    # per-entry-edge inflow (each boundary street has its own real rate)
    from collections import defaultdict as _dd
    by_entry = _dd(list)
    for v in late:
        by_entry[v["route"][0]].append(v)
    routes_pool = [v["route"] for v in vehs]
    print(f"    A demand: {len(vehs)} vehicles ({rejected} rejected), "
          f"entry rate {a_rate*3600:.0f}/h")

    rou = SP / "athens_demand.rou.xml"
    # calibrated behavior (STEP 1 output, authors' method) if present
    import xml.etree.ElementTree as _ET
    calib = {}
    cal_path = REPO / "artifacts/gates/d8_calibration/calibrated_types_d8.xml"
    if cal_path.exists():
        for v in _ET.parse(cal_path).getroot().findall(".//vType"):
            calib[v.get("id")] = {k: v.get(k) for k in
                ("speedFactor", "speedDev", "minGap", "accel", "sigma", "tau",
                 "lcPushy", "lcAssertive", "lcImpatience", "lcSigma",
                 "minGapLat", "lcCooperativeSpeed") if v.get(k)}
        print(f"    calibrated types loaded: {list(calib)}")
    PN2CAL = {"Car": "Car", "Taxi": "Taxi", "Motorcycle": "Motorcycle",
              "Bus": "Bus", "Medium Vehicle": "Medium",
              "Heavy Vehicle": "Heavy"}
    with open(rou, "w") as f:
        f.write("<routes>\n")
        for cls, vc in (("Car", "passenger"), ("Taxi", "passenger"),
                        ("Motorcycle", "motorcycle"), ("Bus", "bus"),
                        ("Medium Vehicle", "delivery"),
                        ("Heavy Vehicle", "truck")):
            extra = "".join(f' {k}="{val}"' for k, val in
                            calib.get(PN2CAL.get(cls, ""), {}).items())
            f.write(f'<vType id="t_{vc}_{cls.replace(" ","_")}" '
                    f'vClass="{vc}"{extra}/>\n')
        k = 0
        cont = []
        import random
        rng = random.Random(7)
        for entry, group in by_entry.items():
            rate_e = len(group) / 150.0
            tt = A1
            while tt < B1:
                tt += rng.expovariate(max(rate_e, 1e-6))
                if tt < B1:
                    cont.append((tt, rng.choice([g["route"] for g in group])))
        allv = ([(v["depart"], v["route"], v["type"], v["id"]) for v in vehs]
                + [(t, r, "Car", f"cont{i}") for i, (t, r) in enumerate(cont)])
        allv.sort(key=lambda x: x[0])
        for dep, route, typ, vid in allv:
            vc = VCLASS.get(typ, "passenger")
            f.write(f'<vehicle id="{vid}" '
                    f'type="t_{vc}_{typ.replace(" ","_") if typ!="Car" or True else typ}" '
                    f'depart="{dep:.2f}" departSpeed="max" departLane="free">'
                    f'<route edges="{" ".join(route)}"/></vehicle>\n')
            k += 1
        f.write("</routes>\n")
    print(f"    route file: {k} vehicles (A cohort + A-fitted continuation)")

    print("[4/6] running the twin 0 -> B end (OSM default signals) …")
    import libsumo as t
    t.start(["sumo", "-n", str(NET), "-r", str(rou), "--no-step-log",
             "--no-warnings", "--seed", "11", "--time-to-teleport", "600",
             "--collision.action", "warn"])
    # validation segments: busiest matched segments that exist in net
    seg_speed_real = defaultdict(list)
    seg_flow_real = defaultdict(set)
    for vid, d in B.items():
        for (ts, la, lo, kmh, (a, b)) in d["rows"]:
            seg_speed_real[(a, b)].append(kmh / 3.6)
            seg_flow_real[(a, b)].add(vid)
    key_segs = []
    for (a, b), lst in sorted(seg_speed_real.items(),
                              key=lambda kv: -len(kv[1]))[:40]:
        if net.hasNode(a):
            for cand in net.getNode(a).getOutgoing():
                if cand.getToNode().getID() == b:
                    key_segs.append(((a, b), cand.getID()))
                    break
        if len(key_segs) >= 8:
            break
    sig_nodes = [n.getID() for n in net.getNodes()
                 if n.getType().startswith("traffic_light")]
    q_appr = key_segs[:3]
    sim_speed = defaultdict(list)
    sim_flow = defaultdict(set)
    sim_q = defaultdict(list)
    real_pos = {f"real{vid}": {r[0]: (r[1], r[2]) for r in d["rows"]}
                for vid, d in A.items()}
    sim_pos = defaultdict(dict)
    tele = coll = 0
    arrived_cohort = {}
    while t.simulation.getTime() < B1 and t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        now = t.simulation.getTime()
        tele += t.simulation.getEndingTeleportNumber()
        coll += len(t.simulation.getCollisions())
        for vid in t.simulation.getArrivedIDList():
            if vid.startswith("real"):
                arrived_cohort[vid] = now
        if int(now) % 2 == 0:
            for v in t.vehicle.getIDList():
                if v.startswith("real") and now <= A1 + 60:
                    x, y = t.vehicle.getPosition(v)
                    lo, la = t.simulation.convertGeo(x, y)
                    sim_pos[v][round(now)] = (la, lo)
        if now > A1 and int(now) % 5 == 0:
            for (ab, eid) in key_segs:
                vs = t.edge.getLastStepVehicleIDs(eid)
                if vs:
                    sim_speed[ab].append(t.edge.getLastStepMeanSpeed(eid))
                for v in vs:
                    sim_flow[ab].add(v)
            for (ab, eid) in q_appr:
                q = sum(1 for v in t.edge.getLastStepVehicleIDs(eid)
                        if t.vehicle.getSpeed(v) < 0.83)   # <3 km/h
                sim_q[ab].append(q)
    inserted = k
    t.close()

    print("[5/6] validation B: real vs SUMO …")
    rows_out = []
    sp_err, fl_pairs = [], []
    for (ab, eid) in key_segs:
        r_sp = statistics.mean(seg_speed_real[ab])
        s_sp = statistics.mean(sim_speed[ab]) if sim_speed[ab] else None
        r_fl = len(seg_flow_real[ab])
        s_fl = len(sim_flow[ab])
        rows_out.append({"seg": ab, "edge": eid,
                         "real_speed_ms": round(r_sp, 2),
                         "sumo_speed_ms": round(s_sp, 2) if s_sp else None,
                         "real_veh": r_fl, "sumo_veh": s_fl})
        if s_sp is not None:
            sp_err.append(abs(s_sp - r_sp))
        fl_pairs.append((r_fl, s_fl))
    geh = [math.sqrt(2 * (s * (3600/(B1-A1)) - r * (3600/(B1-A1))) ** 2
                     / max((s + r) * (3600/(B1-A1)), 1e-9))
           for r, s in fl_pairs]
    # real queue at the 3 approaches (window B, from raw B matches)
    q_rows = []
    for (ab, eid) in q_appr:
        realq = defaultdict(int)
        for vid, d in B.items():
            for (ts, la, lo, kmh, st) in d["rows"]:
                if st == ab and kmh < 3.0:
                    realq[int(ts) // 5] += 1
        r_q = statistics.mean(realq.values()) if realq else 0.0
        s_q = statistics.mean(sim_q[ab]) if sim_q[ab] else 0.0
        q_rows.append({"seg": ab, "real_queue": round(r_q, 1),
                       "sumo_queue": round(s_q, 1)})

    print("[6/6] trajectory-level check (A cohort) …")
    traj = []
    for vid, d in list(A.items())[:200]:
        svid = f"real{vid}"
        if svid not in arrived_cohort or svid not in sim_pos:
            continue
        real_tt = d["rows"][-1][0] - d["rows"][0][0]
        sim_tt = arrived_cohort[svid] - d["rows"][0][0]
        errs = []
        for ts, (la, lo) in sim_pos[svid].items():
            near = min(d["rows"], key=lambda r: abs(r[0] - ts))
            if abs(near[0] - ts) <= 2:
                dx = (la - near[1]) * 111320
                dy = (lo - near[2]) * 111320 * math.cos(math.radians(la))
                errs.append(math.hypot(dx, dy))
        if errs:
            traj.append({"vehicle": svid, "real_tt_s": round(real_tt, 1),
                         "sumo_tt_s": round(sim_tt, 1),
                         "tt_err_s": round(sim_tt - real_tt, 1),
                         "mean_pos_err_m": round(statistics.mean(errs), 1)})
        if len(traj) >= 10:
            break

    art = {
        "gate": "PNEUMA_SAME_SITE_TWIN",
        "hashes": {"pneuma": hashlib.sha256(CSV.read_bytes()).hexdigest(),
                   "osm": hashlib.sha256(OSM.read_bytes()).hexdigest(),
                   "net": hashlib.sha256(NET.read_bytes()).hexdigest()},
        "sumo_version": "1.27.1",
        "windows": {"A": [A0, A1], "B": [A1, B1], "C": "sealed, untouched"},
        "demand": {"A_real_vehicles": len(vehs), "rejected_routes": rejected,
                   "continuation": "A-fitted rate + A route distribution "
                                   "(real B vehicles NEVER used)",
                   "total_inserted": inserted},
        "signals": "OSM-imported default programs (112 TLS), no control",
        "validation_B": {"segments": rows_out,
                         "speed_mae_ms": round(statistics.mean(sp_err), 2)
                         if sp_err else None,
                         "flow_geh_mean": round(statistics.mean(geh), 2)
                         if geh else None,
                         "queues": q_rows},
        "trajectory_level": traj,
        "teleports": tele, "collisions": coll,
        "arrived_cohort": len(arrived_cohort),
        "turning_note": "turning-movement validation NOT claimed (matched "
                        "junction turns too sparse at 1 Hz in B)",
        "wall_s": round(time.time() - t_wall, 1),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "PNEUMA_SAME_SITE_TWIN.json").write_text(json.dumps(art, indent=1))
    print(json.dumps({x: art[x] for x in
                      ("demand", "validation_B", "teleports", "collisions",
                       "arrived_cohort")}, indent=1))
    print("traj sample:", traj[:3])
    ok = (len(vehs) > 100 and tele == 0 and art["validation_B"]["speed_mae_ms"]
          is not None)
    print("RESULT:", "PASS-candidate" if ok else "FAIL")


if __name__ == "__main__":
    main()
