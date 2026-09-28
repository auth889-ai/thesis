#!/usr/bin/env python3
"""Does forecast QUALITY change the routing outcome? The one experiment that answers it.

    python src/pipeline/routing/forecast_quality_ablation.py --seeds 11,12,13,14,15

Four forecasts go through the SAME chain — same network, demand, seeds, congestion scenario,
compliance, V2X condition. Only what the prediction arm routes on changes:

    oracle        this seed's own baseline truth        the ceiling any forecast could reach
    Chronos-Bolt  the real pretrained model              what the system actually has
    persistence   last observed value held flat          the floor a model must beat
    random        seeded uniform noise                   a forecast with no information

Reading the result, in this order:
    oracle does not beat baseline  -> these corridors cannot benefit from ANY forecast at this
                                      compliance; the limit is the scenario, not the model
    oracle beats, Chronos does not -> forecast accuracy IS the bottleneck; better models would pay
    Chronos ~ oracle               -> the forecast is already good enough; routing is the limit

Every number is measured by SUMO in this run; the per-seed agreement rule from integrated_chain
applies (a mean the seeds do not support is not a result).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from pipeline.routing import integrated_chain as ic     # noqa: E402

RESULTS = REPO / "results/routing"
# label -> (forecast_kind, model)
CONDITIONS = {
    "oracle":       ("oracle", None),
    "Chronos-Bolt": ("model", "Chronos-Bolt"),
    "persistence":  ("model", "persistence"),
    "random":       ("random", None),
}


def paired(rec: dict, arm: str) -> dict:
    """arm vs baseline, per seed, on vehicle-hours — the commensurable objective."""
    by = {(r["arm"], r["seed"]): r["metrics"] for r in rec["runs"]}
    per = []
    for s in rec["seeds"]:
        b, x = by.get(("baseline", s)), by.get((arm, s))
        if b and x:
            per.append(round((x["total_vehicle_hours"] - b["total_vehicle_hours"])
                             / (b["total_vehicle_hours"] or 1) * 100, 2))
    better = sum(1 for v in per if v < 0)
    return {"per_seed_pct": per, "mean_pct": round(sum(per) / len(per), 2) if per else None,
            "seeds_improved": f"{better}/{len(per)}",
            "claim": "IMPROVES" if per and better == len(per) else "NOT_ESTABLISHED"}


VEH_RE = re.compile(r'<vehicle id="([^"]+)"[^>]*>\s*<route[^>]*edges="([^"]+)"', re.S)


def route_sensitivity(runs: dict[str, str], seed: int) -> dict:
    """Did the forecast actually reach the router? Count vehicles whose ADVISED route differs
    between forecasts, on one seed. If two forecasts with different numbers produce the same
    routes, the routing decision is not sensitive to the forecast in that range, and no accuracy
    gain could have changed the outcome — the coverage of the priced edges is the limit, not
    the model."""
    advised = {}
    for label, rid in runs.items():
        f = ic.RUNS / rid / f"prediction_aware_s{seed}" / "routes_advised.rou.xml"
        if f.exists():
            advised[label] = dict(VEH_RE.findall(f.read_text()))
    labels = list(advised)
    pair = {}
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            ids = set(advised[a]) & set(advised[b])
            pair[f"{a} vs {b}"] = sum(1 for v in ids if advised[a][v] != advised[b][v])
    return {"seed": seed, "advised_vehicles": {k: len(v) for k, v in advised.items()},
            "vehicles_routed_differently": pair,
            "how_to_read": ("0 between two forecasts = the router made identical decisions on "
                            "both; the forecast's numbers never reached the road")}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seeds", default="11,12,13,14,15")
    p.add_argument("--horizon", type=int, default=1800)
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--v2x", default="ideal")
    p.add_argument("--as-of", default="peak")
    p.add_argument("--conditions", default=",".join(CONDITIONS))
    p.add_argument("--hops", default="0",
                   help="pricing coverage levels to test, e.g. 0,3,8 (corridor edges only = 0)")
    p.add_argument("--out", type=Path, default=RESULTS / "ablation_forecast_quality.json")
    p.add_argument("--from-json", action="store_true",
                   help="recompute the reading and the markdown from --out's existing JSON, no SUMO")
    a = p.parse_args()

    rows, runs = [], {}
    hops_list = [int(x) for x in a.hops.split(",")]
    if a.from_json:
        prev = json.loads(a.out.read_text())
        rows, runs, hops_list = prev["rows"], prev["runs"], prev.get("coverage_hops", hops_list)
        a.conditions = ",".join(dict.fromkeys(r["forecast"] for r in rows))
    for hops in ([] if a.from_json else hops_list):
      for label in a.conditions.split(","):
        kind, model = CONDITIONS[label]
        print(f"\n[ablation] ===== hops={hops} {label}: {ic.FORECAST_KINDS[kind]} =====", flush=True)
        rec = ic.run_chain(seeds=a.seeds, horizon=a.horizon, compliance=a.compliance, v2x=a.v2x,
                           as_of=a.as_of, forecast_kind=kind, model=model, coverage_hops=hops,
                           tag=f"abl_h{hops}_{label.lower().replace('-', '')}")
        arms = {r["arm"]: r for r in rec["summary"]["arms"]}
        pa = arms["prediction_aware"]
        rows.append({
            "forecast": label, "kind": kind, "meaning": ic.FORECAST_KINDS[kind],
            "coverage_hops": hops, "priced_edges": rec["coverage"].get("priced"),
            "run_id": rec["run_id"],
            "model_reported": rec["forecast"]["model"],
            "baseline_vehicle_hours": arms["baseline"]["total_vehicle_hours"],
            "reactive_vehicle_hours": arms["reactive"]["total_vehicle_hours"],
            "prediction_aware_vehicle_hours": pa["total_vehicle_hours"],
            "prediction_aware": {k: pa[k] for k in ("mean_travel_time_s", "p95_travel_time_s",
                                                    "total_waiting_s", "mean_queue_veh", "arrived",
                                                    "teleports", "reroutes")},
            "vs_baseline": paired(rec, "prediction_aware"),
            "reactive_vs_baseline": paired(rec, "reactive"),
        })
        runs[f"{label}@{hops}"] = rec["run_id"]

    # the reading, stated by the numbers rather than by us — at the smallest coverage first,
    # then whether growing the coverage lets the router tell the forecasts apart
    seed0 = int(a.seeds.split(",")[0])
    base_hops = hops_list[0]
    base_rows = [r for r in rows if r["coverage_hops"] == base_hops]
    claims = {r["forecast"]: r["vs_baseline"]["claim"] for r in base_rows}
    means = {r["forecast"]: r["vs_baseline"]["mean_pct"] for r in base_rows}
    by_hops = {}
    for h in hops_list:
        by_hops[h] = route_sensitivity({k.split("@")[0]: v for k, v in runs.items()
                                        if k.endswith(f"@{h}")}, seed0)
    sens = by_hops[base_hops]
    model_vs_random = sens["vehicles_routed_differently"].get("Chronos-Bolt vs random")
    coverage_reading = None
    if len(hops_list) > 1:
        diverge = {h: by_hops[h]["vehicles_routed_differently"].get("Chronos-Bolt vs random")
                   for h in hops_list}
        top = hops_list[-1]
        top_rows = {r["forecast"]: r for r in rows if r["coverage_hops"] == top}
        c, rnd = top_rows.get("Chronos-Bolt"), top_rows.get("random")
        if diverge.get(top):
            gap = (c["vs_baseline"]["mean_pct"] - rnd["vs_baseline"]["mean_pct"]) if c and rnd else None
            better = c["vs_baseline"]["claim"] == "IMPROVES" and rnd["vs_baseline"]["claim"] != "IMPROVES"
            coverage_reading = (f"growing the priced coverage to {top} hops "
                                f"({top_rows['Chronos-Bolt']['priced_edges']} edges) makes the router "
                                f"route {diverge[top]} vehicles differently for the model than for "
                                f"noise, so coverage WAS the first bottleneck"
                                + (f"; with the forecast now reaching the road, the model's outcome is "
                                   f"{gap:+.2f} pp relative to noise — "
                                   + ("it beats noise in every seed: forecast quality matters once coverage allows it"
                                      if better else
                                      "it does NOT beat noise, consistent with its negative skill against "
                                      "persistence (E1): the second bottleneck is the model itself")
                                   if gap is not None else ""))
        else:
            coverage_reading = (f"even at {top} hops the router still cannot tell the model from "
                                f"noise; coverage alone does not let forecast quality through")
    if model_vs_random == 0:
        reading = ("the real model and RANDOM noise produced identical routes: the forecast's "
                   "numbers never reached the router. With only the mapped corridor edges priced, "
                   "the route decision is insensitive to forecast magnitude in the plausible "
                   "range, so no accuracy gain could change the outcome — pricing COVERAGE is "
                   "the bottleneck, not the model")
    elif claims.get("oracle") != "IMPROVES":
        reading = ("even the ORACLE forecast does not improve every seed: at this compliance and "
                   "scenario the corridors cannot benefit from a forecast, so no model could")
    elif claims.get("Chronos-Bolt") != "IMPROVES":
        reading = ("the oracle improves every seed and the real model does not: forecast accuracy "
                   "is the bottleneck between prediction and control")
    else:
        reading = ("the real model improves every seed like the oracle: the forecast is good "
                   "enough and routing is the limit")

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "question": "does forecast quality change the routing outcome?",
        "held_fixed": {"seeds": a.seeds, "horizon_s": a.horizon, "compliance": a.compliance,
                       "v2x": a.v2x, "as_of": a.as_of, "scenario": "observed levels at as-of"},
        "objective": "total vehicle-hours, prediction_aware vs baseline, paired per seed",
        "rows": rows, "mean_pct_by_forecast": means, "claims": claims,
        "coverage_hops": hops_list, "route_sensitivity": sens, "route_sensitivity_by_hops": by_hops,
        "reading": reading, "coverage_reading": coverage_reading,
        "runs": runs, "label": "SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin",
        "command": f"python src/pipeline/routing/forecast_quality_ablation.py --seeds {a.seeds}",
    }
    a.out.write_text(json.dumps(out, indent=1, default=str))
    md = [f"# Forecast-quality ablation — {a.seeds}, compliance {a.compliance:.0%}, V2X {a.v2x}\n",
          "| coverage (hops) | priced edges | forecast | veh-h (pred. arm) | vs baseline mean | per seed | seeds improved | claim |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        v = r["vs_baseline"]
        md.append(f"| {r['coverage_hops']} | {r['priced_edges']} | **{r['forecast']}** | {r['prediction_aware_vehicle_hours']} | "
                  f"{v['mean_pct']:+.2f} % | {v['per_seed_pct']} | {v['seeds_improved']} | {v['claim']} |")
    md += ["", f"Reactive (no forecast) vs baseline: {rows[0]['reactive_vs_baseline']['mean_pct']:+.2f} % "
               f"mean, {rows[0]['reactive_vs_baseline']['seeds_improved']} seeds improved.", "",
           f"## Did the forecast reach the router? (seed {seed0})", "",
           "| coverage (hops) | forecasts compared | vehicles routed differently |", "|---|---|---|"]
    for h in hops_list:
        md += [f"| {h} | {k} | {v} |" for k, v in by_hops[h]["vehicles_routed_differently"].items()]
    md += [""] + ([f"**Coverage.** {coverage_reading}.", ""] if coverage_reading else []) + [
           f"**Reading.** {reading}.", "",
           "SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin. Every number in this table was "
           "measured by SUMO in the runs listed in the JSON.\n"]
    a.out.with_suffix(".md").write_text("\n".join(md))
    print("\n" + "\n".join(md))
    print(f"[ablation] wrote {a.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
