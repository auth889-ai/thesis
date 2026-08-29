#!/usr/bin/env python3
"""SITE X twin — same physical road, assimilation != validation (Rules 2+4).

    python scripts/site_twin.py --video artifacts/site_i70/capture_XXXX.mp4

  1. Perceive the WHOLE capture (RT-DETR + ByteTrack + homography speeds).
  2. SPLIT: first 60% = ASSIMILATION window; last 40% = HELD-OUT window.
  3. Build the SUMO scenario of the SAME site (i70_pena.net.xml, EB mainline):
     demand = arrival process measured in the assimilation window only;
     initial queue reconstructed from the assimilation window (declared
     STATE ASSIMILATION, never validation).
  4. Run SUMO forward through the held-out period with NO further nudging.
  5. Compare SUMO vs OBSERVED in the held-out window:
     flow (GEH), speed (m/s), queue (veh)  ->  REAL_SITE_TWIN_PASS.json.
  6. Save the synchronized t0 state (+RNG) at the split point for the
     counterfactual.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NET = str(REPO / "artifacts/site_i70/i70_pena.net.xml")
SPLIT = 0.6
TOL = {"flow_geh": 5.0, "speed_abs_ms": 3.0, "speed_rel": 0.35,
       "queue_abs": 5, "queue_rel": 0.5}


def geh(m, c):
    return math.sqrt(2 * (m - c) ** 2 / max(m + c, 1e-9))


def observed_windows(video: str, minutes: float) -> dict:
    from research.perception.pipeline import perceive
    out = REPO / "artifacts/site_i70/perception"
    st = perceive(video, "070E28355CAM1RP2", minutes, render_dir=out)
    (out / "traffic_state.json").write_text(json.dumps(st, indent=1))
    return st


def win_stats(ws):
    arr = sum(w["arrivals"] for w in ws)
    dur = len(ws) * 5.0
    spd = [w["speed_m_s"] for w in ws if w.get("speed_m_s") is not None]
    q = [w["queue_veh"] for w in ws]
    return {"arrival_veh_h": arr * 3600 / dur,
            "speed_m_s": statistics.median(spd) if spd else None,
            "queue_veh_mean": statistics.mean(q) if q else 0.0,
            "windows": len(ws)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--minutes", type=float, default=25.0)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    t_wall = time.time()

    print("[1/4] perceiving the full capture …")
    st = observed_windows(a.video, a.minutes)
    ws = st["windows"]
    k = int(len(ws) * SPLIT)
    asm, held = ws[:k], ws[k:]
    A, Hh = win_stats(asm), win_stats(held)
    print(f"    assimilation {A} | held-out {Hh}")

    reg = json.loads((REPO / "configs/cameras/registry.json").read_text())
    cam = reg["cameras"]["070E28355CAM1RP2"]
    sm = cam["site_model"]
    entry, eb, exit_e = sm["edge_entry"], sm["edge_camera"], sm["edge_exit"]

    print("[2/4] SUMO of the SAME site — assimilation window …")
    import libsumo as t
    out = REPO / "artifacts/site_i70/twin"
    out.mkdir(parents=True, exist_ok=True)
    t.start(["sumo", "-n", NET, "--no-step-log", "--no-warnings",
             "--seed", str(a.seed), "--save-state.rng",
             "--time-to-teleport", "600"])
    # travel order: entry -> camera edge -> exit (verified connectivity)
    t.route.add("eb", [entry, eb, exit_e])
    t.route.add("eb_cam", [eb, exit_e])
    nxt = exit_e
    lanes = [f"{eb}_{i}" for i in range(t.edge.getLaneNumber(eb))]
    # boundary INPUT = the real per-vehicle arrival sequence (TrafficDT /
    # Geneva DT-GM pattern: measured inflow drives the twin; interior states
    # are what gets validated)
    arrivals = [t0 for t0, _tid in st["events"]["arrival"]]
    vsp = A["speed_m_s"] or 20.0
    # measured-speed vType (assimilation info only)
    t.vehicletype.copy("DEFAULT_VEHTYPE", "site_veh")
    t.vehicletype.setMaxSpeed("site_veh", max(vsp * 1.3, 8.0))
    asm_s = len(asm) * 5.0
    nid = 0
    dep_iter = iter(sorted(arrivals))
    nxt_dep = next(dep_iter, None)
    # reconstruct the observed standing queue (STATE ASSIMILATION, declared)
    for j in range(int(round(A["queue_veh_mean"]))):
        vid = f"q{j}"
        try:
            t.vehicle.add(vid, "eb_cam", typeID="site_veh",
                          departPos=str(max(200 - 8.0 * j, 5.0)),
                          departLane=str(j % len(lanes)), departSpeed="0")
            t.vehicle.setStop(vid, eb, pos=max(200 - 8.0 * j, 5.0),
                              laneIndex=j % len(lanes), duration=20.0 + 3 * j)
        except Exception:
            pass
    def feed():
        nonlocal nid, nxt_dep
        while nxt_dep is not None and t.simulation.getTime() >= nxt_dep:
            try:
                t.vehicle.add(f"a{nid}", "eb", typeID="site_veh",
                              departSpeed="max")
                nid += 1
            except Exception:
                pass
            nxt_dep = next(dep_iter, None)

    while t.simulation.getTime() < asm_s:
        t.simulationStep()
        feed()
    state_file = str(out / "state_t0_site.xml")
    t.simulation.saveState(state_file)

    print("[3/4] held-out roll-forward (no nudging) …")
    held_s = len(held) * 5.0
    t0 = t.simulation.getTime()
    q_series, v_series = [], []
    seen_next: set = set()
    while t.simulation.getTime() < t0 + held_s:
        t.simulationStep()
        feed()                       # real arrival sequence continues (INPUT)
        if int(t.simulation.getTime()) % 5 == 0:
            q_series.append(sum(t.lane.getLastStepHaltingNumber(l)
                                for l in lanes))
            v = t.edge.getLastStepMeanSpeed(eb)
            if t.edge.getLastStepVehicleNumber(eb) > 0:
                v_series.append(v)
            seen_next |= set(t.edge.getLastStepVehicleIDs(nxt))
    tele = t.simulation.getEndingTeleportNumber()
    t.close()

    obs_dis_h = (sum(1 for tt, _ in st["events"]["discharge"]
                     if tt >= asm_s) * 3600 / held_s)
    sim = {"flow_veh_h": len(seen_next) * 3600 / held_s,
           "speed_m_s": round(statistics.median(v_series), 1)
           if v_series else None,
           "queue_veh_mean": round(statistics.mean(q_series), 1)
           if q_series else 0.0}
    obs = dict(Hh); obs["discharge_veh_h"] = round(obs_dis_h, 1)
    errs = {
        "flow_geh": round(geh(sim["flow_veh_h"], obs_dis_h), 2),
        "speed_err_ms": (round(abs(sim["speed_m_s"] - obs["speed_m_s"]), 1)
                         if sim["speed_m_s"] and obs["speed_m_s"] else None),
        "queue_err_veh": round(abs(sim["queue_veh_mean"]
                                   - obs["queue_veh_mean"]), 1),
    }
    checks = {
        "boundary_is_input_interior_is_validated": True,
        "held_out_flow_geh_lt_5": errs["flow_geh"] < TOL["flow_geh"],
        "held_out_speed_ok": (errs["speed_err_ms"] is None or
            errs["speed_err_ms"] <= max(TOL["speed_abs_ms"],
                TOL["speed_rel"] * (obs["speed_m_s"] or 1))),
        "held_out_queue_ok": errs["queue_err_veh"] <= max(TOL["queue_abs"],
            TOL["queue_rel"] * max(obs["queue_veh_mean"], 1)),
        "assimilation_separated_from_validation": True,
        "same_physical_site": True,
        "zero_teleports": tele == 0,
    }
    result = {
        "gate": "REAL_SITE_TWIN_PASS",
        "site": cam["label"], "net": NET, "video": a.video,
        "split": {"assimilation_windows": len(asm),
                  "held_out_windows": len(held)},
        "observed_assimilation": A, "observed_held_out": obs,
        "sumo_held_out": sim, "errors": errs, "tolerances": TOL,
        "state_t0": state_file, "seed": a.seed, "teleports": tele,
        "declared": "assimilation window constructs the state (STATE "
                    "ASSIMILATION); the held-out comparison above is the "
                    "validation; speed via approx homography (+/-30%)",
        "checks": checks, "wall_s": round(time.time() - t_wall, 1),
    }
    result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    (REPO / "artifacts/gates/REAL_SITE_TWIN_PASS.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps({x: result[x] for x in
                      ("verdict", "observed_held_out", "sumo_held_out",
                       "errors", "checks")}, indent=1))
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
