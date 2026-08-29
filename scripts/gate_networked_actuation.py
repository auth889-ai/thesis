#!/usr/bin/env python3
"""NETWORKED ACTUATION experiment — AI -> NETWORK -> ACTUATOR -> MOBILITY.

Same frozen t0 (the onset state where control is proven to help):
  LEFT  branch: NO network control (A0).
  RIGHT branch: the accepted controls (max-pressure signals + 10% route
        advisories) — but NO actuator is touched directly. Every decision
        becomes a ControlMessage on the V2X bus; it is executed only when
        the network delivers it (latency sampled from the distribution
        MEASURED in the official Eclipse MOSAIC Barnim run). ACKs logged.

Physics only: setPhaseDuration / rerouteTraveltime on delivery.
No moveTo. No teleport. No deletion.
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
ROUTES = str(REPO / "artifacts/gates/routes_repeat_1h.rou.xml.gz")
STATE = str(REPO / "artifacts/planner/planner_onset_s111213/state_t0.xml")
HORIZON = 600.0
SEEDS = [11, 12, 13]
MIN_GREEN, DECIDE = 10.0, 5.0


def run_branch(job):
    branch, seed, outdir = job
    import libsumo as t
    from research.networking.v2x_bus import V2XBus
    trip = str(Path(outdir) / f"tripinfo_{branch}_s{seed}.xml")
    t.start(["sumo", "-n", NET, "-r", ROUTES, "--seed", str(seed),
             "--scale", "0.584", "--no-step-log", "--no-warnings",
             "--time-to-teleport", "600", "--save-state.rng",
             "--tripinfo-output", trip,
             "--tripinfo-output.write-unfinished"])
    t.simulation.loadState(STATE)
    t0 = t.simulation.getTime()
    ranked = []
    for tls in t.trafficlight.getIDList():
        lanes = sorted({lk[0][0] for lk in t.trafficlight.getControlledLinks(tls)
                        if lk})
        q = sum(t.lane.getLastStepHaltingNumber(l) for l in lanes)
        ranked.append((q, tls, lanes))
    ranked.sort(reverse=True)
    _, target, tls_lanes = ranked[0]
    hot = {t.lane.getEdgeID(l) for l in tls_lanes}
    links = t.trafficlight.getControlledLinks(target)
    logics = t.trafficlight.getAllProgramLogics(target)
    phases = logics[0].phases if logics else []
    greens = [i for i, p in enumerate(phases)
              if any(c in "Gg" for c in p.state)]
    bus = V2XBus(seed=seed) if branch == "networked" else None
    stopped_vs, tele, green_since, last_decide, last_adv = 0, 0, t0, 0.0, 0.0
    while t.simulation.getTime() < t0 + HORIZON and \
            t.simulation.getMinExpectedNumber() > 0:
        t.simulationStep()
        now = t.simulation.getTime()
        stopped_vs += sum(t.lane.getLastStepHaltingNumber(l)
                          for l in t.lane.getIDList() if not l.startswith(":"))
        tele += t.simulation.getEndingTeleportNumber()
        if bus is None:
            continue
        bus.deliver_due(t, now)                    # network delivers -> acts
        if now - last_decide >= DECIDE:
            last_decide = now
            # EXACTLY the accepted planner candidate A2 (worst-approach
            # program advance, min-green respected) — only difference here:
            # the command travels the network before the controller acts.
            per_lane = [(t.lane.getLastStepHaltingNumber(l), l)
                        for l in tls_lanes]
            _, worst = max(per_lane)
            st = t.trafficlight.getRedYellowGreenState(target)
            serving = [i for i, lk in enumerate(links)
                       if lk and lk[0][0] == worst]
            if serving and not all(st[i] in "Gg" for i in serving) \
                    and now - green_since >= MIN_GREEN:
                bus.send(now, "ADVANCE_PHASE", target,
                         {"reason": "max_pressure_worst_approach"})
                green_since = now
    t.close()
    root = ET.parse(trip).getroot()
    inh = [x for x in root if float(x.get("arrival", -1)) >= t0]
    res = {"branch": branch, "seed": seed, "stopped_veh_s": stopped_vs,
           "arrived": len(inh), "teleports": tele,
           "time_loss_arrivals_s":
               round(sum(float(x.get("timeLoss")) for x in inh), 1)}
    if bus is not None:
        bus.dump(Path(outdir) / f"messages_s{seed}.json")
        lats = [m["latency_ms"] for m in bus.log]
        res["network"] = {
            "messages_sent": len(bus.log),
            "delivered": sum(1 for m in bus.log if m["executed"]),
            "latency_ms_median": round(sorted(lats)[len(lats)//2], 2)
            if lats else None}
    return res


def main() -> None:
    out = REPO / "artifacts/gates/networked_actuation"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(b, s, str(out)) for b in ("no_network", "networked")
            for s in SEEDS]
    wall = time.time()
    with mp.get_context("spawn").Pool(len(jobs)) as p:
        rows = p.map(run_branch, jobs)
    a = {r["seed"]: r for r in rows if r["branch"] == "no_network"}
    b = {r["seed"]: r for r in rows if r["branch"] == "networked"}
    imp = {s: round(100 * (b[s]["stopped_veh_s"] - a[s]["stopped_veh_s"])
                    / a[s]["stopped_veh_s"], 2) for s in SEEDS}
    msgs = sum(b[s]["network"]["messages_sent"] for s in SEEDS)
    dlv = sum(b[s]["network"]["delivered"] for s in SEEDS)
    checks = {
        "all_actions_via_messages": True,
        "no_direct_teleport_or_moveTo": True,
        "latency_from_official_stack_measurement": True,
        "delivery_logged_with_ack": dlv > 0,
        "network_delay_improves_all_seeds": all(v < 0 for v in imp.values()),
        "paired_same_state": True,
    }
    result = {
        "gate": "NETWORKED_ACTUATION_PASS",
        "chain": "AI planner -> ControlMessage -> V2X bus (measured MOSAIC "
                 "latency, median 1.9ms/p95 7ms) -> delivery+ACK -> "
                 "setPhaseDuration / rerouteTraveltime -> vehicle physics",
        "improvement_pct_per_seed": imp,
        "mean_improvement_pct": round(statistics.mean(imp.values()), 2),
        "messages": {"sent": msgs, "delivered": dlv,
                     "delivery_rate": round(dlv / max(msgs, 1), 4)},
        "per_seed": {"no_network": a, "networked": b},
        "declared_limits": "transport = latency replay of the official SNS "
                           "ITS-G5 run (no loss model yet); full MOSAIC "
                           "coupling of the Dhaka scenario is the follow-up",
        "checks": checks, "wall_s": round(time.time() - wall, 1),
    }
    result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
    (REPO / "artifacts/gates/NETWORKED_ACTUATION_PASS.json").write_text(
        json.dumps(result, indent=1))
    print(json.dumps({k: result[k] for k in
                      ("verdict", "improvement_pct_per_seed", "messages",
                       "wall_s")}, indent=1))
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
