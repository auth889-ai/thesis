#!/usr/bin/env python3
"""The whole system as ONE command, and the only place a result counts as finished.

    python pipeline/routing/integrated_chain.py --seeds 11,12,13
    python pipeline/routing/integrated_chain.py --seeds 11,12,13 --v2x degraded

    CITY -> TRAFFIC DATA -> ACTUAL ML/DL FORECAST -> FUTURE ROUTE COST
         -> ROUTE OPTIMIZATION -> SUMO COUNTERFACTUAL -> BEFORE/AFTER METRICS

Three arms on an IDENTICAL network, demand, seed and horizon. Only the routing rule differs, which
is what makes the comparison mean anything:

    BASELINE          nobody reroutes
    REACTIVE          equipped vehicles reroute on the travel times observed RIGHT NOW
    PREDICTION_AWARE  equipped vehicles reroute on the FORECAST travel-time table produced by a
                      real model through pipeline/routing/forecast_to_costs.py

The V2X condition sits in front of the advisory: under a degraded link only a fraction of equipped
vehicles receive their advisory in time, and that fraction is read from the measured delivery
table rather than assumed. So the causal chain the thesis rests on runs end to end here —

    NETWORK QUALITY -> FORECAST QUALITY -> ROUTE DECISION -> SUMO OUTCOME

Every number is a SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin. The live feed supplies the
congestion state, never the demand.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import pipeline.routing.predictive_routing as pr                  # noqa: E402
from pipeline.routing import live_chain as lc                     # noqa: E402
from pipeline.routing.forecast_to_costs import (build_table, fetch_forecast,  # noqa: E402
                                                write_weights)
from pipeline.core.network_file import ensure_net                 # noqa: E402

RESULTS = REPO / "results/routing"
LATENCY_CSV = REPO / "results/networking/latency.csv"
ARMS = ("baseline", "reactive", "prediction_aware")

# V2X conditions -> (added latency ms, loss %). Delivery is READ from the measured sweep.
V2X = {"ideal": (0, 0), "good": (0, 10), "degraded": (500, 30), "bad": (5000, 30)}


def delivery_fraction(condition: str) -> tuple[float, dict]:
    if condition not in V2X:
        raise SystemExit(f"unknown v2x condition {condition!r}; have {sorted(V2X)}")
    added, loss = V2X[condition]
    if not LATENCY_CSV.exists():
        raise SystemExit(f"missing {LATENCY_CSV}; run pipeline/networking/latency_injection.py")
    for r in csv.DictReader(LATENCY_CSV.open()):
        if int(r["added_latency_ms"]) == added and int(float(r["loss_pct"])) == loss:
            return float(r["frac_delivered_1hz_repeat"]), {
                "condition": condition, "added_latency_ms": added, "loss_pct": loss,
                "source": "results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED)",
                "n_vehicles": int(r["n_vehicles"])}
    raise SystemExit(f"no delivery row for ({added} ms, {loss} %)")


def delivered(vid: str, p: float, condition: str, seed: int) -> bool:
    if p >= 1.0:
        return True
    h = hashlib.md5(f"{vid}|{condition}|{seed}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) < p


def run_arm(a, arm: str, seed: int, slow: dict, weights: Path, deliver_p: float) -> dict:
    """One SUMO run. `slow` makes the observed congestion real in EVERY arm."""
    import traci
    out = RESULTS / f"chain{a.tag}_{arm}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    routes, changed, advised = Path(a.routes), 0, 0

    if arm == "prediction_aware":
        vehicles = lc.read_routes(routes)
        eq = [(v, d, r) for v, d, r in vehicles
              if pr.equipped(v, a.compliance) and float(d) < a.horizon]
        got = [(v, d, r) for v, d, r in eq if delivered(v, deliver_p, a.v2x, seed)]
        advised = len(got)
        if got:
            trips = out / "trips.xml"
            trips.write_text("<routes>\n" + "".join(
                f'  <trip id="{v}" depart="{d}" from="{r.split()[0]}" to="{r.split()[-1]}"/>\n'
                for v, d, r in got) + "</routes>\n")
            alt = out / "routes_advised.rou.xml"
            subprocess.run(["duarouter", "--net-file", str(a.net), "--route-files", str(trips),
                            "--weight-files", str(weights), "--weight-attribute", "traveltime",
                            "--output-file", str(alt), "--ignore-errors", "--no-warnings",
                            "--no-step-log", "--seed", str(seed), "--routing-threads", "4"],
                           check=True, capture_output=True)
            new = {v: r for v, d, r in lc.VEH_RE.findall(alt.read_text())}
            routes = out / "routes_merged.rou.xml"
            with open(routes, "w") as fh:
                fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                         'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
                for v, d, r in vehicles:
                    nr = new.get(v, r)
                    changed += nr != r
                    fh.write(f'    <vehicle id="{v}" depart="{d}">\n'
                             f'        <route edges="{nr}" />\n    </vehicle>\n')
                fh.write("</routes>\n")

    ns = argparse.Namespace(net=str(a.net), routes=str(routes), seed=seed, scale=a.scale,
                            horizon=a.horizon, edgedata_period=300, time_to_teleport=300,
                            sumo_binary="sumo")
    t0 = time.time()
    traci.start(pr.base_cmd(ns, out), label=f"chain-{arm}-{seed}")
    applied = 0
    for eid, m in slow.items():
        try:
            for i in range(traci.edge.getLaneNumber(eid)):
                lid = f"{eid}_{i}"
                traci.lane.setMaxSpeed(lid, max(traci.lane.getMaxSpeed(lid) / m, 0.5))
            applied += 1
        except traci.TraCIException:
            pass
    reroutes, t = 0, 0
    while t < a.horizon and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t = int(traci.simulation.getTime())
        if arm != "reactive":
            continue
        for vid in traci.vehicle.getIDList():
            if not pr.equipped(vid, a.compliance):
                continue
            if not delivered(vid, deliver_p, a.v2x, seed):
                continue                      # a missed advisory means no reroute, in both arms
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % 60 == 0:
                try:
                    traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                    reroutes += 1
                except traci.TraCIException:
                    pass
    traci.close()

    m = pr.parse_metrics(out, horizon=a.horizon)
    rec = {"arm": arm, "seed": seed, "edges_slowed": applied,
           "advisories_delivered": advised, "routes_changed": changed or reroutes,
           "wall_s": round(time.time() - t0, 1), "metrics": m}
    print(f"[chain] {arm:<17} seed={seed} advised={advised:<5} changed={rec['routes_changed']:<5} "
          f"veh-h={m['total_vehicle_hours']:.1f} tt={m.get('mean_travel_time_s', 0):.0f}s "
          f"p95={m.get('p95_travel_time_s', 0):.0f}s wait={m.get('total_waiting_s', 0):.0f} "
          f"arr={m['arrived']} tel={m['teleports']} ({rec['wall_s']}s)", flush=True)
    return rec


def summarise(runs: list[dict]) -> dict:
    by: dict[str, list] = {}
    for r in runs:
        by.setdefault(r["arm"], []).append(r)
    rows = []
    for arm in ARMS:
        rs = by.get(arm) or []
        if not rs:
            continue
        n = len(rs)
        m = [r["metrics"] for r in rs]
        rows.append({
            "arm": arm, "seeds": [r["seed"] for r in rs],
            "total_vehicle_hours": round(sum(x["total_vehicle_hours"] for x in m) / n, 2),
            "mean_travel_time_s": round(sum(x.get("mean_travel_time_s", 0) for x in m) / n, 1),
            "p95_travel_time_s": round(sum(x.get("p95_travel_time_s", 0) for x in m) / n, 1),
            "total_waiting_s": round(sum(x.get("total_waiting_s", 0) for x in m) / n, 0),
            "mean_time_loss_s": round(sum(x.get("mean_time_loss_s", 0) for x in m) / n, 1),
            "arrived": round(sum(x["arrived"] for x in m) / n, 1),
            "teleports": round(sum(x["teleports"] for x in m) / n, 1),
            "reroutes": round(sum(r["routes_changed"] for r in rs) / n, 1),
            "advisories_delivered": round(sum(r["advisories_delivered"] for r in rs) / n, 1),
        })
    base = next((r for r in rows if r["arm"] == "baseline"), None)
    if base:
        for r in rows:
            for k, label in (("total_vehicle_hours", "vehicle_hours_pct"),
                             ("mean_travel_time_s", "travel_time_pct"),
                             ("total_waiting_s", "waiting_pct"),
                             ("p95_travel_time_s", "p95_pct")):
                b = base[k] or 1
                r[label] = round((r[k] - b) / b * 100, 2)
    # per-seed agreement: a mean that only one seed supports is not a result
    verdict = {}
    if base and len(by.get("baseline", [])) >= 2:
        for arm in ("reactive", "prediction_aware"):
            per = []
            for r in by.get(arm, []):
                b = next((x for x in by["baseline"] if x["seed"] == r["seed"]), None)
                if b:
                    bv = b["metrics"]["total_vehicle_hours"] or 1
                    per.append(round((r["metrics"]["total_vehicle_hours"] - bv) / bv * 100, 2))
            if per:
                better = sum(1 for x in per if x < 0)
                verdict[arm] = {
                    "per_seed_pct": per, "seeds_improved": f"{better}/{len(per)}",
                    "claim": "IMPROVES" if better == len(per) else "NOT_ESTABLISHED",
                    "why": ("every paired seed improved" if better == len(per) else
                            f"only {better} of {len(per)} paired seeds improved; a mean that the "
                            f"seeds do not support is not a result"),
                }
    return {"arms": rows, "verdict": verdict}


def write_report(rec: dict, tag: str) -> Path:
    s = rec["summary"]
    fc = rec["forecast"]
    L = [f"# Integrated chain — forecast to control, measured\n",
         f"Generated {rec['generated_utc']}.\n",
         "```",
         "CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO",
         "```\n",
         f"**Forecast.** {fc['model']}"
         + (f" (checkpoint `{fc['checkpoint']}`)" if fc.get("checkpoint") else "")
         + f", horizon {fc['horizon_min']} min, "
         + ("a BASELINE" if fc["is_baseline"] else "a trained/pretrained model") + ". "
         + f"{rec['coverage']['covered']}/{rec['coverage']['mapped']} mapped SUMO edges priced from "
         f"its numeric output.\n",
         f"**V2X condition.** `{rec['v2x']['condition']}` — {rec['v2x']['added_latency_ms']} ms "
         f"added latency, {rec['v2x']['loss_pct']} % loss, delivery fraction "
         f"**{rec['delivery_fraction']}** read from {rec['v2x']['source']}.\n",
         f"**Scenario.** Network {rec['network']}; demand {rec['demand']}; "
         f"{rec['edges_congested']} edges slowed to reproduce the observed state in EVERY arm; "
         f"compliance {rec['compliance']:.0%}; horizon {rec['horizon_s']} s; seeds {rec['seeds']}.\n",
         "## Before / after\n",
         "| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | "
         "time loss s | arrived | teleports | reroutes | advisories |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in s["arms"]:
        L.append(f"| **{r['arm']}** | {r['total_vehicle_hours']} | {r.get('vehicle_hours_pct', 0):+.2f} % | "
                 f"{r['mean_travel_time_s']} | {r.get('travel_time_pct', 0):+.2f} % | "
                 f"{r['p95_travel_time_s']} | {r['total_waiting_s']:.0f} | "
                 f"{r.get('waiting_pct', 0):+.2f} % | {r['mean_time_loss_s']} | {r['arrived']} | "
                 f"{r['teleports']} | {r['reroutes']} | {r['advisories_delivered']} |")
    if s["verdict"]:
        L += ["", "## Does it actually help?\n",
              "| arm | per-seed veh-h % | seeds improved | claim |", "|---|---|---|---|"]
        for arm, v in s["verdict"].items():
            L.append(f"| {arm} | {v['per_seed_pct']} | {v['seeds_improved']} | "
                     f"**{v['claim']}** — {v['why']} |")
    L += ["", "All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a "
              "measurement of the real road. The live feed supplies the congestion state; the "
              "demand is the project's calibrated synthetic demand.\n",
          f"Regenerate: `python pipeline/routing/integrated_chain.py --seeds "
          f"{','.join(str(x) for x in rec['seeds'])} --v2x {rec['v2x']['condition']}`.\n"]
    out = RESULTS / f"integrated_chain{tag}.md"
    out.write_text("\n".join(L))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--horizon", type=int, default=1800)
    p.add_argument("--horizon-min", type=int, default=15, help="forecast lead time")
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--v2x", default="ideal", choices=sorted(V2X))
    p.add_argument("--city", default="dhaka")
    p.add_argument("--model", default=None)
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--levels", default="karwanbazar_to_shahbagh=3,farmgate_to_shahbagh=2")
    p.add_argument("--tag", default="")
    sc = RESULTS / "SCALE_CHOICE.json"
    p.add_argument("--scale", type=float,
                   default=json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    a = p.parse_args()

    # 1. FORECAST — a real model, through the same API the interface uses
    print("[chain] 1/4 forecast")
    res = fetch_forecast(a.city, a.horizon_min, a.model, a.api)
    net = ensure_net(Path(a.net))
    table = build_table(res, a.horizon_min, net)
    weights = RESULTS / f"weights/chain{a.tag}_weights.xml"
    write_weights(table, weights, 0.0, float(a.horizon))
    fc = table["forecast"]
    print(f"        {fc['model']} (baseline={fc['is_baseline']}), "
          f"{table['covered_edges']}/{table['mapped_edges']} edges priced")

    # 2. V2X condition -> how many advisories actually arrive
    print("[chain] 2/4 v2x")
    deliver_p, v2x = delivery_fraction(a.v2x)
    print(f"        {a.v2x}: delivery {deliver_p}")

    # 3. congestion made real in every arm
    cmap = json.loads((REPO / "data/forecasting/live_dhaka/corridor_edges.json").read_text())
    levels = {k: float(v) for k, v in (kv.split("=") for kv in a.levels.split(","))}
    slow = lc.affected_edges(levels, cmap)
    print(f"[chain] 3/4 scenario: {len(slow)} edges congested")

    # 4. three arms, identical everything but the routing rule
    print("[chain] 4/4 SUMO")
    seeds = [int(x) for x in a.seeds.split(",")]
    runs = [run_arm(a, arm, s, slow, weights, deliver_p) for s in seeds for arm in ARMS]

    rec = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "chain": "CITY -> DATA -> FORECAST -> ROUTE COST -> ROUTING -> SUMO",
        "forecast": fc, "coverage": {"covered": table["covered_edges"],
                                     "mapped": table["mapped_edges"]},
        "predicted_speeds": table.get("predicted_speeds"),
        "v2x": v2x, "delivery_fraction": deliver_p,
        "network": Path(a.net).name, "demand": "DHAKA_SIMULATED_DEMAND",
        "edges_congested": len(slow), "compliance": a.compliance, "horizon_s": a.horizon,
        "seeds": seeds, "levels": levels,
        "label": "SIMULATED COUNTERFACTUAL — not a live-road outcome",
        "runs": runs, "summary": summarise(runs),
    }
    (RESULTS / f"integrated_chain{a.tag}.json").write_text(json.dumps(rec, indent=1, default=str))
    out = write_report(rec, a.tag)
    print(f"\n[chain] wrote {out.relative_to(REPO)}")
    for arm, v in rec["summary"]["verdict"].items():
        print(f"[chain] {arm}: {v['claim']} ({v['seeds_improved']} seeds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
