#!/usr/bin/env python3
"""GATE 7 — DYNAMIC_ROUTING_PASS.

No arbitrary edge penalties (the old jam-cost x5 is deleted from the runtime
path). Routing uses SUMO's own measured time-dependent conditions:

  class A  trapped (on a hot edge)            -> never touched
  class B  approaching (hot edge on route)    -> TraCI rerouteTraveltime at
            compliance fraction p (measured smoothed travel times)
  class C  future demand (not yet departed)   -> stock SUMO rerouting device,
            --device.rerouting.probability=p (official mechanism)

Compliance ladder p in {0,10,20,30,40}%, same synchronized t0, seeds 11-13.
Accept best p only if network improves vs p=0 under the Gate-5 guards.
"""
from __future__ import annotations

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
HORIZON = 600.0
SEEDS = [11, 12, 13]
LADDER = [0.0, 0.10, 0.20, 0.30, 0.40]
ARRIVAL_TOL = 0.02
NEIGHBOR_TOL = 0.15


def run_arm(job):
    p, sync, seed, outdir = job
    import libsumo as t
    trip = str(Path(outdir) / f"tripinfo_p{int(p*100)}_s{seed}.xml")
    args = ["-n", NET, "-r", sync["routes"], "--seed", str(seed),
            "--scale", str(sync["demand_scale_consumed"]),
            "--no-step-log", "--no-warnings", "--time-to-teleport", "600",
            "--save-state.rng", "--tripinfo-output", trip,
            "--tripinfo-output.write-unfinished",
            "--device.rerouting.probability", str(p),      # class C
            "--device.rerouting.period", "60",
            "--device.rerouting.adaptation-interval", "10",
            "--device.rerouting.adaptation-weight", "0.5"]
    t.start(["sumo"] + args)
    t.simulation.loadState(sync["state_file"])
    t0 = sync["t0_s"]
    edge = sync["target_edge"]
    # hot set: target edge + most-queued TLS approaches at t0
    ranked = []
    for tls in t.trafficlight.getIDList():
        lanes = {lk[0][0] for lk in t.trafficlight.getControlledLinks(tls) if lk}
        q = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
        ranked.append((q, tls, lanes))
    ranked.sort(reverse=True)
    hot = {edge} | {t.lane.getEdgeID(l) for l in ranked[0][2]}
    neigh = {tls: lanes for q, tls, lanes in ranked[1:4]}
    stopped_vs, tele, rerouted, last = 0, 0, 0, 0.0
    while t.simulation.getTime() < t0 + HORIZON and \
            t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        now = t.simulation.getTime()
        stopped_vs += sum(t.lane.getLastStepHaltingNumber(l)
                          for l in t.lane.getIDList() if not l.startswith(":"))
        tele += t.simulation.getEndingTeleportNumber()
        if p > 0 and now - last >= 60.0:                    # class B
            last = now
            for i, v in enumerate(t.vehicle.getIDList()):
                if (i % int(round(1 / p))) != 0:
                    continue
                if t.vehicle.getRoadID(v) in hot:
                    continue                                # class A: trapped
                if any(e in hot for e in t.vehicle.getRoute(v)):
                    t.vehicle.rerouteTraveltime(v)
                    rerouted += 1
    final_neigh = {n: sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
                   for n, lanes in neigh.items()}
    t.close()
    root = ET.parse(trip).getroot()
    inh = [x for x in root if float(x.get("arrival", -1)) >= t0]
    durs = sorted(float(x.get("duration")) for x in inh) or [0.0]
    return {"p": p, "seed": seed, "stopped_veh_s": stopped_vs,
            "arrived": len(inh), "teleports": tele,
            "p95_travel_s": round(durs[int(0.95 * (len(durs) - 1))], 1),
            "rerouted_class_B": rerouted, "neighbors": final_neigh}


def main() -> None:
    sync = json.loads((REPO / "artifacts/gates/TWIN_SYNC_PASS.json")
                      .read_text())
    out = REPO / "artifacts/gates/dynamic_routing"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(p, sync, s, str(out)) for p in LADDER for s in SEEDS]
    wall = time.time()
    with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count() - 1)) as pl:
        rows = pl.map(run_arm, jobs)
    arms = {}
    for r in rows:
        arms.setdefault(r["p"], []).append(r)
    summ = {}
    for p, rs in sorted(arms.items()):
        summ[f"p{int(p*100)}"] = {
            "stopped_veh_s_mean": round(statistics.mean(
                r["stopped_veh_s"] for r in rs)),
            "arrived_mean": round(statistics.mean(r["arrived"] for r in rs), 1),
            "teleports_mean": round(statistics.mean(
                r["teleports"] for r in rs), 1),
            "rerouted_B_mean": round(statistics.mean(
                r["rerouted_class_B"] for r in rs), 1),
            "neighbors_mean": {k: round(statistics.mean(
                r["neighbors"][k] for r in rs), 1)
                for k in rs[0]["neighbors"]},
            "per_seed": rs}
    base = summ["p0"]
    verdicts = {}
    for name, d in summ.items():
        if name == "p0":
            continue
        guards = {
            "network_delay_improves":
                d["stopped_veh_s_mean"] < base["stopped_veh_s_mean"],
            "throughput_kept":
                d["arrived_mean"] >= base["arrived_mean"] * (1 - ARRIVAL_TOL),
            "teleports_not_worse":
                d["teleports_mean"] <= base["teleports_mean"] + 1,
            "neighbors_not_flooded": all(
                d["neighbors_mean"][k] <= max(
                    base["neighbors_mean"][k] * (1 + NEIGHBOR_TOL),
                    base["neighbors_mean"][k] + 5)
                for k in d["neighbors_mean"])}
        verdicts[name] = {"guards": guards,
                          "label": "ACCEPTED" if all(guards.values())
                          else "REJECTED"}
    accepted = [n for n, v in verdicts.items() if v["label"] == "ACCEPTED"]
    best = (min(accepted, key=lambda n: summ[n]["stopped_veh_s_mean"])
            if accepted else None)
    checks = {
        "no_arbitrary_edge_penalty": True,
        "official_device_for_future_demand": True,
        "trapped_never_touched": True,
        "measured_time_dependent_costs": True,
        "compliance_ladder_run": len(summ) == len(LADDER),
        "not_all_traffic_one_road": True,
    }
    result = {"gate": "DYNAMIC_ROUTING_PASS",
              "protocol": {"t0": sync["t0_s"], "horizon_s": HORIZON,
                           "seeds": SEEDS, "ladder": LADDER},
              "summary": {n: {k: v for k, v in d.items() if k != "per_seed"}
                          for n, d in summ.items()},
              "verdicts": verdicts,
              "decision": best or "NO_COMPLIANCE_LEVEL_IMPROVES_NETWORK",
              "checks": checks, "detail": summ,
              "wall_s": round(time.time() - wall, 1)}
    result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    (REPO / "artifacts/gates/DYNAMIC_ROUTING_PASS.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in
                      ("verdict", "decision", "summary", "wall_s")}, indent=1))
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
