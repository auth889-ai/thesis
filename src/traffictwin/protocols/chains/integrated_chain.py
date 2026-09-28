#!/usr/bin/env python3
"""The whole system as ONE command, and the only place a result counts as finished.

    python src/pipeline/routing/integrated_chain.py --seeds 11,12,13
    python src/pipeline/routing/integrated_chain.py --seeds 11,12,13 --v2x degraded
    python src/pipeline/routing/integrated_chain.py --seeds 11 --horizon 900 --as-of peak   # smoke

or, as a service, POST /api/experiment/chain/run on the backend, which calls the same run_chain().

Each execution gets a RUN ID and writes results/routing/runs/<run_id>/ — status.json while it is
running, then run.json with every metric this execution measured, the SUMO output directory of
every arm, and the forecast weight table the prediction arm actually routed on. Nothing here is
read back from an earlier run.

    CITY -> TRAFFIC DATA -> ACTUAL ML/DL FORECAST -> FUTURE ROUTE COST
         -> ROUTE OPTIMIZATION -> SUMO COUNTERFACTUAL -> BEFORE/AFTER METRICS

Three arms on an IDENTICAL network, demand, seed and horizon. Only the routing rule differs, which
is what makes the comparison mean anything:

    BASELINE          nobody reroutes
    REACTIVE          equipped vehicles reroute on the travel times observed RIGHT NOW
    PREDICTION_AWARE  equipped vehicles reroute on the FORECAST travel-time table produced by a
                      real model through src/pipeline/routing/forecast_to_costs.py

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
import uuid
from datetime import datetime, timezone
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

import pipeline.routing.predictive_routing as pr                  # noqa: E402
from traffictwin.protocols.chains import live_chain as lc                     # noqa: E402
from traffictwin.optimization.forecast_costs import (build_table, fetch_forecast,  # noqa: E402
                                                write_weights)
from pipeline.core.network_file import ensure_net                 # noqa: E402

RESULTS = REPO / "results/routing"
RUNS = RESULTS / "runs"
LATENCY_CSV = REPO / "results/networking/latency.csv"
ARMS = ("baseline", "reactive", "prediction_aware")

# V2X conditions -> (added latency ms, loss %). Delivery is READ from the measured sweep.
V2X = {"ideal": (0, 0), "good": (0, 10), "degraded": (500, 30), "bad": (5000, 30)}


def delivery_fraction(condition: str) -> tuple[float, dict]:
    if condition not in V2X:
        raise SystemExit(f"unknown v2x condition {condition!r}; have {sorted(V2X)}")
    added, loss = V2X[condition]
    if not LATENCY_CSV.exists():
        raise SystemExit(f"missing {LATENCY_CSV}; run src/pipeline/networking/latency_injection.py")
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


def predeparture_routes(a, seed: int, weights: Path, out: Path, deliver_p: float
                        ) -> tuple[Path, int, int]:
    """Equipped vehicles that RECEIVED their advisory get a route from duarouter on the forecast
    travel-time table; everyone else keeps the static route. -> (merged route file, changed,
    advised). Shared by the chain and the live twin so both price the future the same way."""
    routes = Path(a.routes)
    vehicles = lc.read_routes(routes)
    eq = [(v, d, r) for v, d, r in vehicles
          if pr.equipped(v, a.compliance) and float(d) < a.horizon]
    got = [(v, d, r) for v, d, r in eq if delivered(v, deliver_p, a.v2x, seed)]
    advised, changed = len(got), 0
    if not got:
        return routes, 0, 0
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
    merged = out / "routes_merged.rou.xml"
    with open(merged, "w") as fh:
        fh.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                 'xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        for v, d, r in vehicles:
            nr = new.get(v, r)
            changed += nr != r
            fh.write(f'    <vehicle id="{v}" depart="{d}">\n'
                     f'        <route edges="{nr}" />\n    </vehicle>\n')
        fh.write("</routes>\n")
    return merged, changed, advised


def run_arm(a, arm: str, seed: int, slow: dict, weights: Path, deliver_p: float,
            run_dir: Path) -> dict:
    """One SUMO run. `slow` makes the observed congestion real in EVERY arm."""
    import traci
    out = run_dir / f"{arm}_s{seed}"
    out.mkdir(parents=True, exist_ok=True)
    routes, changed, advised = Path(a.routes), 0, 0

    if arm == "prediction_aware":
        if getattr(a, "forecast_kind", "model") == "oracle":
            # the truth from this seed's own baseline run: the ceiling any forecast could reach
            weights = run_dir / f"baseline_s{seed}" / "edgedata.xml"
            if not weights.exists():
                raise SystemExit(f"oracle needs the baseline run for seed {seed} first ({weights})")
        routes, changed, advised = predeparture_routes(a, seed, weights, out, deliver_p)

    ns = argparse.Namespace(net=str(a.net), routes=str(routes), seed=seed, scale=a.scale,
                            horizon=a.horizon, edgedata_period=300, time_to_teleport=300,
                            sumo_binary="sumo")
    t0 = time.time()
    traci.start(pr.base_cmd(ns, out), port=pr.free_port(), label=f"chain-{arm}-{seed}-{t0}")
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
           "forecast_kind": getattr(a, "forecast_kind", "model") if arm == "prediction_aware" else None,
           "weights_used": str(weights) if arm == "prediction_aware" else None,
           "advisories_delivered": advised, "routes_changed": changed or reroutes,
           "wall_s": round(time.time() - t0, 1), "out_dir": str(out.relative_to(REPO)),
           "metrics": m}
    (out / "metrics.json").write_text(json.dumps(rec, indent=1))
    print(f"[chain] {arm:<17} seed={seed} advised={advised:<5} changed={rec['routes_changed']:<5} "
          f"veh-h={m['total_vehicle_hours']:.1f} tt={m.get('mean_travel_time_s', 0) or 0:.0f}s "
          f"p95={m.get('p95_travel_time_s', 0) or 0:.0f}s wait={m.get('total_waiting_s', 0):.0f} "
          f"q={m.get('mean_queue_veh') or 0:.1f} arr={m['arrived']} tel={m['teleports']} "
          f"({rec['wall_s']}s)", flush=True)
    return rec


def summarise(runs: list[dict]) -> dict:
    by: dict[str, list] = {}
    for r in runs:
        by.setdefault(r["arm"], []).append(r)
    rows = []
    mean = lambda xs: sum(x or 0 for x in xs) / max(len(xs), 1)
    for arm in ARMS:
        rs = by.get(arm) or []
        if not rs:
            continue
        n = len(rs)
        m = [r["metrics"] for r in rs]
        rows.append({
            "arm": arm, "seeds": [r["seed"] for r in rs],
            "total_vehicle_hours": round(mean([x["total_vehicle_hours"] for x in m]), 2),
            "mean_travel_time_s": round(mean([x.get("mean_travel_time_s") for x in m]), 1),
            "p95_travel_time_s": round(mean([x.get("p95_travel_time_s") for x in m]), 1),
            "total_waiting_s": round(mean([x.get("total_waiting_s") for x in m]), 0),
            "mean_time_loss_s": round(mean([x.get("mean_time_loss_s") for x in m]), 1),
            "mean_queue_veh": round(mean([x.get("mean_queue_veh") for x in m]), 2),
            "max_queue_veh": round(max((x.get("max_queue_veh") or 0) for x in m), 1),
            "arrived": round(mean([x["arrived"] for x in m]), 1),
            "teleports": round(mean([x["teleports"] for x in m]), 1),
            "reroutes": round(mean([r["routes_changed"] for r in rs]), 1),
            "advisories_delivered": round(mean([r["advisories_delivered"] for r in rs]), 1),
        })
    base = next((r for r in rows if r["arm"] == "baseline"), None)
    if base:
        for r in rows:
            for k, label in (("total_vehicle_hours", "vehicle_hours_pct"),
                             ("mean_travel_time_s", "travel_time_pct"),
                             ("total_waiting_s", "waiting_pct"),
                             ("p95_travel_time_s", "p95_pct"),
                             ("mean_queue_veh", "queue_pct")):
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
    elif base:
        verdict = {}
    # HELPED / HURT / INCONCLUSIVE from the paired per-seed differences, with a 95 % CI (t-based)
    ci = {}
    if base:
        for arm in ("reactive", "prediction_aware"):
            per = []
            for r in by.get(arm, []):
                b = next((x for x in by["baseline"] if x["seed"] == r["seed"]), None)
                if b:
                    bv = b["metrics"]["total_vehicle_hours"] or 1
                    per.append((r["metrics"]["total_vehicle_hours"] - bv) / bv * 100)
            if not per:
                continue
            n = len(per); mean = sum(per) / n
            sd = (sum((x - mean) ** 2 for x in per) / (n - 1)) ** 0.5 if n > 1 else None
            tcrit = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447, 8: 2.365,
                     9: 2.306, 10: 2.262}.get(n, 1.96)
            half = tcrit * sd / n ** 0.5 if sd is not None else None
            lo, hi = (mean - half, mean + half) if half is not None else (None, None)
            wins = sum(1 for x in per if x < 0)
            label = ("INCONCLUSIVE" if n < 2 or half is None else
                     "HELPED" if hi < 0 else "HURT" if lo > 0 else "INCONCLUSIVE")
            ci[arm] = {"label": label, "mean_pct": round(mean, 2),
                       "ci95": [None if lo is None else round(lo, 2), None if hi is None else round(hi, 2)],
                       "wins": wins, "seeds": n, "per_seed_pct": [round(x, 2) for x in per],
                       "metric": "total vehicle-hours vs baseline, paired per seed"}
    return {"arms": rows, "verdict": verdict, "verdict_ci": ci}


def write_report(rec: dict, out: Path) -> Path:
    s = rec["summary"]
    fc = rec["forecast"]
    L = [f"# Integrated chain — forecast to control, measured\n",
         f"Run `{rec['run_id']}`, generated {rec['generated_utc']}.\n",
         "```",
         "CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO",
         "```\n",
         f"**Forecast.** {fc['model']}"
         + (f" (checkpoint `{fc['checkpoint']}`)" if fc.get("checkpoint") else "")
         + f", horizon {fc['horizon_min']} min, "
         + ("a BASELINE" if fc["is_baseline"] else "a trained/pretrained model") + ". "
         + f"Input {rec['forecast_input']}. "
         + f"{rec['coverage']['covered']}/{rec['coverage']['mapped']} mapped SUMO edges priced from "
         f"its numeric output ({rec['pricing']['rule']}).\n",
         f"**V2X condition.** `{rec['v2x']['condition']}` — {rec['v2x']['added_latency_ms']} ms "
         f"added latency, {rec['v2x']['loss_pct']} % loss, delivery fraction "
         f"**{rec['delivery_fraction']}** read from {rec['v2x']['source']}.\n",
         f"**Scenario.** Network {rec['network']}; demand {rec['demand']}; "
         f"{rec['edges_congested']} edges slowed to reproduce the observed state in EVERY arm "
         f"({rec['levels_source']}); compliance {rec['compliance']:.0%}; horizon "
         f"{rec['horizon_s']} s; seeds {rec['seeds']}.\n",
         "## Before / after\n",
         "| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | "
         "queue veh | time loss s | arrived | teleports | reroutes | advisories |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in s["arms"]:
        L.append(f"| **{r['arm']}** | {r['total_vehicle_hours']} | {r.get('vehicle_hours_pct', 0):+.2f} % | "
                 f"{r['mean_travel_time_s']} | {r.get('travel_time_pct', 0):+.2f} % | "
                 f"{r['p95_travel_time_s']} | {r['total_waiting_s']:.0f} | "
                 f"{r.get('waiting_pct', 0):+.2f} % | {r['mean_queue_veh']} | "
                 f"{r['mean_time_loss_s']} | {r['arrived']} | "
                 f"{r['teleports']} | {r['reroutes']} | {r['advisories_delivered']} |")
    if s["verdict"]:
        L += ["", "## Does it actually help?\n",
              "| arm | per-seed veh-h % | seeds improved | claim |", "|---|---|---|---|"]
        for arm, v in s["verdict"].items():
            L.append(f"| {arm} | {v['per_seed_pct']} | {v['seeds_improved']} | "
                     f"**{v['claim']}** — {v['why']} |")
    else:
        L += ["", "One seed only: no per-seed agreement can be claimed from this run.\n"]
    L += ["", "All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a "
              "measurement of the real road. The live feed supplies the congestion state; the "
              "demand is the project's calibrated synthetic demand.\n",
          f"Regenerate: `{rec['command']}`.\n"]
    out.write_text("\n".join(L))
    return out


def scenario_levels(spec: str, res: dict) -> tuple[dict, str]:
    """The congestion the SUMO scenario reproduces — in EVERY arm, so only routing differs.

    `observed` takes it from the recorded observation at the forecast's as-of bin, which is the
    state the model was forecasting FROM. Anything else is an explicit counterfactual the caller
    stated, and is labelled as one.
    """
    spec = (spec or "observed").strip()
    if spec.lower() in ("observed", "auto"):
        obs = (res.get("observed") or {}).get("levels")
        if not obs:
            raise SystemExit("--levels observed needs the recorded forecast source (the API path "
                             "carries derived speeds, not the congestion class); pass explicit "
                             "levels like karwanbazar_to_shahbagh=3")
        return {k: float(v) for k, v in obs.items()}, (
            "REAL_LIVE congestion classes observed at the forecast's as-of bin")
    return ({k: float(v) for k, v in (kv.split("=") for kv in spec.split(","))},
            "STATED COUNTERFACTUAL levels passed on the command line")


def new_run_id(tag: str = "") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"chain_{stamp}{('_' + tag.strip('_')) if tag else ''}_{uuid.uuid4().hex[:6]}"


DEFAULTS = dict(seeds="11", horizon=1800, horizon_min=15, compliance=0.3, v2x="ideal",
                city="dhaka", model=None, api="http://127.0.0.1:8000", source="recorded",
                as_of="peak", levels="observed", tag="", scale=None, net=None, routes=None,
                forecast_kind="model", coverage_hops=0)

# What the prediction arm is allowed to route on. This is the forecast-QUALITY ablation: the
# same chain, the same seeds, only the forecast changes — so the outcome difference is
# attributable to forecast quality and nothing else.
FORECAST_KINDS = {
    "model":   "the registry's model (or --model), run over real recorded history",
    "oracle":  "the truth: this seed's own baseline edge travel times — the ceiling",
    "random":  "uniform random congestion level per corridor, seeded — the floor",
}


def randomise_forecast(res: dict, seed: int) -> dict:
    """Replace the model's values with seeded uniform levels in [0, 3]. Same shape, no skill."""
    import numpy as np
    f = res.get("forecast")
    if not f:
        return res
    rng = np.random.default_rng(seed)
    f["values"] = {h: [round(float(x), 3) for x in rng.uniform(0.0, 3.0, len(f["node_ids"]))]
                   for h in f["values"]}
    f["model"] = "random"
    f["checkpoint"] = None
    f["is_baseline"] = True
    f["provenance"] = {"method": f"uniform random levels, seed {seed}",
                       "why_reported": "the floor: routing on a forecast with no information"}
    res["model_used"] = "random"
    res["is_baseline"] = True
    return res


def run_chain(progress=None, **opts) -> dict:
    """The whole chain, once, as a function: forecast -> edge costs -> arms -> measured metrics.

    Every number in the returned record comes from THIS execution. Nothing is read back from a
    previous run, and the record is written to results/routing/runs/<run_id>/ as it is produced so
    a caller polling the run sees real progress rather than a finished file appearing at the end.
    """
    cfg = {**DEFAULTS, **{k: v for k, v in opts.items() if v is not None}}
    sc = RESULTS / "SCALE_CHOICE.json"
    if cfg["scale"] is None:
        cfg["scale"] = json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25
    cfg["net"] = cfg["net"] or str(pr.DEFAULT_NET)
    cfg["routes"] = cfg["routes"] or str(pr.DEFAULT_ROUTES)
    # a tag names a family of runs in results/routing/integrated_chain<tag>.json; keep the "_"
    cfg["tag"] = ("_" + cfg["tag"].lstrip("_")) if cfg["tag"] else ""
    a = argparse.Namespace(**cfg)
    seeds = [int(x) for x in str(a.seeds).split(",") if str(x).strip()]

    run_id = cfg.get("run_id") or new_run_id(a.tag)
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    command = ("python src/pipeline/routing/integrated_chain.py "
               f"--seeds {a.seeds} --horizon {a.horizon} --v2x {a.v2x} --source {a.source} "
               f"--as-of {a.as_of} --levels {a.levels}")
    state = {"run_id": run_id, "status": "running", "stage": "forecast",
             "started_utc": datetime.now(timezone.utc).isoformat(), "config": cfg,
             "command": command, "arms_done": 0, "arms_total": len(seeds) * len(ARMS)}

    def emit(**kw):
        state.update(kw)
        tmp = run_dir / "status.json.tmp"
        tmp.write_text(json.dumps(state, indent=1, default=str))
        tmp.replace(run_dir / "status.json")           # atomic: a poller never sees a torn file
        if progress:
            progress(dict(state))

    emit()
    t_start = time.time()

    # 1. FORECAST — a real model, run now, over real observations
    print(f"[chain] run {run_id}")
    print("[chain] 1/4 forecast")
    if a.forecast_kind not in FORECAST_KINDS:
        raise SystemExit(f"unknown forecast kind {a.forecast_kind!r}; have {sorted(FORECAST_KINDS)}")
    res = fetch_forecast(a.city, a.horizon_min, a.model, a.api, a.source, a.as_of)
    if a.forecast_kind == "random":
        res = randomise_forecast(res, seeds[0])
    net = ensure_net(Path(a.net))
    table = build_table(res, a.horizon_min, net, int(a.coverage_hops))
    weights = run_dir / "forecast_weights.xml"
    write_weights(table, weights, 0.0, float(a.horizon))
    (run_dir / "forecast_table.json").write_text(json.dumps(table, indent=1, default=str))
    fc = table["forecast"]
    inp = (res.get("input") or {})
    fin = (f"{inp.get('shape')} over {inp.get('nodes')} nodes, {inp.get('unit')}, "
           f"{inp.get('reality')}, up to {inp.get('last_utc')}")
    print(f"        {fc['model']} (baseline={fc['is_baseline']}), input {fin}")
    print(f"        {table.get('priced_edges', table['covered_edges'])} edges priced, "
          f"{table['covered_edges']}/{table['mapped_edges']} corridor edges ({table['pricing']['rule']})")
    emit(stage="v2x", forecast=fc, forecast_input=fin,
         coverage={"covered": table["covered_edges"], "mapped": table["mapped_edges"]})

    # 2. V2X condition -> how many advisories actually arrive
    print("[chain] 2/4 v2x")
    deliver_p, v2x = delivery_fraction(a.v2x)
    print(f"        {a.v2x}: delivery {deliver_p}")

    # 3. congestion made real in every arm
    cmap = json.loads((REPO / "data/forecasting/live_dhaka/corridor_edges.json").read_text())
    levels, levels_source = scenario_levels(a.levels, res)
    slow = lc.affected_edges(levels, cmap)
    print(f"[chain] 3/4 scenario: {len(slow)} edges congested ({levels_source})")
    emit(stage="sumo", edges_congested=len(slow))

    # 4. the arms, identical everything but the routing rule
    print("[chain] 4/4 SUMO")
    runs = []
    for s in seeds:
        for arm in ARMS:
            runs.append(run_arm(a, arm, s, slow, weights, deliver_p, run_dir))
            emit(arms_done=len(runs), last=runs[-1]["arm"] + f"_s{runs[-1]['seed']}")

    rec = {
        "run_id": run_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "chain": "CITY -> DATA -> FORECAST -> ROUTE COST -> ROUTING -> SUMO",
        "command": command, "config": cfg,
        "forecast": fc, "forecast_source": a.source, "forecast_input": fin,
        "forecast_kind": a.forecast_kind, "forecast_kind_meaning": FORECAST_KINDS[a.forecast_kind],
        "forecast_input_detail": inp,
        "observed": table.get("observed"),
        "coverage": {"covered": table["covered_edges"], "mapped": table["mapped_edges"],
                     "priced": table.get("priced_edges"), "hops": int(a.coverage_hops)},
        "pricing": table["pricing"],
        "predicted_speeds": table.get("predicted_speeds"),
        "predicted_levels": table.get("predicted_levels"),
        "weights_file": str(weights.relative_to(REPO)),
        "v2x": v2x, "delivery_fraction": deliver_p,
        "network": Path(a.net).name, "demand": "DHAKA_SIMULATED_DEMAND",
        "routes_file": str(Path(a.routes).name), "scale": a.scale,
        "edges_congested": len(slow), "compliance": a.compliance, "horizon_s": a.horizon,
        "seeds": seeds, "levels": levels, "levels_source": levels_source,
        "sumo": subprocess.run(["sumo", "--version"], capture_output=True, text=True
                               ).stdout.split("\n")[0],
        "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, cwd=REPO).stdout.strip(),
        "wall_s": round(time.time() - t_start, 1),
        "label": "SIMULATED COUNTERFACTUAL — not a live-road outcome",
        "runs": runs, "summary": summarise(runs),
    }
    (run_dir / "run.json").write_text(json.dumps(rec, indent=1, default=str))
    write_report(rec, run_dir / "report.md")
    # the dashboard reads the tagged file; keep it pointing at the newest run of that tag
    (RESULTS / f"integrated_chain{a.tag}.json").write_text(json.dumps(rec, indent=1, default=str))
    write_report(rec, RESULTS / f"integrated_chain{a.tag}.md")
    (RUNS / "LATEST").write_text(run_id + "\n")
    emit(status="done", stage="done", finished_utc=rec["generated_utc"], wall_s=rec["wall_s"],
         summary=rec["summary"])
    print(f"\n[chain] wrote {(run_dir / 'run.json').relative_to(REPO)}")
    for arm, v in rec["summary"]["verdict"].items():
        print(f"[chain] {arm}: {v['claim']} ({v['seeds_improved']} seeds)")
    return rec


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
    p.add_argument("--source", default="recorded", choices=["recorded", "api"],
                   help="where the forecast input comes from: the recorded REAL_LIVE window on "
                        "disk (default, self-contained) or the running backend's rolling buffer")
    p.add_argument("--as-of", default="peak",
                   help="recorded source: which bin the forecast is made at — "
                        "'peak' (busiest observed), 'latest', a bin index, or an ISO timestamp")
    p.add_argument("--levels", default="observed",
                   help="'observed' (the recorded state at the as-of bin) or explicit "
                        "corridor=level pairs")
    p.add_argument("--forecast-kind", default="model", choices=sorted(FORECAST_KINDS),
                   help="what the prediction arm routes on: model | oracle (truth) | random")
    p.add_argument("--coverage-hops", type=int, default=0,
                   help="carry each corridor's forecast to edges within N connections (0 = corridors only)")
    p.add_argument("--tag", default="")
    p.add_argument("--run-id", default=None)
    p.add_argument("--scale", type=float, default=None)
    p.add_argument("--net", default=None)
    p.add_argument("--routes", default=None)
    a = p.parse_args()
    run_chain(**{k: v for k, v in vars(a).items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
