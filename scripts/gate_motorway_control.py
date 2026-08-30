#!/usr/bin/env python3
"""GATE: MOTORWAY_CONTROL — paper-faithful freeway control at SITE X.

PAPER (primary): Papageorgiou, Hadj-Salem, Blosseville (1991), ALINEA:
  r(k) = r(k-1) + K_R * (O_HAT - o_out(k))
  o_out = downstream occupancy [%] measured every T on the merge-downstream
  edge (the camera edge, where the real video measured the jam).
  Parameters (paper): K_R = 70 veh/h per % occupancy; T = 40 s;
  set-point O_HAT = 21 %; bounds r in [240, 1800] veh/h.
VSL (integrated-control literature, Carlson/Hegyi): reactive step law —
  upstream mainline limit 25.0 -> 16.7 -> 11.1 m/s while o_out > O_HAT,
  recover when o_out < 0.8*O_HAT.  DEVIATION: reactive simplification of the
  optimal-control formulation (recorded).
DEVIATION 2: mainline/ramp demand split 85/15 declared (total inflow = the
  MEASURED conservation rate from the real video; separate ramp counts
  pending ramp zones).

T0 PROVENANCE: real I-70 rush video -> perception -> conservation inflow ->
  twin validated on HELD-OUT window (REAL_SITE_TWIN_PASS: density 14.8%,
  speed 0.1 m/s) -> the same construction replayed with the physical
  mainline+ramp split, warm 60 s -> saved t0 (this script, phase 1) -> all
  branches load THAT file. Validation is re-checked here after the split.

Actions: ramp stop-and-release + edge speed limits only.
No moveTo / teleport / delete. Ramp waiting counts in the objective.
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
MAIN_IN, RAMP, MERGE = "118357029", "16961629", "118357136"
CAM, EXIT = "1341991149", "1340464367"
SITE_EDGES = [MAIN_IN, RAMP, MERGE, CAM]
SPLIT_MAIN = 0.85
WARM, ASM, HORIZON = 240.0, 35.0, 300.0   # warm > 145s upstream transit
SEEDS = [11, 12, 13]
# ALINEA
KR, T_C, O_HAT, R_MIN, R_MAX = 70.0, 40.0, 21.0, 240.0, 1800.0
VSL_STEPS = [25.0, 16.7, 11.1]
STATE = str(REPO / "artifacts/site_i70/twin/state_t0_motorway.xml")


def measured_inflow():
    st = json.loads((REPO / "artifacts/site_i70/perception/traffic_state.json"
                     ).read_text())
    dur = len(st["windows"]) * 5.0
    rate = len(st["events"]["discharge"]) * 3600.0 / dur
    vsp = statistics.median([w["speed_m_s"] for w in st["windows"]
                             if w.get("speed_m_s")])
    obs_b = st["windows"][int(len(st["windows"]) * 0.6):]
    return rate, vsp, obs_b


def setup(t, vsp, seed):
    t.route.add("r_main", [MAIN_IN, MERGE, CAM, EXIT])
    t.route.add("r_ramp", [RAMP, MERGE, CAM, EXIT])
    t.vehicletype.copy("DEFAULT_VEHTYPE", "site_veh")
    t.vehicletype.setMaxSpeed("site_veh", max(vsp * 1.15, 4.0))
    t.edge.setMaxSpeed(EXIT, max(vsp, 2.0))       # measured downstream creep


def feeder(rate):
    pm = 3600.0 / (rate * SPLIT_MAIN)
    pr = 3600.0 / (rate * (1 - SPLIT_MAIN))
    return pm, pr


def build_t0(rate, vsp, obs_b, seed):
    import libsumo as t
    t.start(["sumo", "-n", NET, "--no-step-log", "--no-warnings",
             "--seed", str(seed), "--save-state.rng",
             "--time-to-teleport", "600"])
    setup(t, vsp, seed)
    pm, pr = feeder(rate)
    nm = nr = 0
    dens_b, spd_b = [], []
    total = WARM + ASM + 60.0                     # includes held-out check
    while t.simulation.getTime() < total:
        t.simulationStep()
        now = t.simulation.getTime()
        while nm * pm <= now:
            try:
                t.vehicle.add(f"m{nm}", "r_main", typeID="site_veh",
                              departSpeed="max", departLane="free")
            except Exception:                      # noqa: BLE001
                pass
            nm += 1
        while nr * pr <= now:
            try:
                t.vehicle.add(f"r{nr}", "r_ramp", typeID="site_veh",
                              departSpeed="max", departLane="free")
            except Exception:                      # noqa: BLE001
                pass
            nr += 1
        if abs(now - (WARM + ASM)) < 0.5:
            t.simulation.saveState(STATE)
        if now > WARM + ASM and int(now) % 5 == 0:  # quick held-out re-check
            nv, vs = 0, []
            for v in t.edge.getLastStepVehicleIDs(CAM):
                if t.vehicle.getLanePosition(v) <= 150:
                    nv += 1
                    vs.append(t.vehicle.getSpeed(v))
            dens_b.append(nv)
            if vs:
                spd_b.append(statistics.mean(vs))
    t.close()
    ob_d = statistics.mean(w["tracked_mean"] for w in obs_b)
    ob_v = statistics.median([w["speed_m_s"] for w in obs_b
                              if w.get("speed_m_s")])
    sim_d = statistics.mean(dens_b) if dens_b else 0
    sim_v = statistics.mean(spd_b) if spd_b else 0
    return {"obs_density": round(ob_d, 1), "sim_density": round(sim_d, 1),
            "density_rel_err": round(abs(sim_d - ob_d) / max(ob_d, 1), 3),
            "obs_speed": ob_v, "sim_speed": round(sim_v, 1),
            "speed_err_ms": round(abs(sim_v - ob_v), 1)}


def run_branch(job):
    branch, seed, rate, vsp = job
    import libsumo as t
    t.start(["sumo", "-n", NET, "--no-step-log", "--no-warnings",
             "--seed", str(seed), "--save-state.rng",
             "--time-to-teleport", "600"])
    setup(t, vsp, seed)
    t.simulation.loadState(STATE)
    t0 = t.simulation.getTime()
    pm, pr = feeder(rate)
    use_alinea = branch in ("A1_alinea", "A3_integrated")
    use_vsl = branch in ("A2_vsl", "A3_integrated")
    r_k = 900.0                                   # initial metering rate
    vsl_i = 0
    ramp_len = t.lane.getLength(f"{RAMP}_0")
    held, released = [], set()
    nm = int(t0 / pm) + 1
    nr = int(t0 / pr) + 1
    next_ctrl = t0 + T_C
    next_rel = t0
    m = {k: 0.0 for k in ("time_loss", "ttt", "stopped_vs", "ramp_q_peak",
                          "spill", "tele")}
    seen_mid = set()
    occ_hist = []
    while t.simulation.getTime() < t0 + HORIZON:
        t.simulationStep()
        now = t.simulation.getTime()
        while nm * pm <= now:
            try:
                t.vehicle.add(f"m{nm}", "r_main", typeID="site_veh",
                              departSpeed="max", departLane="free")
            except Exception:                      # noqa: BLE001
                pass
            nm += 1
        while nr * pr <= now:
            vid = f"r{nr}"
            try:
                t.vehicle.add(vid, "r_ramp", typeID="site_veh",
                              departSpeed="max", departLane="free")
                if use_alinea:
                    t.vehicle.setStop(vid, RAMP, pos=ramp_len - 8.0,
                                      laneIndex=nr % 2, duration=1e5)
                    held.append(vid)
            except Exception:                      # noqa: BLE001
                pass
            nr += 1
        o_out = t.edge.getLastStepOccupancy(CAM) * 100.0  # ->[%] (TraCI returns fraction)
        occ_hist.append(o_out)
        if now >= next_ctrl:
            next_ctrl += T_C
            if use_alinea:                          # ALINEA feedback law
                r_k = min(max(r_k + KR * (O_HAT - o_out), R_MIN), R_MAX)
            if use_vsl:                             # reactive VSL steps
                if o_out > O_HAT and vsl_i < 2:
                    vsl_i += 1
                elif o_out < 0.8 * O_HAT and vsl_i > 0:
                    vsl_i -= 1
                t.edge.setMaxSpeed(MAIN_IN, VSL_STEPS[vsl_i])
        if use_alinea and held and now >= next_rel:
            vid = held.pop(0)
            try:
                t.vehicle.resume(vid)
                released.add(vid)
            except Exception:                      # noqa: BLE001
                pass
            next_rel = now + 3600.0 / r_k
        m["tele"] += t.simulation.getEndingTeleportNumber()
        rq = 0
        for e in SITE_EDGES:
            vmax = t.lane.getMaxSpeed(f"{e}_0")
            for v in t.edge.getLastStepVehicleIDs(e):
                sp = t.vehicle.getSpeed(v)
                m["ttt"] += 1.0
                m["time_loss"] += max(0.0, 1.0 - sp / max(vmax, 0.1))
                if sp < 0.1:
                    m["stopped_vs"] += 1.0
                if e == RAMP:
                    rq += 1 if sp < 3.0 else 0
                    if sp < 0.1 and t.vehicle.getLanePosition(v) < 0.2 * ramp_len:
                        m["spill"] += 1.0
                if e == CAM and t.vehicle.getLanePosition(v) > 140 \
                        and v not in seen_mid:
                    seen_mid.add(v)
        m["ramp_q_peak"] = max(m["ramp_q_peak"], rq)
    cam_sp = t.edge.getLastStepMeanSpeed(CAM)
    cam_dens = len([v for v in t.edge.getLastStepVehicleIDs(CAM)
                    if t.vehicle.getLanePosition(v) <= 150])
    t.close()
    return {"branch": branch, "seed": seed,
            "total_time_loss_vs": round(m["time_loss"], 1),
            "total_travel_time_vs": round(m["ttt"], 1),
            "stopped_veh_s": round(m["stopped_vs"], 1),
            "mainline_speed_end": round(cam_sp, 1),
            "mainline_density_end": cam_dens,
            "ramp_queue_peak": int(m["ramp_q_peak"]),
            "throughput_midview": len(seen_mid),
            "spillback_veh_s": round(m["spill"], 1),
            "teleports": int(m["tele"]),
            "mean_occupancy_pct": round(statistics.mean(occ_hist), 1)}


def main() -> None:
    rate, vsp, obs_b = measured_inflow()
    print(f"[1/2] rebuild t0 with real merge (inflow {rate:.0f}/h, "
          f"split {SPLIT_MAIN:.0%}/{1-SPLIT_MAIN:.0%}) + re-validate …")
    val = build_t0(rate, vsp, obs_b, SEEDS[0])
    print("    re-validation:", val)
    if val["density_rel_err"] > 0.35 or val["speed_err_ms"] > 3.0:
        print("T0 REVALIDATION FAILED — refusing to run branches on an "
              "unvalidated state.")
        sys.exit(1)
    print("[2/2] A0/A1_ALINEA/A2_VSL/A3 from the SAME t0, paired seeds …")
    branches = ["A0_nothing", "A1_alinea", "A2_vsl", "A3_integrated"]
    jobs = [(b, s, rate, vsp) for b in branches for s in SEEDS]
    wall = time.time()
    with mp.get_context("spawn").Pool(min(len(jobs), mp.cpu_count() - 1)) as p:
        rows = p.map(run_branch, jobs)
    agg = {}
    for r in rows:
        agg.setdefault(r["branch"], []).append(r)
    keys = [k for k in rows[0] if k not in ("branch", "seed")]
    summ = {b: {k: round(statistics.mean(x[k] for x in v), 1) for k in keys}
            for b, v in agg.items()}
    a0 = summ["A0_nothing"]
    verd = {}
    for b in branches[1:]:
        per = list(zip(sorted(agg[b], key=lambda r: r["seed"]),
                       sorted(agg["A0_nothing"], key=lambda r: r["seed"])))
        wins = sum(1 for x, y in per
                   if x["total_time_loss_vs"] < y["total_time_loss_vs"])
        g = {"network_time_loss_improves":
             summ[b]["total_time_loss_vs"] < a0["total_time_loss_vs"],
             "throughput_kept": summ[b]["throughput_midview"]
             >= a0["throughput_midview"] * 0.98,
             "no_teleports": summ[b]["teleports"] == 0,
             "seed_wins": f"{wins}/{len(per)}"}
        verd[b] = {"guards": g, "label": "ACCEPTED"
                   if g["network_time_loss_improves"] and g["throughput_kept"]
                   and g["no_teleports"] and wins >= 2 else "REJECTED"}
    acc = [b for b in verd if verd[b]["label"] == "ACCEPTED"]
    best = (min(acc, key=lambda b: summ[b]["total_time_loss_vs"])
            if acc else None)
    result = {
        "gate": "MOTORWAY_CONTROL",
        "t0_provenance": "real I-70 rush video -> validated twin "
                         "(REAL_SITE_TWIN_PASS) -> same construction with "
                         "physical mainline+ramp split -> re-validated here "
                         f"-> {STATE}",
        "revalidation_after_split": val,
        "papers": {"ALINEA": "Papageorgiou et al. 1991 "
                             "(r(k)=r(k-1)+K_R*(O_hat-o_out))",
                   "VSL": "Carlson/Hegyi integrated motorway control "
                          "(reactive step simplification — deviation)"},
        "parameters": {"K_R_veh_h_per_pct": KR, "T_s": T_C,
                       "O_hat_pct": O_HAT, "r_bounds": [R_MIN, R_MAX],
                       "vsl_steps_ms": VSL_STEPS,
                       "demand_split_declared": SPLIT_MAIN},
        "seeds": SEEDS, "horizon_s": HORIZON,
        "summary": summ, "verdicts": verd,
        "decision": best or "NO_CONTROLLER_BEATS_A0_AT_THIS_STATE",
        "wall_s": round(time.time() - wall, 1),
    }
    (REPO / "artifacts/gates/MOTORWAY_CONTROL.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps(result["summary"], indent=1))
    print("verdicts:", {b: verd[b]["label"] for b in verd},
          "| decision:", result["decision"])


if __name__ == "__main__":
    main()
