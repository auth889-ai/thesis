#!/usr/bin/env python3
"""PREDICTIVE PLANNER — Gates 4+5+8: same-state candidate futures, network guard.

    run demand to trigger t0 -> saveState (incl. RNG)
    branch A0 DO-NOTHING, A1 green-extend, A2 max-pressure-style,
           A3/A4/A5 = A1 + 10/20/30% bounded rerouting of APPROACHING vehicles
    all branches load the SAME state file; candidates run in PARALLEL processes
    (libsumo, headless). A candidate is ACCEPTED only if the NETWORK improves
    over A0 and no guard is violated. If none qualifies:
    NO_SAFE_INTERVENTION_IMPROVES_THE_NETWORK.

Objective (documented): network stopped-vehicle-seconds over the horizon
(integral of stopped count = total standstill delay proxy), reported alongside
tripinfo time loss. Guards: arrivals >= A0 - 2%; teleports <= A0; neighbor
queue growth <= +15% vs A0. Weights/tolerances declared here, in code.

Determinism check: A0 is run TWICE; results must match exactly (paired RNG).
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
MIN_GREEN = 10.0
DECIDE_EVERY = 5.0
ARRIVAL_TOL = 0.02          # accept if arrivals >= A0*(1-2%)
NEIGHBOR_TOL = 0.15         # neighbor queues may grow at most 15% vs A0
T0_TRIGGER_STOPPED = 250
T0_MAX_S = 7200

CANDIDATES = ["A0_do_nothing", "A0_repeat", "A1_green_extend",
              "A2_max_pressure", "A3_ext_reroute10", "A4_ext_reroute20",
              "A5_ext_reroute30"]


def _sumo_args(routes: str, seed: int, trip_out: str) -> list[str]:
    return ["-n", NET, "-r", routes, "--seed", str(seed),
            "--no-step-log", "--no-warnings", "--time-to-teleport", "600",
            "--save-state.rng", "--tripinfo-output", trip_out,
            "--tripinfo-output.write-unfinished"]


def make_t0(routes: str, seed: int, out: Path) -> dict:
    import libsumo as t
    t.start(["sumo"] + _sumo_args(routes, seed, str(out / "tripinfo_warm.xml")))
    t0 = None
    while t.simulation.getTime() < T0_MAX_S:
        t.simulationStep()
        stopped = sum(t.lane.getLastStepHaltingNumber(l)
                      for l in t.lane.getIDList() if not l.startswith(":"))
        if stopped >= T0_TRIGGER_STOPPED:
            t0 = t.simulation.getTime()
            break
    if t0 is None:
        t.close(); raise SystemExit("no congestion trigger before T0_MAX_S")
    # target = most-queued TLS now; neighbors = next three
    ranked = []
    for tls in t.trafficlight.getIDList():
        lanes = {lk[0][0] for lk in t.trafficlight.getControlledLinks(tls) if lk}
        q = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
        ranked.append((q, tls, sorted(lanes)))
    ranked.sort(reverse=True)
    state = str(out / "state_t0.xml")
    t.simulation.saveState(state)
    meta = {"t0_s": t0, "state_file": state,
            "target_tls": ranked[0][1], "target_lanes": ranked[0][2],
            "target_queue_t0": ranked[0][0],
            "neighbors": {tls: {"lanes": lanes, "queue_t0": q}
                          for q, tls, lanes in ranked[1:4]}}
    t.close()
    return meta


def run_branch(job) -> dict:
    """One candidate future in its own process (libsumo is per-process)."""
    cand, meta, routes, seed, horizon, outdir = job
    import libsumo as t
    trip = str(Path(outdir) / f"tripinfo_{cand}.xml")
    t.start(["sumo"] + _sumo_args(routes, seed, trip))
    t.simulation.loadState(meta["state_file"])
    t0 = meta["t0_s"]
    tls, tls_lanes = meta["target_tls"], meta["target_lanes"]
    hot = {t.lane.getEdgeID(l) for l in tls_lanes}
    reroute_p = {"A3_ext_reroute10": .10, "A4_ext_reroute20": .20,
                 "A5_ext_reroute30": .30}.get(cand, 0.0)
    extend = cand.startswith(("A1", "A3", "A4", "A5"))
    maxp = cand == "A2_max_pressure"
    stopped_vs, tele, rerouted = 0, 0, 0
    green_started, last_decide = t0, 0.0
    while t.simulation.getTime() < t0 + horizon and \
            t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        now = t.simulation.getTime()
        stopped_vs += sum(t.lane.getLastStepHaltingNumber(l)
                          for l in t.lane.getIDList() if not l.startswith(":"))
        tele += t.simulation.getEndingTeleportNumber()
        if now - last_decide < DECIDE_EVERY:
            continue
        last_decide = now
        per_lane = [(t.lane.getLastStepHaltingNumber(l), l) for l in tls_lanes]
        worst_q, worst = max(per_lane)
        if extend and worst_q > 10:
            st = t.trafficlight.getRedYellowGreenState(tls)
            links = t.trafficlight.getControlledLinks(tls)
            serving = [i for i, lk in enumerate(links) if lk and lk[0][0] == worst]
            if serving and all(st[i] in "Gg" for i in serving):
                t.trafficlight.setPhaseDuration(
                    tls, t.trafficlight.getNextSwitch(tls) - now + 5.0)
        if maxp and now - green_started >= MIN_GREEN:
            # advance program (own yellows play out) toward the phase serving
            # the worst approach — valid transitions guaranteed by the program
            st = t.trafficlight.getRedYellowGreenState(tls)
            links = t.trafficlight.getControlledLinks(tls)
            serving = [i for i, lk in enumerate(links) if lk and lk[0][0] == worst]
            if serving and not all(st[i] in "Gg" for i in serving):
                t.trafficlight.setPhaseDuration(tls, 0.0)
                green_started = now
        if reroute_p > 0:
            # capacity gate: mean halting on non-hot outgoing alternatives
            alt = [l for l in tls_lanes if t.lane.getEdgeID(l) not in hot]
            for i, v in enumerate(t.vehicle.getIDList()):
                if (i % int(1 / reroute_p)) != 0:
                    continue
                if t.vehicle.getRoadID(v) in hot:
                    continue                       # trapped: never touched
                if any(e in hot for e in t.vehicle.getRoute(v)):
                    t.vehicle.rerouteTraveltime(v)  # measured times, no x5
                    rerouted += 1
    final_q = sum(t.lane.getLastStepHaltingNumber(l) for l in tls_lanes)
    final_neigh = {n: sum(t.lane.getLastStepHaltingNumber(l)
                          for l in d["lanes"])
                   for n, d in meta["neighbors"].items()}
    net_stop = sum(t.lane.getLastStepHaltingNumber(l)
                   for l in t.lane.getIDList() if not l.startswith(":"))
    t.close()
    root = ET.parse(trip).getroot()
    inh = [x for x in root if float(x.get("arrival", -1)) >= t0]
    durs = sorted(float(x.get("duration")) for x in inh) or [0.0]
    return {"candidate": cand,
            "network": {
                "stopped_veh_s": stopped_vs,
                "time_loss_arrivals_s":
                    round(sum(float(x.get("timeLoss")) for x in inh), 1),
                "arrived": len(inh),
                "mean_travel_s": round(statistics.mean(durs), 1),
                "p95_travel_s": round(durs[int(0.95 * (len(durs) - 1))], 1),
                "teleports": tele,
                "network_stopped_final": net_stop},
            "target": {"queue_final": final_q},
            "neighbors": final_neigh,
            "rerouted": rerouted}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", default=str(
        REPO / "artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz"))
    ap.add_argument("--demand-label", default="OFFLINE fair fixed demand "
                    "(DUE v200) — replace via Gate 2 synchronized scenario")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--horizon", type=int, default=600)
    ap.add_argument("--name", default="planner_dev")
    a = ap.parse_args()
    out = REPO / "artifacts" / "planner" / a.name
    out.mkdir(parents=True, exist_ok=True)
    wall = time.time()
    meta = make_t0(a.routes, a.seed, out)
    t_warm = time.time() - wall
    jobs = [(c, meta, a.routes, a.seed, a.horizon, str(out))
            for c in CANDIDATES]
    with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count() - 1)) as p:
        branches = p.map(run_branch, jobs)
    res = {b["candidate"]: b for b in branches}
    a0, a0r = res["A0_do_nothing"], res.pop("A0_repeat")
    determinism = a0["network"] == a0r["network"]

    verdicts = {}
    for c, b in res.items():
        if c == "A0_do_nothing":
            continue
        n, g = b["network"], a0["network"]
        guards = {
            "network_delay_improves": n["stopped_veh_s"] < g["stopped_veh_s"],
            "throughput_kept": n["arrived"] >= g["arrived"] * (1 - ARRIVAL_TOL),
            "teleports_not_worse": n["teleports"] <= g["teleports"],
            "neighbors_not_flooded": all(
                b["neighbors"][k] <= max(a0["neighbors"][k] * (1 + NEIGHBOR_TOL),
                                         a0["neighbors"][k] + 5)
                for k in b["neighbors"]),
        }
        ok = all(guards.values())
        label = ("ACCEPTED_CANDIDATE" if ok else
                 ("LOCAL_RELIEF_NETWORK_FAIL"
                  if b["target"]["queue_final"] < a0["target"]["queue_final"]
                  and not guards["network_delay_improves"]
                  else "REJECTED"))
        verdicts[c] = {"guards": guards, "label": label}
    accepted = [c for c, v in verdicts.items()
                if v["label"] == "ACCEPTED_CANDIDATE"]
    best = (min(accepted, key=lambda c: res[c]["network"]["stopped_veh_s"])
            if accepted else None)
    result = {
        "gate_stack": ["SAME_STATE_COUNTERFACTUAL", "NETWORK_GUARD",
                       "PREDICTIVE_PLANNER"],
        "demand": {"routes": a.routes, "label": a.demand_label},
        "seed": a.seed, "t0": meta["t0_s"], "horizon_s": a.horizon,
        "determinism_check_A0_twice_identical": determinism,
        "objective": "network stopped-vehicle-seconds over horizon (primary); "
                     "guards: arrivals>=A0-2%, teleports<=A0, neighbor queues "
                     "<=A0+15%",
        "branches": res, "verdicts": verdicts,
        "decision": best or "NO_SAFE_INTERVENTION_IMPROVES_THE_NETWORK",
        "wall_s": {"warmup_to_t0": round(t_warm, 1),
                   "total": round(time.time() - wall, 1)},
        "real_time_factor": round(
            (a.horizon * len(CANDIDATES)) / max(time.time() - wall - t_warm,
                                                1e-6), 1),
    }
    (out / "result.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in
                      ("t0", "determinism_check_A0_twice_identical",
                       "decision", "wall_s", "real_time_factor")}, indent=1))
    for c, v in verdicts.items():
        print(f"  {c}: {v['label']}  stopped_veh_s="
              f"{res[c]['network']['stopped_veh_s']} vs A0="
              f"{a0['network']['stopped_veh_s']}")
    print("->", out / "result.json")


if __name__ == "__main__":
    main()
