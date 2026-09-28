#!/usr/bin/env python3
"""The whole live chain in one command: live Dhaka -> forecast -> routing -> counterfactual -> decision.

    python src/pipeline/routing/live_chain.py --seeds 11,12,13                     # on the CURRENT live state
    python src/pipeline/routing/live_chain.py --seeds 11,12,13 --horizon-min 30    # route on a 30-min-ahead forecast
    python src/pipeline/routing/live_chain.py --levels karwanbazar_to_shahbagh=3   # WHAT-IF (labelled, not evidence)

    live APIs -> state -> forecast -> future edge times -> router -> SUMO counterfactual -> ACT / NO_ACTION

The live feed supplies the CONGESTION STATE of six real Dhaka corridors. It does not supply demand:
the twin's trips remain the calibrated synthetic demand (`DHAKA_SIMULATED_DEMAND`), so what is
tested here is "does acting on live congestion knowledge help?", not "how much traffic is in Dhaka".
Both facts are written into every output record.

The counterfactual is honest in the way that matters: the live congestion is made REAL inside the
simulation for BOTH arms (each affected edge's speed limit is divided by its multiplier, so a
CONGESTED corridor genuinely slows traffic), and the arms differ only in whether the router KNOWS:

    unaware   every vehicle drives its pre-computed route                       (baseline)
    advised   the equipped share (--compliance) is routed before departure on
              the forecast edge times from src/pipeline/forecasting/live_to_edges.py

Paired seeds, identical demand, identical congestion. Decision rule (deliberately strict, the same
spirit as src/pipeline/routing/decision_guard.py): ACT only if the advised arm improves total vehicle-hours on
EVERY paired seed and does not reduce arrivals or increase teleports on average. Anything else is
NO_ACTION — including the common and honest case where the network is free-flowing and there is
nothing to route around.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from pipeline.forecasting.live_to_edges import MAP_FILE, latest_levels, multiplier, write_weights  # noqa: E402
from pipeline.routing import predictive_routing as pr  # noqa: E402
from pipeline.routing.predeparture_arm import VEH_RE, read_routes  # noqa: E402

RESULTS = REPO / "results/routing"
REACTIVE_PERIOD = 60          # s between reroute opportunities per vehicle
# Three arms, identical network / demand / seed; only the routing rule differs.
ARMS = ("unaware", "reactive", "advised")
SERIES = REPO / "data/forecasting/live_dhaka/series.npz"


def affected_edges(levels: dict, cmap: dict) -> dict:
    """edge -> multiplier actually in force (worst corridor wins), ignoring free-flow corridors."""
    out = {}
    for cid, level in levels.items():
        rec = cmap.get(cid, {})
        if rec.get("status") != "MAPPED" or level <= 0:
            continue
        m = multiplier(level)
        for eid in rec["edges"]:
            out[eid] = max(out.get(eid, 1.0), m)
    return out


def run_arm(a, arm: str, seed: int, slow: dict, weights: Path | None) -> dict:
    """One SUMO run. `slow` is applied in BOTH arms; only `advised` gets the weights."""
    import traci
    out = RESULTS / f"live_chain{a.tag}_{arm}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    routes = Path(a.routes)
    changed = 0
    if arm == "advised":
        vehicles = read_routes(routes)
        eq = [(v, d, r) for v, d, r in vehicles if pr.equipped(v, a.compliance) and float(d) < a.horizon]
        trips = out / "trips_equipped.xml"
        trips.write_text("<routes>\n" + "".join(
            f'  <trip id="{v}" depart="{d}" from="{r.split()[0]}" to="{r.split()[-1]}"/>\n' for v, d, r in eq) + "</routes>\n")
        alt = out / "routes_equipped.rou.xml"
        subprocess.run(["duarouter", "--net-file", str(a.net), "--route-files", str(trips),
                        "--weight-files", str(weights), "--weight-attribute", "traveltime",
                        "--output-file", str(alt), "--ignore-errors", "--no-warnings", "--no-step-log",
                        "--seed", str(seed), "--routing-threads", "4"], check=True, capture_output=True)
        new = {v: r for v, d, r in VEH_RE.findall(alt.read_text())}
        routes = out / "routes_merged.rou.xml"
        with open(routes, "w") as fh:
            fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                     'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
            for v, d, r in vehicles:
                nr = new.get(v, r); changed += nr != r
                fh.write(f'    <vehicle id="{v}" depart="{d}">\n        <route edges="{nr}" />\n    </vehicle>\n')
            fh.write("</routes>\n")
    ns = argparse.Namespace(net=str(a.net), routes=str(routes), seed=seed, scale=a.scale, horizon=a.horizon,
                            edgedata_period=300, time_to_teleport=300, sumo_binary="sumo")
    t0 = time.time()
    traci.start(pr.base_cmd(ns, out), label=f"live-{arm}-{seed}")
    applied = 0
    reroute_calls = 0
    for eid, m in slow.items():                       # make the live congestion REAL, in both arms
        try:
            for i in range(traci.edge.getLaneNumber(eid)):
                lid = f"{eid}_{i}"
                traci.lane.setMaxSpeed(lid, max(traci.lane.getMaxSpeed(lid) / m, 0.5))
            applied += 1
        except traci.TraCIException:
            pass
    t = 0
    while t < a.horizon and traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        t = int(traci.simulation.getTime())
        if arm != "reactive":
            continue
        # REACTIVE: equipped vehicles reroute on the travel times observed RIGHT NOW, with no
        # forecast at all. Each vehicle reroutes once per period at its own hash offset, so the
        # calls are staggered rather than every equipped vehicle rerouting on the same tick —
        # the same rule predictive_routing.py uses, so the arms stay comparable.
        for vid in traci.vehicle.getIDList():
            if not pr.equipped(vid, a.compliance):
                continue
            if (int(hashlib.md5(vid.encode()).hexdigest()[8:12], 16) + t) % REACTIVE_PERIOD == 0:
                try:
                    traci.vehicle.rerouteTraveltime(vid, currentTravelTimes=True)
                    reroute_calls += 1
                except traci.TraCIException:
                    pass
    traci.close()
    m = pr.parse_metrics(out, horizon=a.horizon)
    rec = {"arm": arm, "seed": seed, "edges_slowed": applied,
           "routes_changed": changed if arm != "reactive" else reroute_calls,
           "reroute_calls": reroute_calls,
           "wall_s": round(time.time() - t0, 1), "metrics": m}
    print(f"[live_chain] {arm:<8} seed={seed} slowed={applied} changed={rec['routes_changed']} "
          f"veh-h={m['total_vehicle_hours']:.1f} arrived={m['arrived']} teleports={m['teleports']} "
          f"({rec['wall_s']}s)", flush=True)
    return rec


def decide(runs: list[dict]) -> dict:
    by = {}
    for r in runs:
        by.setdefault(r["arm"], {})[r["seed"]] = r["metrics"]
    if "advised" not in by or "unaware" not in by:
        return {"decision": "NO_ACTION", "reason": "an arm did not run"}
    seeds = sorted(set(by["unaware"]) & set(by["advised"]))
    d = [(by["unaware"][s]["total_vehicle_hours"], by["advised"][s]["total_vehicle_hours"]) for s in seeds]
    pct = [100 * (b - u) / u for u, b in d if u]
    arr = [by["advised"][s]["arrived"] - by["unaware"][s]["arrived"] for s in seeds]
    tel = [by["advised"][s]["teleports"] - by["unaware"][s]["teleports"] for s in seeds]
    all_better = bool(pct) and all(x < 0 for x in pct)
    ok_arr = statistics.fmean(arr) >= 0 if arr else False
    ok_tel = statistics.fmean(tel) <= 0 if tel else False
    act = all_better and ok_arr and ok_tel
    reasons = []
    if not pct:
        reasons.append("no paired seeds")
    if pct and not all_better:
        reasons.append(f"vehicle-hours improved on only {sum(x < 0 for x in pct)}/{len(pct)} seeds")
    if not ok_arr:
        reasons.append(f"arrivals fall on average ({statistics.fmean(arr):+.1f})")
    if not ok_tel:
        reasons.append(f"teleports rise on average ({statistics.fmean(tel):+.1f})")
    return {"decision": "ACT" if act else "NO_ACTION",
            "reason": "advised improves total vehicle-hours on every paired seed without cost to arrivals or teleports"
                      if act else "; ".join(reasons),
            "seeds": seeds, "vehicle_hours_pct_per_seed": [round(x, 2) for x in pct],
            "mean_pct": round(statistics.fmean(pct), 2) if pct else None,
            "arrivals_delta": arr, "teleports_delta": tel,
            "rule": "ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall "
                    "and mean teleports do not rise"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="11,12,13")
    p.add_argument("--horizon", type=int, default=3600, help="simulation horizon (s)")
    p.add_argument("--horizon-min", type=float, default=15.0, help="forecast lead time (min)")
    p.add_argument("--compliance", type=float, default=0.3)
    sc = RESULTS / "SCALE_CHOICE.json"
    p.add_argument("--scale", type=float, default=json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25)
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--series", type=Path, default=SERIES)
    p.add_argument("--tag", default="", help="suffix for the output files (sweeps)")
    p.add_argument("--levels", default="", help="WHAT-IF override, e.g. 'corridor=3,other=2' (labelled, not evidence)")
    a = p.parse_args()

    cmap = json.loads(MAP_FILE.read_text())
    if a.levels:
        levels = {k: float(v) for k, v in (kv.split("=") for kv in a.levels.split(","))}
        source = {"reality": "SYNTHETIC_WHAT_IF", "note": "levels supplied on the command line — a mechanism "
                  "check, NEVER evidence about Dhaka", "levels": levels}
    else:
        levels, prov = latest_levels(a.series, int(round(a.horizon_min * 60 / 300)))
        source = {"reality": "REAL_LIVE", "provider": "google_routes", "google_data_mode": "RUNTIME_REFERENCE",
                  "forecast": "persistence", "horizon_min": a.horizon_min, "levels": levels} | prov
    slow = affected_edges(levels, cmap)
    print(f"[live_chain] {source['reality']}: levels {({k: round(v, 2) for k, v in levels.items()})}")
    print(f"[live_chain] {len(slow)} edges congested above free flow")

    arms_note = ("unaware = nobody reroutes; reactive = reroute on CURRENT travel times "
                 "(no forecast); advised = reroute on the FORECAST travel-time table")
    weights = RESULTS / "live_chain_weights.xml"
    wrec = write_weights(levels, cmap, weights, 0.0, float(a.horizon), source)
    seeds = [int(s) for s in a.seeds.split(",")]
    runs = []
    if not slow:
        dec = {"decision": "NO_ACTION", "reason": "every monitored corridor is at free flow — nothing to route "
               "around; acting would be intervention without evidence", "seeds": seeds}
        print(f"[live_chain] DECISION: NO_ACTION — {dec['reason']}")
    else:
        for seed in seeds:
            for arm in ARMS:
                runs.append(run_arm(a, arm, seed, slow, weights))
        dec = decide(runs)
        print(f"[live_chain] DECISION: {dec['decision']} — {dec['reason']}")

    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(), "source": source,
           "demand": "DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand)",
           "network": str(Path(a.net).relative_to(REPO)), "scale": a.scale, "horizon_s": a.horizon,
           "compliance": a.compliance, "edges_congested": len(slow), "weights": wrec, "runs": runs, "decision": dec}
    (RESULTS / f"live_chain{a.tag}.json").write_text(json.dumps(rec, indent=1, default=str))

    lines = [f"# Live chain — Dhaka live congestion to a routing decision\n",
             f"Generated {rec['generated_utc']}. Source: **{source['reality']}**"
             + (f" (google_routes, RUNTIME_REFERENCE, persistence +{a.horizon_min:.0f} min)" if source["reality"] == "REAL_LIVE" else "")
             + f". Network: real Dhaka R1. Demand: {rec['demand']}. "
             f"{len(slow)} edges congested above free flow; compliance {a.compliance:.0%}; scale {a.scale}; horizon {a.horizon}s.\n",
             "| corridor | level | multiplier | edges |", "|---|---|---|---|"]
    for cid, r in sorted(wrec["corridors"].items()):
        lines.append(f"| {cid} | {r['level']:.2f} | x{r['multiplier']:.2f} | {r['edges']} |")
    if runs:
        lines += ["", "| arm | seed | total veh-h | arrived | teleports | routes changed |", "|---|---|---|---|---|---|"]
        for r in runs:
            m = r["metrics"]
            lines.append(f"| {r['arm']} | {r['seed']} | {m['total_vehicle_hours']:.1f} | {m['arrived']} | "
                         f"{m['teleports']} | {r['routes_changed']} |")
        lines += ["", f"Per-seed vehicle-hour change: {dec.get('vehicle_hours_pct_per_seed')} "
                      f"(mean {dec.get('mean_pct')} %)."]
    lines += ["", f"## Decision: **{dec['decision']}**", "", dec["reason"], "",
              f"Rule: {dec.get('rule', 'no congestion observed -> no intervention')}", "",
              "Regenerate: `python src/pipeline/routing/live_chain.py --seeds " + a.seeds + "`."]
    (RESULTS / f"live_chain{a.tag}.md").write_text("\n".join(lines) + "\n")
    print(f"[live_chain] wrote {RESULTS / ('live_chain' + a.tag + '.md')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
