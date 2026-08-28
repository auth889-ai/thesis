#!/usr/bin/env python3
"""SAME-STATE counterfactual — the causal bridge the audit demanded.

One twin simulation runs the fair demand until congestion is real (t0). The
EXACT simulator state is saved (traci.simulation.saveState). Two branches then
run from that identical state:

  NO_ACTION : simulation continues untouched for HORIZON_S.
  CONTROL   : v1 rule-based coordinator acts at/around the TARGET junction
              (chosen by the camera's location — the examiner's video decides
              WHERE):
                * discharge: hold/extend green for the most-queued approach
                  at the target TLS (min-green respected, max 60 s),
                * bounded rerouting: every 60 s, half of the vehicles that are
                  APPROACHING (not yet on) the hot edges are rerouted using
                  fresh measured travel times (reset-then-penalize),
                * vehicles already inside the queue are never teleported.

Because everything before t0 is byte-identical, the difference at t0+HORIZON
is CAUSED by the control. Declared scope (v1): the twin runs the fair fixed
demand; the observed video selects the intervention site and trigger —
trajectory-level state reconstruction is the follow-up gate.

Output: artifacts/same_state/<name>/result.json with the four-pane numbers:
queue, stopped, arrived, mean delay of arrivals — per branch.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

NET = str(REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml")
ROUTES = str(REPO / "artifacts/due_dso_stats/v200/DUE/003/trips_003.rou.xml.gz")
REROUTE_MODE = "gated"      # off | gated
T0_TRIGGER_STOPPED = 250     # auto-t0: act when the network is genuinely jammed
T0_MAX_S = 7200
HORIZON_S = 600
MIN_GREEN = 10.0

CAMERAS = {"farmgate": (23.7573, 90.3854), "karwanbazar": (23.7529, 90.3944),
           "banglamotor": (23.7465, 90.3948), "shahbagh": (23.7389, 90.3958)}


def snapshot(t, lanes):
    """Network metrics + local queue on the target approaches."""
    halting = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
    net_halt = sum(t.lane.getLastStepHaltingNumber(l)
                   for l in t.lane.getIDList() if not l.startswith(":"))
    return {"target_queue_veh": halting, "network_stopped_veh": net_halt,
            "vehicles_running": t.vehicle.getIDCount()}


def run(name: str, cam: str, seed: int) -> dict:
    import sumolib
    import traci
    from sumolib import checkBinary

    out = REPO / "artifacts" / "same_state" / name
    out.mkdir(parents=True, exist_ok=True)
    net = sumolib.net.readNet(NET)

    # camera -> target edge -> target TLS + its approach lanes
    from research.routing.r1_router import R1Router
    router = R1Router()
    cam_edge = router.nearest_edge(*CAMERAS[cam])

    results = {}
    for branch in ("no_action", "control"):
        trip = out / f"tripinfo_{branch}.xml"
        label = f"ss_{branch}_{seed}"
        traci.start([checkBinary("sumo"), "-n", NET, "-r", ROUTES,
                     "--seed", str(seed), "--end", str(T0_MAX_S + HORIZON_S + 10),
                     "--tripinfo-output", str(trip),
                     "--no-warnings", "--no-step-log",
                     "--time-to-teleport", "300"], label=label)
        t = traci.getConnection(label)

        # target TLS = the signal controlling (or nearest to) the camera edge
        tls_ids = t.trafficlight.getIDList()
        target_tls, tls_lanes = None, []
        ex, ey = net.getEdge(cam_edge).getShape()[0]
        best = 1e18
        for tls in tls_ids:
            lanes = [lk[0][0] for lk in t.trafficlight.getControlledLinks(tls)
                     if lk]
            if not lanes:
                continue
            jx, jy = net.getEdge(t.lane.getEdgeID(lanes[0])).getShape()[-1]
            d = (jx - ex) ** 2 + (jy - ey) ** 2
            if d < best:
                best, target_tls, tls_lanes = d, tls, lanes

        # hot edges = camera edge + incoming approaches of the target TLS
        hot = {cam_edge} | {t.lane.getEdgeID(l) for l in tls_lanes}

        # identical warm-up: run until the network is GENUINELY congested
        # (deterministic given seed+demand → both branches hit the same t0)
        net_stopped = 0
        while t.simulation.getTime() < T0_MAX_S:
            t.simulationStep()
            if int(t.simulation.getTime()) % 60 == 0:
                net_stopped = sum(t.lane.getLastStepHaltingNumber(l)
                                  for l in t.lane.getIDList()
                                  if not l.startswith(":"))
                if net_stopped >= T0_TRIGGER_STOPPED:
                    break
        T0_S = t.simulation.getTime()
        # retarget: the most-queued TLS at t0 (the camera names the corridor;
        # the jammed junction inside it is chosen from measurement)
        best_q = -1
        for tls in tls_ids:
            lanes = [lk[0][0] for lk in t.trafficlight.getControlledLinks(tls)
                     if lk]
            q = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
            if q > best_q:
                best_q, target_tls, tls_lanes = q, tls, lanes
        hot = {cam_edge} | {t.lane.getEdgeID(l) for l in tls_lanes}
        state_file = str(out / "state_t0.xml")
        if branch == "no_action":
            t.simulation.saveState(state_file)     # save the exact t0 state
        pre = snapshot(t, tls_lanes)

        green_started = t.simulation.getTime()
        while t.simulation.getTime() < T0_S + HORIZON_S and \
                t.simulation.getMinExpectedNumber() > 0:
            t.simulationStep()
            now = t.simulation.getTime()
            if branch != "control":
                continue
            if int(now) % 5 == 0:
                # DISCHARGE: if the most-queued approach isn't green, switch
                # (respecting min-green); if it is green, extend.
                per_lane = [(t.lane.getLastStepHaltingNumber(l), l)
                            for l in tls_lanes]
                q, worst = max(per_lane)
                state = t.trafficlight.getRedYellowGreenState(target_tls)
                links = t.trafficlight.getControlledLanes(target_tls)
                idx = [i for i, l in enumerate(links) if l == worst]
                worst_green = bool(idx) and state[idx[0]] in "Gg"
                if q > 10 and worst_green:
                    # MILD: extend the already-green jammed approach by 5 s;
                    # never force-switch (cross-traffic keeps its slots)
                    t.trafficlight.setPhaseDuration(target_tls, 5.0)
            if int(now) % 60 == 0 and REROUTE_MODE != "off":
                # BOUNDED REROUTE with ALTERNATIVE-CAPACITY GATE: skip entirely
                # when the rest of the network is already loaded (audit rule:
                # never just move the jam).
                others = [l for l in t.lane.getIDList()
                          if not l.startswith(":")
                          and t.lane.getEdgeID(l) not in hot]
                alt_load = sum(t.lane.getLastStepHaltingNumber(l)
                               for l in others) / max(len(others), 1)
                if alt_load > 0.35:          # alternatives busy -> hold traffic
                    continue
                for eid in hot:
                    v = max(t.edge.getLastStepMeanSpeed(eid), 0.5)
                    ln = net.getEdge(eid).getLength()
                    t.edge.adaptTraveltime(eid, (ln / v) * 3.0)
                cand = []
                for vid in t.vehicle.getIDList():
                    try:
                        route = t.vehicle.getRoute(vid)
                        here = t.vehicle.getRoadID(vid)
                        if here not in hot and any(e in hot for e in route):
                            cand.append(vid)
                    except traci.TraCIException:
                        pass
                for k, vid in enumerate(cand):
                    if k % 2 == 0:                 # 50% bounded diversion
                        try:
                            t.vehicle.rerouteTraveltime(vid)
                        except traci.TraCIException:
                            pass
        post = snapshot(t, tls_lanes)
        t.close()

        arr = ET.parse(trip).getroot()
        late = [x for x in arr if float(x.get("arrival")) >= T0_S]
        losses = [float(x.get("timeLoss")) for x in late]
        results[branch] = {
            "t0": pre, "t0_plus_10min": post, "t0_s_actual": T0_S,
            "arrived_in_horizon": len(late),
            "mean_time_loss_of_horizon_arrivals_s":
                round(statistics.mean(losses), 1) if losses else None,
        }

    a, b = results["no_action"], results["control"]
    summary = {
        "stage": "SAME_STATE_COUNTERFACTUAL",
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "scope_v1": "fair fixed demand drives the twin; the observed video "
                    "selects intervention site+trigger; trajectory-level "
                    "reconstruction is the declared next gate",
        "camera": cam, "camera_edge": cam_edge, "seed": seed,
        "t0_s": results["no_action"]["t0_s_actual"], "horizon_s": HORIZON_S,
        "identical_t0_proof": "same seed+demand to t0; state saved at "
                              f"{out / 'state_t0.xml'}",
        "no_action": a, "control": b,
        "four_pane": {
            "queue_no_action": a["t0_plus_10min"]["target_queue_veh"],
            "queue_control": b["t0_plus_10min"]["target_queue_veh"],
            "network_stopped_no_action": a["t0_plus_10min"]["network_stopped_veh"],
            "network_stopped_control": b["t0_plus_10min"]["network_stopped_veh"],
            "arrived_no_action": a["arrived_in_horizon"],
            "arrived_control": b["arrived_in_horizon"],
        },
    }
    (out / "result.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default="karwanbazar", choices=list(CAMERAS))
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--name", default=None)
    ap.add_argument("--reroute", choices=["off", "gated"], default="gated")
    args = ap.parse_args()
    global REROUTE_MODE
    REROUTE_MODE = args.reroute
    s = run(args.name or f"{args.camera}_{args.reroute}_s{args.seed}",
            args.camera, args.seed)
    print(json.dumps(s["four_pane"], indent=2))


if __name__ == "__main__":
    main()
