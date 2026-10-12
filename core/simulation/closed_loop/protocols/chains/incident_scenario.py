#!/usr/bin/env python3
"""Text -> reroute -> measured delay: the NLP incident experiment on the Dhaka R1 twin.

    python -m core.simulation.closed_loop.protocols.chains.incident_scenario --seeds 11,12,13                 # 3 arms x 3 paired seeds
    python -m core.simulation.closed_loop.protocols.chains.incident_scenario --seeds 11 --report-delays 60,300,900   # value of early detection

The incident REALLY happens in every arm: at --t-inc the edges named by the NLP event
(results/nlp/events_karwan_bazar.jsonl: "Bus and CNG collision at Karwan Bazar ...") get
their speed limit cut to --v-inc for --duration seconds (traci.edge.setMaxSpeed), then restored.
Only the information differs:

  uninformed    nobody is told; every vehicle drives its pre-computed route          (baseline)
  reactive      equipped vehicles reroute every --period s on CURRENT travel times     (SUMO learns
                of the incident only once queues have formed)
  nlp_informed  at t_inc + --report-delay the classified report is turned into edge costs
                (free-flow traveltime x factor on the affected edges, valid for the incident
                window, via traci.edge.adaptTraveltime); equipped vehicles reroute on those
                costs (currentTravelTimes=False) -> they avoid the blocked edges BEFORE queues form.
                (report only: no live sensing elsewhere)
  nlp_predeparture   report only, applied to trips that have NOT departed yet: equipped vehicles are
                rerouted once, at insertion (the trip-start route choice), on free-flow + incident
                costs -> no mid-trip route swap.  reactive_predeparture = same but on live travel times (sensing).
  reactive_plus_nlp  sensing + report: every period the live edge travel times (TraCI subscription,
                edges slower than 1.1x free flow) are copied into the routing weights and the
                report's incident costs are overlaid (max of the two); reroute currentTravelTimes=False.

Same equipped set (predictive_routing.equipped), same demand (--scale, default SCALE_CHOICE),
same seed per arm.  Metrics = predictive_routing.parse_metrics + the "affected population":
vehicles whose initial route contained an incident edge (their mean travel time is the number
the incident report is supposed to improve).  Outputs results/routing/incident_{arm}_s{seed}/,
results/routing/incident.json, incident.md and (with --report-delays) incident_delay_sweep.md.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from core.common.paths import REPO
sys.path.insert(0, str(REPO))
from core.simulation.twin import runtime as pr  # noqa: E402

RESULTS = REPO / "results/routing"
DEFAULT_EVENT = REPO / "results/nlp/events_karwan_bazar.jsonl"


def load_event(path: Path) -> dict:
    ev = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    ev = [e for e in ev if e.get("edges")]
    if not ev:
        raise SystemExit(f"no mapped event with edges in {path}")
    e = ev[0]
    return {"text": e["text"], "label": e["label"], "place": e.get("place"), "edges": e["edges"],
            "factor": float(e.get("factor", 10.0)), "confidence": e.get("confidence")}


def run_arm(a, arm: str, seed: int, report_delay: int) -> dict:
    import traci
    out = RESULTS / (f"incident_{arm}_s{seed}" + (f"_d{report_delay}" if arm == "nlp_informed" and report_delay != a.report_delay else ""))
    out.mkdir(parents=True, exist_ok=True)
    a.seed = seed
    traci.start(pr.base_cmd(a, out), label=f"inc-{arm}-{seed}-{report_delay}")
    ev = a.event
    inc_edges = [e for e in ev["edges"] if e in a.known_edges]
    # remember speed limits so the incident can be lifted again
    lane_speed = {}
    for e in inc_edges:
        for i in range(traci.edge.getLaneNumber(e)):
            lid = f"{e}_{i}"
            lane_speed[lid] = traci.lane.getMaxSpeed(lid)
    free_tt = {e: traci.edge.getTraveltime(e) for e in inc_edges}   # free-flow before anything happens
    if arm == "reactive_plus_nlp":
        import traci.constants as tc
        for e in a.known_edges:
            traci.edge.subscribe(e, [tc.VAR_CURRENT_TRAVELTIME])
    affected, n_calls, informed_at = set(), 0, None
    t_end = a.t_inc + a.duration
    t = 0
    while t < a.horizon:
        traci.simulationStep()
        t = int(traci.simulation.getTime())
        if traci.simulation.getMinExpectedNumber() == 0:
            break
        for vid in traci.simulation.getDepartedIDList():          # affected population = planned through the incident
            if any(e in inc_edges for e in traci.vehicle.getRoute(vid)):
                affected.add(vid)
        if arm in ("nlp_predeparture", "reactive_predeparture"):   # pre-departure: reroute once at insertion
            if arm == "reactive_predeparture" or informed_at is not None:   # (SUMO cannot reroute loaded-not-inserted vehicles)
                for vid in traci.simulation.getDepartedIDList():
                    if pr.equipped(vid, a.compliance):
                        try:
                            traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=(arm == "reactive_predeparture"))
                            n_calls += 1
                        except traci.TraCIException:
                            pass
        if t == a.t_inc:                                            # the incident happens (all arms)
            for e in inc_edges:
                traci.edge.setMaxSpeed(e, a.v_inc)
        if t == t_end:
            for lid, v in lane_speed.items():
                traci.lane.setMaxSpeed(lid, v)
        if arm == "reactive_plus_nlp" and t % a.period == 0:        # sensing: live travel times -> weights
            import traci.constants as tc
            for e, res in traci.edge.getAllSubscriptionResults().items():
                tt = res.get(tc.VAR_CURRENT_TRAVELTIME)
                if tt is not None and tt > 1.1 * a.free_tt_all[e]:
                    if informed_at is not None and e in inc_edges and t < t_end:
                        tt = max(tt, free_tt[e] * ev["factor"])
                    traci.edge.adaptTraveltime(e, tt, begin=t, end=t + a.period)
        if arm in ("nlp_informed", "reactive_plus_nlp", "nlp_predeparture") and t == a.t_inc + report_delay:  # the report arrives
            for e in inc_edges:
                traci.edge.adaptTraveltime(e, free_tt[e] * ev["factor"], begin=t, end=t_end)
            informed_at = t
        if arm in ("uninformed", "nlp_predeparture", "reactive_predeparture"):
            continue                                                # no en-route rerouting in these arms
        for vid in traci.vehicle.getIDList():
            if not pr.equipped(vid, a.compliance):
                continue
            if (int(pr.hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % a.period == 0:
                if arm == "nlp_informed" and informed_at is None:
                    continue                                        # nothing to know yet -> keep route
                try:
                    traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=(arm == "reactive"))
                    n_calls += 1
                except traci.TraCIException:
                    pass
    traci.close()
    m = pr.parse_metrics(out, horizon=a.horizon) if "horizon" in pr.parse_metrics.__code__.co_varnames else pr.parse_metrics(out)
    # affected-population travel time (arrived only) + unfinished among affected
    aff_d, aff_unf = [], 0
    for ti in ET.parse(out / "tripinfo.xml").getroot().iter("tripinfo"):
        if ti.get("id") in affected:
            if float(ti.get("arrival", -1)) < 0:
                aff_unf += 1
            else:
                aff_d.append(float(ti.get("duration")))
    m.update({"affected_n": len(affected), "affected_arrived": len(aff_d), "affected_unfinished": aff_unf,
              "affected_mean_travel_time_s": statistics.fmean(aff_d) if aff_d else None})
    rec = {"arm": arm, "seed": seed, "report_delay_s": report_delay if arm in ("nlp_informed", "reactive_plus_nlp", "nlp_predeparture") else None,
           "t_inc": a.t_inc, "duration_s": a.duration, "v_inc_ms": a.v_inc, "incident_edges": inc_edges,
           "event": ev, "scale": a.scale, "horizon_s": a.horizon, "compliance": a.compliance,
           "rerouted_calls": n_calls, "metrics": m}
    (out / "metrics.json").write_text(json.dumps(rec, indent=1))
    print(f"[incident] {arm:12s} seed={seed} delay={report_delay} veh-h={m['total_vehicle_hours']:.1f} "
          f"affected_tt={m['affected_mean_travel_time_s']} arrived={m['arrived']} teleports={m['teleports']}", flush=True)
    return rec


def pct(a, b):
    return None if not a else 100.0 * (b - a) / a


def boot_ci(xs, n=10000, seed=0):
    r = random.Random(seed)
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return (None, None)
    ms = sorted(statistics.fmean(r.choices(xs, k=len(xs))) for _ in range(n))
    return (ms[int(0.025 * n)], ms[int(0.975 * n)])


COLS = ["total_vehicle_hours", "mean_travel_time_all", "p95_travel_time_s", "affected_mean_travel_time_s", "arrived", "unfinished", "teleports"]


def write_tables(a, recs: list[dict]):
    arms = [x for x in ["uninformed", "reactive", "nlp_informed", "reactive_plus_nlp", "reactive_predeparture", "nlp_predeparture"] if x in a.arms.split(",")]
    by = {arm: {r["seed"]: r["metrics"] for r in recs if r["arm"] == arm and (r["report_delay_s"] in (None, a.report_delay))} for arm in arms}
    lines = [f"# NLP incident scenario — Dhaka R1, {len(by['uninformed'])} paired seeds\n",
             f"Event: \"{a.event['text']}\" → label `{a.event['label']}` (p={a.event['confidence']}), place {a.event['place']}, "
             f"{len(a.event['edges'])} edges, factor ×{a.event['factor']}. Incident at t={a.t_inc}s for {a.duration}s, speed limit {a.v_inc} m/s; "
             f"report delay {a.report_delay}s; compliance {a.compliance}; demand scale {a.scale}; horizon {a.horizon}s.\n",
             "| arm | " + " | ".join(COLS) + " |", "|---|" + "---|" * len(COLS)]
    for arm in arms:
        vals = []
        for c in COLS:
            xs = [m[c] for m in by[arm].values() if m.get(c) is not None]
            vals.append(f"{statistics.fmean(xs):.1f} ± {statistics.pstdev(xs):.1f}" if xs else "–")
        lines.append(f"| {arm} | " + " | ".join(vals) + " |")
    summary = {}
    if "uninformed" not in by:
        (RESULTS / "incident.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines)); return
    lines += ["", "## Paired % change vs uninformed (mean over seeds [bootstrap 95 % CI]; sign count = seeds improved)", "",
              "| arm | " + " | ".join(COLS) + " |", "|---|" + "---|" * len(COLS)]
    for arm in [x for x in arms if x != "uninformed"]:
        cells, summary[arm] = [], {}
        for c in COLS:
            d = [pct(by["uninformed"][s].get(c), by[arm][s].get(c)) for s in by[arm] if s in by["uninformed"]]
            d = [x for x in d if x is not None]
            if not d:
                cells.append("–"); continue
            lo, hi = boot_ci(d)
            better = sum(x < 0 for x in d) if c != "arrived" else sum(x > 0 for x in d)
            cells.append(f"{statistics.fmean(d):+.1f} % [{lo:+.1f}, {hi:+.1f}] {better}/{len(d)}" if lo is not None else f"{d[0]:+.1f} %")
            summary[arm][c] = {"mean_pct": statistics.fmean(d), "ci95": [lo, hi], "per_seed": d}
        lines.append(f"| {arm} | " + " | ".join(cells) + " |")
    lines += ["", "`affected_*` = vehicles whose initial route ran through an incident edge. `arrived`: higher is better; all other columns: lower is better.",
              "Regenerate: `python -m core.simulation.closed_loop.protocols.chains.incident_scenario --seeds " + a.seeds + "`."]
    (RESULTS / "incident.md").write_text("\n".join(lines) + "\n")
    (RESULTS / "incident.json").write_text(json.dumps({"config": {k: v for k, v in vars(a).items() if k not in ("known_edges",)}, "runs": recs, "summary": summary}, indent=1, default=str))
    print("\n".join(lines))


def write_delay_sweep(a, recs: list[dict], seed: int):
    base = next(r for r in recs if r["arm"] == "uninformed" and r["seed"] == seed)["metrics"]
    lines = [f"# Value of early detection — nlp_informed arm, seed {seed}\n",
             "| report delay s | total_vehicle_hours | Δ vs uninformed | affected mean TT s | Δ affected | arrived | teleports |", "|---|---|---|---|---|---|---|",
             f"| (uninformed) | {base['total_vehicle_hours']:.1f} | – | {base['affected_mean_travel_time_s']:.1f} | – | {base['arrived']} | {base['teleports']} |"]
    for r in sorted((r for r in recs if r["arm"] == "nlp_informed" and r["seed"] == seed), key=lambda r: r["report_delay_s"]):
        m = r["metrics"]
        lines.append(f"| {r['report_delay_s']} | {m['total_vehicle_hours']:.1f} | {pct(base['total_vehicle_hours'], m['total_vehicle_hours']):+.1f} % | "
                     f"{m['affected_mean_travel_time_s']:.1f} | {pct(base['affected_mean_travel_time_s'], m['affected_mean_travel_time_s']):+.1f} % | {m['arrived']} | {m['teleports']} |")
    (RESULTS / "incident_delay_sweep.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> int:
    global RESULTS
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--arms", default="uninformed,reactive,nlp_informed,reactive_plus_nlp,reactive_predeparture,nlp_predeparture")
    p.add_argument("--results", default=str(RESULTS))
    p.add_argument("--resume", action="store_true", help="reuse finished incident_<arm>_s<seed>/metrics.json")
    p.add_argument("--event-file", default=str(DEFAULT_EVENT))
    p.add_argument("--horizon", type=int, default=5400)
    p.add_argument("--t-inc", type=int, default=900)
    p.add_argument("--duration", type=int, default=1800)
    p.add_argument("--v-inc", type=float, default=1.5, help="speed limit on incident edges during the incident (m/s)")
    p.add_argument("--report-delay", type=int, default=120, help="s between incident and classified report")
    p.add_argument("--report-delays", default="", help="extra delays to sweep for nlp_informed on the first seed, e.g. 60,300,900")
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--period", type=int, default=60)
    sc = RESULTS / "SCALE_CHOICE.json"
    p.add_argument("--scale", type=float, default=json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--edgedata-period", type=int, default=300)
    p.add_argument("--time-to-teleport", type=int, default=300)
    p.add_argument("--sumo-binary", default="sumo")
    a = p.parse_args()
    RESULTS = Path(a.results); RESULTS.mkdir(parents=True, exist_ok=True)
    a.event = load_event(Path(a.event_file))
    import sumolib
    net = sumolib.net.readNet(a.net)
    a.known_edges = {e.getID() for e in net.getEdges()}
    a.free_tt_all = {e.getID(): e.getLength() / max(e.getSpeed(), 0.1) for e in net.getEdges()}
    seeds = [int(s) for s in a.seeds.split(",")]
    t0 = time.time()
    recs = []
    for seed in seeds:
        for arm in a.arms.split(","):
            done = RESULTS / f"incident_{arm}_s{seed}" / "metrics.json"
            if a.resume and done.exists():
                recs.append(json.loads(done.read_text())); print(f"[incident] resume {arm} seed={seed}", flush=True)
                continue
            recs.append(run_arm(a, arm, seed, a.report_delay))
    write_tables(a, recs)
    if a.report_delays:
        for d in (int(x) for x in a.report_delays.split(",")):
            if d != a.report_delay:
                recs.append(run_arm(a, "nlp_informed", seeds[0], d))
        write_delay_sweep(a, recs, seeds[0])
    print(f"wall {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
