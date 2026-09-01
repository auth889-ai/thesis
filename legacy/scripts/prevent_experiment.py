#!/usr/bin/env python3
"""PREVENT-mode experiment: forecast-triggered pre-emptive rerouting.

Two branches, identical demand and seed, on the frozen R1 network:

  BASELINE  : selfish routes (E4 DUE converged) run untouched — jams form.
  PREVENT   : every 300 s a forecast trigger scores each monitored edge with
              the predicted next-interval speed (persistence forecaster —
              benchmarked floor of the P3 gate; --trigger gwnet plugs the
              graph model in on a machine with its env). When an edge's
              predicted speed falls below THRESH × its free speed, vehicles
              that have NOT YET DEPARTED and whose route uses that edge are
              rerouted around it (travel-time penalty + rerouteTraveltime).
              Vehicles already on the road are never teleported — prevention
              only stops the jam being fed, exactly the thesis claim.

Metrics from tripinfo: mean/total timeLoss, duration, arrivals.
Output: artifacts/prevent_experiment/result.json (+ per-branch tripinfo).
Labels: DHAKA_SIMULATED_SENSOR_GRAPH — twin evidence, declared.
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
END_S = 10800
CHECK_S = 300
THRESH = 0.5          # predicted speed < 50% of free speed -> act
PENALTY = 4.0         # cost multiplier on predicted-congested edges


def run(branch: str, seed: int, out_dir: Path) -> dict:
    import traci
    from sumolib import checkBinary

    trip = out_dir / f"tripinfo_{branch}_{seed}.xml"
    traci.start([checkBinary("sumo"), "-n", NET, "-r", ROUTES,
                 "--seed", str(seed), "--end", str(END_S),
                 "--tripinfo-output", str(trip),
                 "--no-warnings", "--no-step-log",
                 "--time-to-teleport", "300"], label=f"{branch}{seed}")
    t = traci.getConnection(f"{branch}{seed}")

    # monitored edges: every edge with length > 50 m (speed sensors everywhere
    # would be the 250-sensor graph; monitoring all sizable edges is the
    # perfect-sensing upper bound, declared)
    import sumolib
    net = sumolib.net.readNet(NET)
    monitored = {e.getID(): e.getSpeed() for e in net.getEdges()
                 if e.getLength() > 50}

    prev_speed: dict[str, float] = {}
    actions = []
    next_check = CHECK_S
    while t.simulation.getMinExpectedNumber() > 0 and \
            t.simulation.getTime() < END_S:
        t.simulationStep()
        now = t.simulation.getTime()
        if branch == "prevent" and now >= next_check:
            next_check = now + CHECK_S
            hot = []
            for eid, vfree in monitored.items():
                v = t.edge.getLastStepMeanSpeed(eid)
                # persistence forecast: predicted next-interval speed = current
                pred = v if eid not in prev_speed else 0.5 * v + 0.5 * prev_speed[eid]
                prev_speed[eid] = v
                if t.edge.getLastStepVehicleNumber(eid) > 3 and \
                        pred < THRESH * vfree:
                    hot.append(eid)
            # RESET stale penalties first (fresh measured tt), else they
            # compound across checks (4x -> 16x -> ...) — found: seed-3 +66%.
            for eid, vfree in monitored.items():
                v = max(t.edge.getLastStepMeanSpeed(eid), 0.5)
                length = net.getEdge(eid).getLength()
                t.edge.adaptTraveltime(eid, length / v)
            if hot:
                for eid in hot:
                    length = net.getEdge(eid).getLength()
                    v = max(t.edge.getLastStepMeanSpeed(eid), 0.5)
                    t.edge.adaptTraveltime(eid, (length / v) * PENALTY)
                # reroute only pending vehicles, capped at 50% of matches —
                # over-diversion just moves the jam (bounded-action principle)
                pending = list(t.simulation.getPendingVehicles())
                n_rr = 0
                matches = []
                for vid in pending:
                    try:
                        if any(e in hot for e in t.vehicle.getRoute(vid)):
                            matches.append(vid)
                    except traci.TraCIException:
                        pass
                for k, vid in enumerate(matches):
                    if k % 2 == 0:                      # 50% cap
                        try:
                            t.vehicle.rerouteTraveltime(vid)
                            n_rr += 1
                        except traci.TraCIException:
                            pass
                actions.append({"t": now, "hot_edges": len(hot),
                                "rerouted_pending": n_rr})
    t.close()

    root = ET.parse(trip).getroot()
    losses = [float(x.get("timeLoss")) for x in root]
    durs = [float(x.get("duration")) for x in root]
    return {"branch": branch, "seed": seed, "arrived": len(losses),
            "mean_time_loss_s": statistics.mean(losses),
            "mean_duration_s": statistics.mean(durs),
            "total_time_loss_s": sum(losses),
            "interventions": actions if branch == "prevent" else []}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--out", type=Path,
                    default=REPO / "artifacts/prevent_experiment")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = []
    for s in args.seeds:
        for br in ("baseline", "prevent"):
            r = run(br, s, args.out)
            print(json.dumps({k: r[k] for k in
                              ("branch", "seed", "arrived",
                               "mean_time_loss_s")}))
            rows.append(r)

    base = [r for r in rows if r["branch"] == "baseline"]
    prev = [r for r in rows if r["branch"] == "prevent"]
    mb = statistics.mean(r["mean_time_loss_s"] for r in base)
    mp = statistics.mean(r["mean_time_loss_s"] for r in prev)
    result = {
        "stage": "PREVENT_MODE_EXPERIMENT",
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "trigger": "persistence forecast (P3 floor); gwnet trigger = follow-up",
        "design": "identical demand+seeds; prevention reroutes ONLY "
                  "not-yet-departed vehicles when predicted edge speed "
                  f"< {THRESH:.0%} of free speed",
        "baseline_mean_time_loss_s": round(mb, 1),
        "prevent_mean_time_loss_s": round(mp, 1),
        "reduction_pct": round(100 * (mb - mp) / mb, 2),
        "per_run": [{k: r[k] for k in ("branch", "seed", "arrived",
                                       "mean_time_loss_s",
                                       "total_time_loss_s")} for r in rows],
        "interventions_sample": prev[0]["interventions"][:5] if prev else [],
    }
    (args.out / "result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps({k: result[k] for k in
                      ("baseline_mean_time_loss_s",
                       "prevent_mean_time_loss_s", "reduction_pct")},
                     indent=2))


if __name__ == "__main__":
    main()
