#!/usr/bin/env python3
"""FINAL SEALED VALIDATION on independent session D — run ONCE.

Freeze guard: refuses to run if the frozen config, its hash sidecar, the
network, the calibrated types, or the working tree of scripts/research have
changed since the freeze commit. All metrics computed at runtime from raw D
trajectories and SUMO FCD output — no precomputed result JSONs are read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
OUT = REPO / "results/final_validation"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def freeze_guard(cfg, cfg_path):
    errs = []
    if sha(cfg_path) != (REPO / "configs/final_twin_frozen.sha256").read_text().strip():
        errs.append("config hash != sidecar (config edited after freeze)")
    if sha(cfg["network"]["path"]) != cfg["network"]["sha256"]:
        errs.append("network file changed")
    if sha(cfg["calibration"]["types_file"]) != cfg["calibration"]["types_sha256"]:
        errs.append("calibrated types changed")
    if sha(cfg["D_session"]["path"]) != cfg["D_session"]["sha256"]:
        errs.append("D data changed")
    dirty = subprocess.run(
        ["git", "diff", "--quiet", cfg["git_sha"], "HEAD", "--",
         "scripts/", "research/"], cwd=REPO).returncode
    wt = subprocess.run(["git", "diff", "--quiet", "--", "scripts/",
                         "research/"], cwd=REPO).returncode
    if dirty or wt:
        errs.append("code changed since freeze commit " + cfg["git_sha"][:10])
    if errs:
        print("FREEZE GUARD REFUSED:", errs)
        sys.exit(2)
    print("freeze guard OK (config, net, types, D, code all frozen)")


# ---------------- D loading + mapping (frozen algorithm) -------------------
def load_and_match(cfg):
    from research.urban.pneuma_provider import parse
    from scripts.gate_pneuma_twin import build_matcher, route_from_states
    from leuvenmapmatching.matcher.distance import DistanceMatcher
    import sumolib
    net = sumolib.net.readNet(cfg["network"]["path"])
    tracks = list(parse(cfg["D_session"]["path"], hz=1.0))
    dur = max(tr.samples[-1].t for tr in tracks)
    a1 = dur * cfg["windows"]["input_fraction"]
    mmap, _nodes = build_matcher()
    cohort, meas_ref = {}, {}
    for tr in tracks:
        pts_in = [(s.t, s.lat, s.lon, s.speed_kmh) for s in tr.samples
                  if s.t <= a1]
        pts_ms = [(s.t, s.lat, s.lon, s.speed_kmh) for s in tr.samples
                  if s.t > a1]
        for pts, dst, cap in ((pts_in, cohort, 650), (pts_ms, meas_ref, 650)):
            if len(pts) < 12 or len(dst) >= cap or tr.vid in dst:
                continue
            m = DistanceMatcher(mmap, max_dist=45, max_dist_init=60,
                                obs_noise=8, obs_noise_ne=25,
                                min_prob_norm=0.001,
                                non_emitting_states=True)
            try:
                st, _ = m.match([(p[1], p[2]) for p in pts])
            except Exception:
                continue
            if st and len(st) >= 0.5 * len(pts):
                dst[tr.vid] = {"type": tr.vtype,
                               "rows": [(p[0], p[1], p[2], p[3], s_)
                                        for p, s_ in zip(pts, st)]}
    return net, tracks, dur, a1, cohort, meas_ref


# ---------------- frozen demand + SUMO run --------------------------------
def run_twin(cfg, net, cohort, a1, d_end):
    from scripts.gate_pneuma_twin import route_from_states
    VCLASS = {"Car": "passenger", "Taxi": "passenger",
              "Motorcycle": "motorcycle", "Bus": "bus",
              "Medium Vehicle": "delivery", "Heavy Vehicle": "truck"}
    P2C = {"Car": "Car", "Taxi": "Taxi", "Motorcycle": "Motorcycle",
           "Bus": "Bus", "Medium Vehicle": "Medium",
           "Heavy Vehicle": "Heavy"}
    vehs, rej = [], 0
    for vid, d in cohort.items():
        r = route_from_states(net, d["rows"])
        if len(r) < 2:
            rej += 1
            continue
        vehs.append({"id": f"real{vid}", "depart": d["rows"][0][0],
                     "route": r, "type": d["type"]})
    vehs.sort(key=lambda v: v["depart"])
    late = [v for v in vehs if v["depart"] >= a1 - 150.0]
    by_entry = defaultdict(list)
    for v in late:
        by_entry[v["route"][0]].append(v)
    rng = random.Random(cfg["seeds"]["continuation_rng"])
    cont = []
    for entry, grp in by_entry.items():
        rate = len(grp) / 150.0
        tt = a1
        while True:
            tt += rng.expovariate(max(rate, 1e-6))
            if tt >= d_end:
                break
            cont.append((tt, rng.choice([g["route"] for g in grp])))
    rou = OUT / "demand_D.rou.xml"
    with open(rou, "w") as f:
        f.write("<routes>\n")
        cal = cfg["calibration"]["parameters"]
        for cls, vc in VCLASS.items():
            extra = "".join(f' {k}="{v}"' for k, v in
                            cal.get(P2C[cls], {}).items())
            f.write(f'<vType id="t_{cls.replace(" ","_")}" vClass="{vc}"'
                    f'{extra}/>\n')
        allv = ([(v["depart"], v["route"], v["type"], v["id"])
                 for v in vehs]
                + [(t, r, "Car", f"cont{i}") for i, (t, r)
                   in enumerate(cont)])
        allv.sort(key=lambda x: x[0])
        for dep, route, typ, vid in allv:
            f.write(f'<vehicle id="{vid}" type="t_{typ.replace(" ","_")}" '
                    f'depart="{dep:.2f}" departSpeed="max" '
                    f'departLane="free"><route edges='
                    f'"{" ".join(route)}"/></vehicle>\n')
        f.write("</routes>\n")
    import libsumo as t
    fcd = OUT / "fcd.xml"
    t.start(["sumo", "-n", cfg["network"]["path"], "-r", str(rou),
             "--no-step-log", "--no-warnings",
             "--seed", str(cfg["seeds"]["sumo"]),
             "--time-to-teleport", "600",
             "--collision.action", "warn",
             "--fcd-output", str(fcd), "--fcd-output.geo",
             "--device.fcd.begin", str(a1)])
    tele = coll = 0
    arrived = {}
    while t.simulation.getTime() < d_end and \
            t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        tele += t.simulation.getEndingTeleportNumber()
        coll += len(t.simulation.getCollisions())
        for v in t.simulation.getArrivedIDList():
            if v.startswith("real"):
                arrived[v] = t.simulation.getTime()
    t.close()
    return vehs, rej, len(cont), tele, coll, arrived, fcd


# ---------------- runtime metrics from raw + FCD --------------------------
def metrics(cfg, net, cohort, meas_ref, a1, d_end, arrived, fcd):
    import xml.etree.ElementTree as ET
    skip = cfg["windows"]["measurement_skip_first_s"]
    m0 = a1 + skip
    # real per-segment state (measurement window, from raw matched D)
    seg_speed_r = defaultdict(list)
    seg_veh_r = defaultdict(set)
    for vid, d in meas_ref.items():
        for (ts, la, lo, kmh, (a, b)) in d["rows"]:
            if ts >= m0:
                seg_speed_r[(a, b)].append(kmh / 3.6)
                seg_veh_r[(a, b)].add(vid)
    key = []
    for ab, lst in sorted(seg_speed_r.items(), key=lambda kv: -len(kv[1])):
        if net.hasNode(ab[0]):
            for e in net.getNode(ab[0]).getOutgoing():
                if e.getToNode().getID() == ab[1]:
                    key.append((ab, e.getID()))
                    break
        if len(key) >= 8:
            break
    # sim from FCD (edge speeds via nearest-node pairing is complex;
    # use edge assignment from FCD lane attribute)
    sim_speed = defaultdict(list)
    sim_veh = defaultdict(set)
    sim_pos = defaultdict(dict)
    q_sim = defaultdict(lambda: defaultdict(int))
    q_real = defaultdict(lambda: defaultdict(int))
    keyed = {eid: ab for ab, eid in key}
    for _, el in ET.iterparse(str(fcd)):
        if el.tag == "timestep":
            ts = float(el.get("time"))
            for v in el:
                lane = v.get("lane") or ""
                eid = lane.rsplit("_", 1)[0]
                sp = float(v.get("speed"))
                vid = v.get("id")
                if ts >= m0 and eid in keyed:
                    ab = keyed[eid]
                    sim_speed[ab].append(sp)
                    sim_veh[ab].add(vid)
                    if sp < 3.0:
                        q_sim[ab][int(ts) // 5] += 1
                if vid.startswith("real") and abs(ts - round(ts)) < 0.01:
                    sim_pos[vid][int(round(ts))] = (float(v.get("y")),
                                                    float(v.get("x")))
            el.clear()
    for vid, d in meas_ref.items():
        for (ts, la, lo, kmh, ab) in d["rows"]:
            if ts >= m0 and kmh < 10.8 and ab in dict(key):
                q_real[ab][int(ts) // 5] += 1
    rows = []
    sp_err = []
    geh = []
    for ab, eid in key:
        rs = statistics.mean(seg_speed_r[ab])
        ss = statistics.mean(sim_speed[ab]) if sim_speed[ab] else None
        rn, sn = len(seg_veh_r[ab]), len(sim_veh[ab])
        if ss is not None:
            sp_err.append(abs(ss - rs))
        w = (d_end - m0) / 3600
        geh.append(math.sqrt(2 * (sn / w - rn / w) ** 2
                             / max((sn + rn) / w, 1e-9)))
        rows.append({"seg": f"{ab[0]}-{ab[1]}", "edge": eid,
                     "real_speed": round(rs, 2),
                     "sim_speed": round(ss, 2) if ss else None,
                     "real_veh": rn, "sim_veh": sn})
    qr = [statistics.mean(q_real[ab].values()) if q_real[ab] else 0
          for ab, _ in key[:3]]
    qs = [statistics.mean(q_sim[ab].values()) if q_sim[ab] else 0
          for ab, _ in key[:3]]
    q_rel = (statistics.mean(abs(a - b) / max(a, 1) for a, b in zip(qr, qs))
             if qr else None)
    # cohort travel time + trajectory error
    tt_err, traj_err = [], []
    for vid, d in cohort.items():
        svid = f"real{vid}"
        if svid in arrived:
            real_tt = d["rows"][-1][0] - d["rows"][0][0]
            sim_tt = arrived[svid] - d["rows"][0][0]
            if real_tt > 5:
                tt_err.append(abs(sim_tt - real_tt) / real_tt)
        if svid in sim_pos:
            errs = []
            for (ts, la, lo, kmh, _ab) in d["rows"]:
                p = sim_pos[svid].get(int(round(ts)))
                if p:
                    dx = (p[0] - la) * 111320
                    dy = (p[1] - lo) * 111320 * math.cos(math.radians(la))
                    errs.append(math.hypot(dx, dy))
            if errs:
                traj_err.append(statistics.mean(errs))
    return {"segments": rows,
            "speed_mae_ms": round(statistics.mean(sp_err), 2)
            if sp_err else None,
            "flow_geh_mean_nongating": round(statistics.mean(geh), 2),
            "queues_real": [round(x, 1) for x in qr],
            "queues_sim": [round(x, 1) for x in qs],
            "queue_mean_rel_err": round(q_rel, 3) if q_rel is not None else None,
            "travel_time_median_rel_err":
                round(statistics.median(tt_err), 3) if tt_err else None,
            "trajectory_pos_err_m_mean":
                round(statistics.mean(traj_err), 1) if traj_err else None,
            "cohort_arrived": len(arrived)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    import yaml
    cfg = yaml.safe_load(open(a.config))
    freeze_guard(cfg, a.config)
    OUT.mkdir(parents=True, exist_ok=True)
    print("[1/4] loading + matching sealed D …")
    net, tracks, dur, a1, cohort, meas_ref = load_and_match(cfg)
    print(f"    D duration {dur:.1f}s · cohort {len(cohort)} · "
          f"measurement refs {len(meas_ref)}")
    print("[2/4] frozen twin run …")
    vehs, rej, ncont, tele, coll, arrived, fcd = run_twin(
        cfg, net, cohort, a1, dur)
    print(f"    demand {len(vehs)} real (+{ncont} continuation, {rej} "
          f"rejected) · teleports {tele} · collisions {coll}")
    print("[3/4] runtime metrics …")
    M = metrics(cfg, net, cohort, meas_ref, a1, dur, arrived, fcd)
    M["teleports"], M["collisions"] = tele, coll
    # outputs
    import csv as _csv
    with open(OUT / "observed_vs_simulated.csv", "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=list(M["segments"][0]))
        w.writeheader()
        w.writerows(M["segments"])
    with open(OUT / "real_measurements.csv", "w") as f:
        f.write("seg,real_speed,real_veh\n")
        for r in M["segments"]:
            f.write(f'{r["seg"]},{r["real_speed"]},{r["real_veh"]}\n')
    with open(OUT / "sim_measurements.csv", "w") as f:
        f.write("seg,sim_speed,sim_veh\n")
        for r in M["segments"]:
            f.write(f'{r["seg"]},{r["sim_speed"]},{r["sim_veh"]}\n')
    (OUT / "metrics.json").write_text(json.dumps(M, indent=1))
    # plots
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    segs = [r["seg"][:14] for r in M["segments"]]
    for what, rk, sk, fn in (
            ("speed m/s", "real_speed", "sim_speed", "speed_real_vs_sim.png"),
            ("vehicles", "real_veh", "sim_veh",
             "cumulative_discharge_real_vs_sim.png")):
        fig, ax = plt.subplots(figsize=(9, 4))
        x = range(len(segs))
        ax.bar([i - .2 for i in x], [r[rk] or 0 for r in M["segments"]],
               width=.4, label="real")
        ax.bar([i + .2 for i in x], [r[sk] or 0 for r in M["segments"]],
               width=.4, label="sim")
        ax.set_xticks(list(x))
        ax.set_xticklabels(segs, rotation=45, fontsize=7)
        ax.set_title(f"D validation: {what}")
        ax.legend()
        plt.tight_layout()
        plt.savefig(OUT / fn, dpi=120)
        plt.close(fig)
    for vals, title, fn in ((list(zip(M["queues_real"], M["queues_sim"])),
                             "queue (veh, 3 busiest approaches)",
                             "queue_real_vs_sim.png"),):
        fig, ax = plt.subplots(figsize=(6, 4))
        x = range(len(vals))
        ax.bar([i - .2 for i in x], [v[0] for v in vals], width=.4,
               label="real")
        ax.bar([i + .2 for i in x], [v[1] for v in vals], width=.4,
               label="sim")
        ax.set_title(title)
        ax.legend()
        plt.tight_layout()
        plt.savefig(OUT / fn, dpi=120)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.bar([0], [M["travel_time_median_rel_err"] or 0])
    ax.set_title("travel-time median rel. error (cohort)")
    plt.tight_layout()
    plt.savefig(OUT / "travel_time_real_vs_sim.png", dpi=120)
    plt.close(fig)
    print("[4/4] gating (frozen thresholds) …")
    th = cfg["gating_thresholds"]
    checks = {
        "speed": M["speed_mae_ms"] is not None
                 and M["speed_mae_ms"] <= th["speed_mae_ms_max"],
        "queue": M["queue_mean_rel_err"] is not None
                 and M["queue_mean_rel_err"] <= th["queue_mean_rel_err_max"],
        "trajectory": M["trajectory_pos_err_m_mean"] is not None
                 and M["trajectory_pos_err_m_mean"]
                 <= th["trajectory_pos_err_m_max"],
        "travel_time": M["travel_time_median_rel_err"] is not None
                 and M["travel_time_median_rel_err"]
                 <= th["travel_time_median_rel_err_max"],
        "teleports": tele <= th["teleports_max"],
        "collisions": coll <= th["collisions_max"],
    }
    M["checks"] = checks
    (OUT / "metrics.json").write_text(json.dumps(M, indent=1))
    print(json.dumps({k: M[k] for k in
                      ("speed_mae_ms", "queue_mean_rel_err",
                       "trajectory_pos_err_m_mean",
                       "travel_time_median_rel_err",
                       "flow_geh_mean_nongating", "queues_real",
                       "queues_sim", "teleports", "collisions",
                       "cohort_arrived", "checks")}, indent=1))
    verdict = ("FINAL_VALIDATION_PASS" if all(checks.values())
               else "FINAL_VALIDATION_FAIL")
    print("RESULT:", verdict)


if __name__ == "__main__":
    main()
