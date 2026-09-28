#!/usr/bin/env python3
"""R2 — ROUTE-DECISION SENSITIVITY of the production optimizer, before any SUMO outcome.

Same network, same demand, same O/Ds, same seed, same horizon, same compliance. Only the forecast
arm and the spatial coverage change:

    arms      ORACLE (measured baseline edge times), Chronos-Bolt, persistence, historical_average,
              random, and STID / GWNet where the registry admits them for this data
    coverage  0-hop (corridor edges only), 1-hop, 2-hop DERIVED propagation

For every arm x coverage the PRODUCTION cost builder (src/pipeline/routing/edge_costs.py) and the
PRODUCTION candidate generator + admission (src/pipeline/routing/route_optimizer.py) run over the
equipped vehicles of the demand, and the table records: raw forecast hash, future edge-cost hash,
priced edge count, % edge costs differing from persistence, candidate count, selected-routes hash,
% best paths and % decisions differing from persistence and from oracle, Jaccard, top-route share,
top-edge concentration — and the first stage where two arms become identical (the collapse point).

    python src/pipeline/routing/r2_sensitivity.py --seed 11 --horizon 1800 --compliance 0.3
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from traffictwin.optimization import edge_costs as ec              # noqa: E402
from traffictwin.protocols.chains import integrated_chain as ic       # noqa: E402
from traffictwin.digital_twin import runtime as pr     # noqa: E402
from traffictwin.optimization import route_optimizer as ro        # noqa: E402
from traffictwin.optimization.forecast_costs import corridor_records, fetch_forecast  # noqa: E402
from traffictwin.protocols.chains.predeparture_arm import read_routes  # noqa: E402
from experiments.routing.predeparture_sensitivity import find_baseline_edgedata  # noqa: E402

OUT = REPO / "results/routing/r2_route_decisions"
ARMS = [("oracle", None), ("Chronos-Bolt", "Chronos-Bolt"), ("persistence", "persistence"),
        ("historical_average", "historical_average"), ("random", "random"), ("STID", "STID"), ("GWNet", "GWNet")]
HOPS = (0, 1, 2)


def jaccard(a: list[str] | None, b: list[str] | None) -> float:
    if not a or not b:
        return 0.0
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb)


def forecast_values(label: str, model: str | None, a) -> tuple[dict | None, dict]:
    """The raw forecast for an arm, or the refusal reason. Random is seeded from the run seed."""
    try:
        res = fetch_forecast(a.city, a.horizon_min, None if label == "random" else model, a.api, a.source, a.as_of)
        if label == "random":
            res = ic.randomise_forecast(res, a.seed)
        f = res.get("forecast")
        if not f:
            reason = str((res.get("decision") or {}).get("reason"))
            if "not a registered model" in reason:          # ask the registry's own gates why the graph models refuse this data
                try:
                    from traffictwin.forecasting.adapters.registry import available_for
                    from traffictwin.optimization.forecast_costs import recorded_city_data
                    cd, _obs = recorded_city_data(a.city, a.as_of)
                    gates = [m for m in available_for(cd) if m["model"].split("/")[0] == model]
                    reason = "; ".join(f"{m['model']}: {', '.join(m.get('reasons') or ['refused'])}" for m in gates) or reason
                except Exception as exc:                      # noqa: BLE001
                    reason += f" ({type(exc).__name__}: {exc})"
            return None, {"status": "REFUSED: " + reason[:240]}
        if model and label != "random" and f.get("model") != model:
            return None, {"status": f"REFUSED: registry served {f.get('model')} instead of {model}"}
        vals = f["values"].get(a.horizon_min) or f["values"].get(str(a.horizon_min))
        return {"values": dict(zip(f["node_ids"], [float(v) for v in vals])), "unit": f["unit"], "model": f["model"],
                "checkpoint": f.get("checkpoint")}, {"status": "ok"}
    except BaseException as exc:                    # noqa: BLE001 - recorded, never hidden
        return None, {"status": f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}"}


def run(a) -> dict:
    net = Path(a.net)
    cmap = corridor_records()
    cfg = ec.load_config()
    veh = read_routes(Path(a.routes))
    trips = [{"id": v, "from": r.split()[0], "to": r.split()[-1], "depart": float(d), "current_route": r.split()}
             for v, d, r in veh if pr.equipped(v, a.compliance) and float(d) < a.horizon]
    if a.limit:
        trips = trips[: a.limit]
    oracle_ed = find_baseline_edgedata(a.seed, a.net, a.routes)
    forecasts, status = {}, {}
    for label, model in ARMS:
        if label == "oracle":
            status[label] = {"status": "ok" if oracle_ed else "no baseline run of this seed on this net/demand — run the chain once first"}
            continue
        fv, st = forecast_values(label, model, a)
        forecasts[label], status[label] = fv, st
    rows: dict[tuple[str, int], dict] = {}
    records: dict[tuple[str, int], dict] = {}
    best_paths: dict[tuple[str, int], dict] = {}
    for hops in HOPS:
        for label, _model in ARMS:
            if status[label]["status"] != "ok":
                continue
            if label == "oracle" and hops != HOPS[0]:
                continue                                    # measured everywhere: coverage does not apply
            t0 = time.time()
            out = OUT / f"s{a.seed}" / f"h{hops}" / label
            if label == "oracle":
                table = ec.oracle_table(oracle_ed, net, cfg)
            else:
                fv = forecasts[label]
                table = ec.build(fv["values"], fv["unit"], cmap, net, a.horizon_min, cfg, hops, fv["model"], analysis_run_id=f"r2_s{a.seed}")
            rec = ro.optimize(net, trips, table, out, a.seed, a.horizon, cfg, keep_candidates=False)
            records[(label, hops)] = rec
            alt0 = out / "alt_0.rou.xml"
            best_paths[(label, hops)] = {v: r.split() for v, r in ro.VEH_RE.findall(alt0.read_text())} if alt0.exists() else {}
            s = rec["stats"]
            rows[(label, hops)] = {"arm": label, "coverage_hops": None if label == "oracle" else hops, "model_served": table.get("model"),
                                   "raw_forecast_hash": table["raw_forecast_hash"], "future_cost_hash": table["future_cost_hash"],
                                   "priced_edges": table["priced_edges"], "direct_edges": table["direct_edges"], "derived_edges": table["derived_edges"],
                                   "candidate_sets_hash": rec["candidate_sets_hash"], "candidate_costs_hash": rec["candidate_costs_hash"],
                                   "selected_routes_hash": rec["selected_routes_hash"], "mean_candidates_real": s["mean_candidates_real"],
                                   "vehicles": s["vehicles"], "advised_above_threshold": s["advised_above_threshold"], "admitted": s["vehicles_admitted"],
                                   "rejected_capacity": s["rejected_by_capacity_gate"], "rejected_share": s["rejected_by_share_gate"],
                                   "top_route_share": s["top_route_share"], "top_edge_concentration": s["top_edge_flow_concentration"],
                                   "decisions": s["decisions"], "wall_s": round(time.time() - t0, 1)}
            print(f"[r2] {label:<18} hops={hops} priced={table['priced_edges']:<5} cand={s['mean_candidates_real']:.2f} "
                  f"admitted={s['vehicles_admitted']:<5} cost={table['future_cost_hash']} sel={rec['selected_routes_hash']} ({rows[(label, hops)]['wall_s']}s)", flush=True)
    # ---- comparisons against persistence (same coverage) and oracle
    def tab(key):
        return records[key]["selected_routes"]
    def pct_edge_costs_differ(x, y):
        ex, ey = _edge_tt(x), _edge_tt(y)
        keys = set(ex) | set(ey)
        return round(100 * sum(1 for e in keys if ex.get(e) != ey.get(e)) / len(keys), 2) if keys else 0.0
    def mean_abs_pct_cost_diff(x, y):
        ex, ey = _edge_tt(x), _edge_tt(y)
        common = [e for e in ex if e in ey and ey[e]]
        return round(float(np.mean([abs(ex[e] - ey[e]) / ey[e] * 100 for e in common])), 2) if common else None
    def pct_differ(x, y, which):
        A = tab(x) if which == "selected" else best_paths[x]
        B = tab(y) if which == "selected" else best_paths[y]
        ids = set(A) & set(B)
        return round(100 * sum(1 for v in ids if A[v] != B[v]) / len(ids), 2) if ids else None
    def mean_jaccard(x, y):
        A, B = tab(x), tab(y)
        ids = set(A) & set(B)
        return round(float(np.mean([jaccard(A[v], B[v]) for v in ids])), 4) if ids else None
    def _edge_tt(key):
        rr = OUT / f"s{a.seed}" / f"h{key[1]}" / key[0] / "future_weights.xml"
        if not rr.exists():
            return {}
        return {m.group(1): float(m.group(2)) for m in re.finditer(r'<edge id="([^"]+)" traveltime="([^"]+)"', rr.read_text())}
    for (label, hops), row in rows.items():
        pk, ok_ = ("persistence", hops), ("oracle", HOPS[0])
        if pk in rows and label != "persistence":
            row["pct_edge_costs_differ_vs_persistence"] = pct_edge_costs_differ((label, hops), pk)
            row["mean_abs_pct_cost_diff_vs_persistence"] = mean_abs_pct_cost_diff((label, hops), pk)
            row["pct_best_path_differs_vs_persistence"] = pct_differ((label, hops), pk, "best")
            row["pct_decisions_differ_vs_persistence"] = pct_differ((label, hops), pk, "selected")
            row["mean_jaccard_vs_persistence"] = mean_jaccard((label, hops), pk)
        if ok_ in rows and label != "oracle":
            row["pct_decisions_differ_vs_oracle"] = pct_differ((label, hops), ok_, "selected")
            row["mean_jaccard_vs_oracle"] = mean_jaccard((label, hops), ok_)
    # ---- collapse point per coverage among the forecast arms
    collapse = {}
    for hops in HOPS:
        arms = [l for (l, h), r in rows.items() if h == hops and l != "oracle"]
        stages = {"raw_forecast": "raw_forecast_hash", "edge_costs": "future_cost_hash", "candidate_sets": "candidate_sets_hash",
                  "candidate_costs": "candidate_costs_hash", "selected_routes": "selected_routes_hash"}
        per = {}
        for st, key in stages.items():
            groups: dict[str, list[str]] = {}
            for l in arms:
                groups.setdefault(rows[(l, hops)][key], []).append(l)
            per[st] = {"distinct": len(groups), "identical_groups": [g for g in groups.values() if len(g) > 1]}
        first = next((st for st in stages if per[st]["distinct"] < len(arms)), None)
        chr_rand = None
        if ("Chronos-Bolt", hops) in rows and ("random", hops) in rows:
            chr_rand = {"edge_costs_identical": rows[("Chronos-Bolt", hops)]["future_cost_hash"] == rows[("random", hops)]["future_cost_hash"],
                        "selected_routes_identical": rows[("Chronos-Bolt", hops)]["selected_routes_hash"] == rows[("random", hops)]["selected_routes_hash"],
                        "pct_decisions_differ": pct_differ(("Chronos-Bolt", hops), ("random", hops), "selected"),
                        "pct_best_path_differ": pct_differ(("Chronos-Bolt", hops), ("random", hops), "best")}
        collapse[hops] = {"arms": arms, "stages": per, "first_collapse_stage": first, "chronos_vs_random": chr_rand}
    return {"seed": a.seed, "horizon_s": a.horizon, "horizon_min": a.horizon_min, "compliance": a.compliance, "as_of": a.as_of,
            "net": str(net), "routes": str(a.routes), "vehicles": len(trips), "config": cfg, "arm_status": status,
            "rows": [rows[k] for k in rows], "collapse": {str(k): v for k, v in collapse.items()},
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def markdown(res: dict) -> str:
    L = [f"# R2 — route-decision sensitivity (seed {res['seed']}, horizon {res['horizon_s']} s, forecast +{res['horizon_min']} min, "
         f"compliance {res['compliance']}, {res['vehicles']} equipped vehicles, as-of {res['as_of']})", "",
         "Production cost builder (`src/pipeline/routing/edge_costs.py`) and optimizer (`src/pipeline/routing/route_optimizer.py`); "
         f"config hash `{res['config']['_config_hash']}`.", "",
         "| arm | hops | priced edges (direct+derived) | raw forecast hash | edge-cost hash | % costs ≠ persistence | mean |Δcost| % | cand/veh | admitted | "
         "% best path ≠ pers. | % decisions ≠ pers. | Jaccard vs pers. | % decisions ≠ oracle | Jaccard vs oracle | top-route share | top-edge conc. |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    g = lambda r, k: ("—" if r.get(k) is None else r.get(k))
    for r in res["rows"]:
        L.append(f"| {r['arm']} | {g(r, 'coverage_hops') if r['arm'] != 'oracle' else 'all (measured)'} | {r['priced_edges']} ({r['direct_edges']}+{r['derived_edges']}) | "
                 f"`{r['raw_forecast_hash'][:10]}` | `{r['future_cost_hash'][:10]}` | {g(r, 'pct_edge_costs_differ_vs_persistence')} | {g(r, 'mean_abs_pct_cost_diff_vs_persistence')} | "
                 f"{r['mean_candidates_real']} | {r['admitted']}/{r['vehicles']} | {g(r, 'pct_best_path_differs_vs_persistence')} | {g(r, 'pct_decisions_differ_vs_persistence')} | "
                 f"{g(r, 'mean_jaccard_vs_persistence')} | {g(r, 'pct_decisions_differ_vs_oracle')} | {g(r, 'mean_jaccard_vs_oracle')} | {r['top_route_share']} | {r['top_edge_concentration']} |")
    L += ["", "## Refused arms", ""]
    for k, v in res["arm_status"].items():
        if v["status"] != "ok":
            L.append(f"- **{k}**: {v['status']}")
    L += ["", "## Collapse point per coverage", ""]
    for h, c in res["collapse"].items():
        L.append(f"- **{h}-hop**: first stage where two forecast arms become identical: **{c['first_collapse_stage'] or 'none (all arms distinct through selection)'}**; "
                 + "; ".join(f"{st}: {v['distinct']}/{len(c['arms'])} distinct" + (f" (identical: {v['identical_groups']})" if v['identical_groups'] else "") for st, v in c["stages"].items())
                 + (f"; Chronos vs random: costs identical={c['chronos_vs_random']['edge_costs_identical']}, selected identical={c['chronos_vs_random']['selected_routes_identical']}, "
                    f"{c['chronos_vs_random']['pct_decisions_differ']} % decisions differ, {c['chronos_vs_random']['pct_best_path_differ']} % best paths differ" if c.get("chronos_vs_random") else ""))
    return "\n".join(L) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--horizon", type=int, default=1800)
    p.add_argument("--horizon-min", type=int, default=15)
    p.add_argument("--compliance", type=float, default=0.3)
    p.add_argument("--city", default="dhaka")
    p.add_argument("--as-of", default="peak")
    p.add_argument("--source", default="recorded")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--net", default=str(pr.DEFAULT_NET))
    p.add_argument("--routes", default=str(pr.DEFAULT_ROUTES))
    p.add_argument("--limit", type=int, default=0, help="only the first N equipped vehicles (0 = all)")
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    res = run(a)
    (REPO / "results/routing/r2_route_decisions.json").write_text(json.dumps(res, indent=1))
    (REPO / "results/routing/r2_route_decisions.md").write_text(markdown(res))
    print(markdown(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
