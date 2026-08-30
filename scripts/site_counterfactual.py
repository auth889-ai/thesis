#!/usr/bin/env python3
"""SITE X before/after — two futures from the validated synchronized state.

Branches from ONE saved state (incl. RNG), same arrivals, same horizon:
  A0  DO NOTHING
  A1  VSL harmonization: entry-edge speed 8 m/s (smooth the shockwave feed)
  A2  UPSTREAM GATING: 120 s of doubled insertion spacing, backlog released
      (ramp-metering pattern; held vehicles' delay COUNTS in the objective)
  A3  A1 + A2

Legitimate actions only (edge speed limits + insertion timing = infrastructure
control). No moveTo / teleport / deletion; zero-teleport check enforced.
Objective: total vehicle-seconds below 3 m/s in the visible stretch + total
upstream hold time; guards: throughput (discharges past mid-view) not worse
than A0 - 2%.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
NET = str(REPO / "artifacts/site_i70/i70_pena.net.xml")
STATE = str(REPO / "artifacts/site_i70/twin/state_t0_site.xml")
HORIZON = 300.0
SEEDS = [11, 12, 13]
VISIBLE_M = 150.0


def run_branch(job):
    branch, seed, outdir, cam, vsp, period = job
    import libsumo as t
    sm = cam["site_model"]
    entry, eb, exit_e = sm["edge_entry"], sm["edge_camera"], sm["edge_exit"]
    t.start(["sumo", "-n", NET, "--no-step-log", "--no-warnings",
             "--seed", str(seed), "--save-state.rng",
             "--time-to-teleport", "600"])
    t.simulation.loadState(STATE)
    t0 = t.simulation.getTime()
    if vsp and vsp < 12.0:
        t.edge.setMaxSpeed(exit_e, max(vsp, 2.0))   # same boundary as twin
    if branch in ("A1_vsl", "A3_vsl_gating"):
        t.edge.setMaxSpeed(entry, 8.0)              # harmonization
    gate = branch in ("A2_gating", "A3_vsl_gating")
    slow_vs = hold_s = 0.0
    tele = discharges = 0
    seen = set()
    nid = 90000
    # analytic vehicle-conserving metering: release[i] = max(sched, prev+hw)
    sched = [t0 + i * period for i in range(int(HORIZON / period) + 2)]
    rel = []
    prev = t0 - period
    for st_i in sched:
        hw = period
        if gate:
            hw = period * 2.0 if (st_i - t0) < 120.0 else period * 0.7
        r = max(st_i, prev + hw)
        rel.append(r)
        prev = r
    hold_s = round(sum(r - st_i for r, st_i in zip(rel, sched)), 1)
    qi = 0
    while t.simulation.getTime() < t0 + HORIZON:
        t.simulationStep()
        now = t.simulation.getTime()
        while qi < len(rel) and rel[qi] <= now:
            try:
                t.vehicle.add(f"c{nid}", "eb", typeID="site_veh",
                              departSpeed="max", departLane="free")
                nid += 1
            except Exception:                       # noqa: BLE001
                pass
            qi += 1
        tele += t.simulation.getEndingTeleportNumber()
        for v in t.edge.getLastStepVehicleIDs(eb):
            p = t.vehicle.getLanePosition(v)
            if p <= VISIBLE_M:
                sp = t.vehicle.getSpeed(v)
                slow_vs += max(0.0, 1.0 - sp / 25.0)   # veh-s of time loss
            if p > 140.0 and v not in seen:
                seen.add(v)
                discharges += 1
    t.close()
    return {"branch": branch, "seed": seed,
            "delay_veh_s_in_view": round(slow_vs, 1),
            "upstream_hold_veh_s": round(hold_s, 1),
            "objective": round(slow_vs + hold_s, 1),
            "discharged": discharges, "teleports": tele}


def main() -> None:
    twin = json.loads((REPO / "artifacts/gates/REAL_SITE_TWIN_PASS.json")
                      .read_text())
    cam = json.loads((REPO / "configs/cameras/registry.json").read_text()
                     )["cameras"]["070E28355CAM1RP2"]
    vsp = twin["observed_A"]["speed_m_s"]
    # arrival period from the twin's conservation inflow
    st = json.loads((REPO / "artifacts/site_i70/perception/traffic_state.json"
                     ).read_text())
    dur = len(st["windows"]) * 5.0
    period = dur / max(len(st["events"]["discharge"]), 1)
    out = REPO / "artifacts/site_i70/counterfactual"
    out.mkdir(parents=True, exist_ok=True)
    branches = ["A0_nothing", "A1_vsl", "A2_gating", "A3_vsl_gating"]
    jobs = [(b, s, str(out), cam, vsp, period) for b in branches
            for s in SEEDS]
    wall = time.time()
    with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count() - 1)) as p:
        rows = p.map(run_branch, jobs)
    agg = {}
    for r in rows:
        agg.setdefault(r["branch"], []).append(r)
    summ = {b: {k: round(statistics.mean(x[k] for x in v), 1)
                for k in ("delay_veh_s_in_view", "upstream_hold_veh_s",
                          "objective", "discharged", "teleports")}
            for b, v in agg.items()}
    a0 = summ["A0_nothing"]
    verdicts = {}
    for b, d in summ.items():
        if b == "A0_nothing":
            continue
        per = [(x["objective"], y["objective"]) for x, y in
               zip(sorted(agg[b], key=lambda r: r["seed"]),
                   sorted(agg["A0_nothing"], key=lambda r: r["seed"]))]
        wins = sum(1 for o, o0 in per if o < o0)
        g = {"objective_improves": d["objective"] < a0["objective"],
             "throughput_kept": d["discharged"] >= a0["discharged"] * 0.98,
             "no_teleports": d["teleports"] == 0,
             "seed_wins": f"{wins}/{len(per)}"}
        verdicts[b] = {"guards": g,
                       "label": "ACCEPTED" if g["objective_improves"]
                       and g["throughput_kept"] and g["no_teleports"]
                       and wins >= 2 else "REJECTED"}
    acc = [b for b, v in verdicts.items() if v["label"] == "ACCEPTED"]
    best = min(acc, key=lambda b: summ[b]["objective"]) if acc else None
    result = {"gate": "SITE_BEFORE_AFTER",
              "site": twin["site"], "state": STATE, "seeds": SEEDS,
              "horizon_s": HORIZON, "summary": summ, "verdicts": verdicts,
              "decision": best or "NO_SAFE_INTERVENTION_AT_THIS_SITE_STATE",
              "objective": "time-loss veh-s in view (1 - v/vfree) + upstream hold veh-s "
                           "(held vehicles' delay counted honestly)",
              "wall_s": round(time.time() - wall, 1)}
    (REPO / "artifacts/gates/SITE_BEFORE_AFTER.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
