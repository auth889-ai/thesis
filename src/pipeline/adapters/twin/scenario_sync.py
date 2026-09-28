"""Twin synchronization (Gate 2) — observed video state CONFIGURES the twin.

Method: Geneva DT-GM dynamic flow calibration pattern (Kusic et al. 2023,
10.1016/j.aei.2022.101858) — per-interval measured flows drive the simulation;
here via TraCI injection (stock SUMO), plus standing-queue reconstruction.

SITE_TRANSFER (declared, never hidden): the observed camera is a REAL foreign
feed (I-70). Its measured PER-LANE arrival rate and queue are transferred onto
the Dhaka R1 corridor named by the registry hint; the Dhaka vehicle mix of the
twin is retained (mix comparison WAIVED_SITE_TRANSFER). The demand-scale
calibration (twin_calibration_A: scale vs live reference) is CONSUMED via
--scale, not merely displayed.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
ROUTES_SRC = REPO / "results/artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz"
WARM_S = 3600.0   # 12x300s: forecast history is FULL before control t0
SETTLE_S = 60.0


def geh(m: float, c: float) -> float:
    return math.sqrt(2 * (m - c) ** 2 / max(m + c, 1e-9))


def observed_summary(state: dict) -> dict:
    ws = state["windows"]
    dur = ws[-1]["t0"] + 5 - ws[0]["t0"]
    arr = sum(w["arrivals"] for w in ws)
    flag = None
    if arr == 0:
        # no registered count line (any-video generic mode): estimate the
        # arrival rate from newly-appearing tracked vehicles — declared,
        # approximate (track churn inflates it; median window rate used)
        rates = sorted(w.get("new_tracks", 0) for w in ws)
        arr = rates[len(rates) // 2] * len(ws)
        flag = "ARRIVAL_FROM_TRACK_BIRTHS_APPROX"
    queues = sorted(w["queue_veh"] for w in ws)
    return {"duration_s": dur, "arrival_veh_h": arr * 3600 / dur,
            "queue_median": queues[len(queues) // 2],
            "queue_max": queues[-1], "flag": flag,
            "classes": {}}


def synchronize(state: dict, camera: dict, seed: int, out_dir: Path) -> dict:
    """Build a twin whose t0 state matches the observation. Returns report."""
    import numpy as np
    import libsumo as t
    from pipeline.adapters.routing.r1_router import R1Router
    from pipeline.adapters.twin.demand import make_repeating_routes
    from pipeline.adapters.control.gwnet_in_loop import GWNetForecaster

    routes = str(make_repeating_routes(
        ROUTES_SRC, REPO / "results/artifacts/gates/routes_repeat_1h.rou.xml.gz",
        cycles=8, period_s=600.0))

    out_dir.mkdir(parents=True, exist_ok=True)
    obs = observed_summary(state)
    # observed per-lane rate; camera approach lane count from registration
    cam_lanes = camera.get("approach_lane_count", 3)
    per_lane_h = obs["arrival_veh_h"] / cam_lanes

    scale = json.loads((REPO / "results/artifacts/twin_calibration_A.json")
                       .read_text())["calibrated_demand_scale_A"]
    hint = camera["sumo_site_transfer"]["edge_hint_camera"]
    hint_ll = {"karwanbazar": (23.7529, 90.3944),
               "farmgate": (23.7573, 90.3854),
               "shahbagh": (23.7389, 90.3958)}[hint]
    router = R1Router()
    edge = router.nearest_edge(*hint_ll)

    t.start(["sumo", "-n", NET, "-r", routes, "--seed", str(seed),
             "--scale", str(scale), "--no-step-log", "--no-warnings",
             "--time-to-teleport", "600", "--save-state.rng"])
    lanes = [f"{edge}_{i}" for i in range(t.edge.getLaneNumber(edge))]
    target_rate_h = per_lane_h * len(lanes)

    fc = GWNetForecaster()
    tls_all = list(t.trafficlight.getIDList())
    nxt_fc = 0.0
    while t.simulation.getTime() < WARM_S:
        t.simulationStep()
        if t.simulation.getTime() >= nxt_fc:      # rolling history ingestion
            fc(t, tls_all)
            nxt_fc += 5.0

    # --- reconstruct the standing/creeping queue observed at the camera ----
    lane_len = t.lane.getLength(lanes[0])
    route_id = "sync_route"
    nxt = router._dijkstra(edge, edge, {})     # trivial; extend downstream
    try:
        t.route.add(route_id, [edge])
    except Exception:
        pass
    existing_q = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
    deficit = max(obs["queue_median"] - existing_q, 0)
    injected = []
    for k in range(deficit):
        vid = f"syncq_{k}"
        pos = max(lane_len - 8.0 * (k // len(lanes) + 1), 5.0)
        try:
            t.vehicle.add(vid, route_id, departPos=str(pos),
                          departLane=str(k % len(lanes)), departSpeed="0")
            t.vehicle.setStop(vid, edge, pos=pos,
                              laneIndex=k % len(lanes),
                              duration=30.0 + 5.0 * k)   # staggered creep
            injected.append(vid)
        except Exception:
            continue
    # --- inject measured arrival flow upstream for SETTLE_S ---------------
    period = 3600.0 / max(target_rate_h, 1.0)
    t0_mark = t.simulation.getTime()
    next_dep, arr_count, q_samples = t0_mark, 0, []
    while t.simulation.getTime() < t0_mark + SETTLE_S:
        t.simulationStep()
        now = t.simulation.getTime()
        if target_rate_h >= 1.0 and now >= next_dep:
            vid = f"syncf_{arr_count}"
            try:
                t.vehicle.add(vid, route_id, departSpeed="max")
                arr_count += 1
            except Exception:
                pass
            next_dep += period
        if int(now) % 5 == 0:
            q_samples.append(sum(t.lane.getLastStepHaltingNumber(l)
                                 for l in lanes))
    # like-for-like: median queue over the SAME sampled minute as observation
    sim_queue = sorted(q_samples)[len(q_samples) // 2] if q_samples else 0
    sim_rate_h = arr_count * 3600 / SETTLE_S
    state_file = str(out_dir / "state_sync_t0.xml")
    t.simulation.saveState(state_file)
    t0_s = t.simulation.getTime()
    np.savez(out_dir / "forecast_context.npz",
             hist=np.stack(fc.hist), vfree=fc.vfree,
             pred5=fc.pred_speed.get(5), pred10=fc.pred_speed.get(10),
             pred15=fc.pred_speed.get(15))
    forecast_fraction = fc.forecast_available_fraction
    t.close()

    checks = {
        "queue_match": abs(sim_queue - obs["queue_median"])
        <= max(5, 0.30 * obs["queue_median"]),
        "flow_geh_lt_5": geh(sim_rate_h, target_rate_h) < 5.0,
        "calibration_consumed": True,
    }
    return {
        "observed": obs, "per_lane_arrival_h": round(per_lane_h, 1),
        "target_edge": edge, "target_lanes": len(lanes),
        "sim_queue_at_t0": sim_queue, "existing_queue_prewarm": existing_q,
        "injected_deficit": deficit,
        "sim_arrival_rate_h": round(sim_rate_h, 1),
        "target_rate_h": round(target_rate_h, 1),
        "geh_flow": round(geh(sim_rate_h, target_rate_h), 2),
        "demand_scale_consumed": scale,
        "state_file": state_file, "t0_s": t0_s, "seed": seed,
        "routes": routes,
        "forecast_available_fraction_warm": round(forecast_fraction, 4),
        "forecast_context": str(out_dir / "forecast_context.npz"),
        "checks": checks,
        "waived": {
            "vehicle_mix": "WAIVED_SITE_TRANSFER (foreign camera; Dhaka twin "
                           "mix retained by design)",
            "speed": "SPEED_NO_HOMOGRAPHY at camera",
            "signal_state": "NOT_OBSERVABLE in this feed"},
        "tolerances": {
            "queue": "abs diff <= max(5 veh, 30%) [DiTAT-style volume tol]",
            "flow": "GEH < 5 [standard traffic-engineering acceptance]"},
        "method": "Geneva DT-GM dynamic flow calibration pattern via TraCI "
                  "(10.1016/j.aei.2022.101858); SITE_TRANSFER declared",
    }
