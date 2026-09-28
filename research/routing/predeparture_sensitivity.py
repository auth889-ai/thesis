#!/usr/bin/env python3
"""R1 — FORECAST-TO-ACTION SENSITIVITY AUDIT: do different forecasts reach different route decisions?

    python src/pipeline/routing/r1_sensitivity.py --seed 11 --hops 0,8

Same network, demand, OD set, seed, horizon, compliance and V2X condition as the chain
(`integrated_chain.DEFAULTS`). Only the forecast changes:

    oracle      this seed's own baseline edge travel times (the ceiling)      -> from an existing baseline run
    GWNet/STID  requested from the registry: on Dhaka's 6 recorded corridors they REFUSE (recorded here)
    Chronos     the registry model over the recorded history
    persistence the last observed class holds
    historical_average
    random      seeded uniform classes (the floor)

For every one, the chain's own stages are executed and hashed:

    forecast (raw values)  ->  mapped SUMO-edge forecast (which corridor edges are priced, and with
    which class/multiplier)  ->  future edge-cost table  ->  duarouter candidate paths with their
    costs (the .alt.xml it writes)  ->  selected route per advised vehicle

and compared between forecasts: % edges whose cost differs, % vehicles whose selected route
differs, mean per-vehicle Jaccard overlap of route edges, and the share of route-edge use on the
20 busiest edges. The stage at which two forecasts become identical is the collapse point.

Nothing new is routed here: pricing is `forecast_to_costs.build_table`, routing is
`integrated_chain.predeparture_routes` (duarouter on the weight file), exactly as in the chain.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import app.twin.runtime as pr                        # noqa: E402
from app.protocols.chains import integrated_chain as ic                     # noqa: E402
from app.protocols.chains import live_chain as lc                           # noqa: E402
from app.routing.forecast_costs import build_table, fetch_forecast, write_weights  # noqa: E402
from app.twin.network_file import ensure_net                       # noqa: E402

RESULTS = REPO / "results/routing"
OUT = RESULTS / "r1_forecast_to_action"
KINDS = [("oracle", None), ("GWNet", "GWNet"), ("STID", "STID"), ("Chronos-Bolt", "Chronos-Bolt"),
         ("persistence", "persistence"), ("historical_average", "historical_average"), ("random", None)]
ROUTE_ALT_RE = re.compile(r'<vehicle id="([^"]+)"[^>]*>(.*?)</vehicle>', re.S)
ALT_RE = re.compile(r'<route cost="([0-9.eE+-]+)" probability="([0-9.eE+-]+)" edges="([^"]+)"')


def h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def jaccard(a: str, b: str) -> float:
    A, B = set(a.split()), set(b.split())
    return len(A & B) / len(A | B) if A | B else 1.0


def concentration(routes: dict[str, str], k: int = 20) -> float:
    counts: dict[str, int] = {}
    for r in routes.values():
        for e in r.split():
            counts[e] = counts.get(e, 0) + 1
    total = sum(counts.values())
    return round(sum(sorted(counts.values(), reverse=True)[:k]) / total, 4) if total else 0.0


def parse_alternatives(alt: Path) -> dict[str, list[tuple[float, str]]]:
    out = {}
    if not alt.exists():
        return out
    for vid, body in ROUTE_ALT_RE.findall(alt.read_text()):
        out[vid] = [(float(c), e) for c, _p, e in ALT_RE.findall(body)]
    return out


def find_baseline_edgedata(seed: int, net: str, routes: str) -> Path | None:
    """The oracle: an existing baseline run of this seed on this net/demand (the chain's own)."""
    best = None
    for st in sorted((ic.RUNS).glob("*/status.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            cfg = json.loads(st.read_text()).get("config") or {}
        except json.JSONDecodeError:
            continue
        f = st.parent / f"baseline_s{seed}" / "edgedata.xml"
        if f.exists() and Path(cfg.get("net", "")).name == Path(net).name and Path(cfg.get("routes", "")).name == Path(routes).name:
            best = f
            break
    return best


def run(seed: int, hops: int, a) -> dict:
    net = ensure_net(Path(a.net))
    deliver_p, _ = ic.delivery_fraction(a.v2x)
    oracle = find_baseline_edgedata(seed, a.net, a.routes)
    rows, tables, advised, alts, forecasts = {}, {}, {}, {}, {}
    for label, model in KINDS:
        out = OUT / f"s{seed}_h{hops}" / label
        out.mkdir(parents=True, exist_ok=True)
        row = {"forecast": label}
        if label == "oracle":
            if oracle is None:
                row["status"] = "no baseline run of this seed on this net/demand — run the chain once first"
                rows[label] = row
                continue
            weights = oracle
            row.update(status="ok", source=str(oracle.relative_to(REPO)), raw_forecast_hash="(baseline edge travel times)",
                       mapped_edges=None, priced_edges=None)
            tables[label] = None
        else:
            try:
                res = fetch_forecast(a.city, a.horizon_min, model, a.api, a.source, a.as_of)
                if label == "random":
                    res = ic.randomise_forecast(res, seed)
                f = res.get("forecast")
                if not f:
                    reason = str((res.get("decision") or {}).get("reason"))
                    if "not a registered model" in reason:      # ask the registry's own gates why the graph models refuse
                        try:
                            from app.forecasting.adapters.registry import available_for
                            from app.routing.forecast_costs import recorded_city_data
                            cd = recorded_city_data(a.city); cd = cd[0] if isinstance(cd, tuple) else cd
                            gates = [m for m in available_for(cd) if m["model"].split("/")[0] == model]
                            reason = "; ".join(f"{m['model']}: {', '.join(m.get('reasons') or ['refused'])}" for m in gates) or reason
                        except Exception as exc:              # noqa: BLE001
                            reason += f" ({type(exc).__name__}: {exc})"
                    row["status"] = "REFUSED: " + reason[:220]
                    rows[label] = row
                    continue
                if model and f.get("model") != model and label not in ("random",):
                    row["status"] = f"REFUSED: registry served {f.get('model')} instead of {model} — " + str((res.get("decision") or {}).get("reason"))[:160]
                    rows[label] = row
                    continue
            except BaseException as exc:                    # noqa: BLE001 - recorded, never hidden
                row["status"] = f"REFUSED: {type(exc).__name__}: {str(exc)[:160]}"
                rows[label] = row
                continue
            vals = f["values"].get(str(a.horizon_min)) or f["values"].get(a.horizon_min)
            forecasts[label] = dict(zip(f["node_ids"], [round(float(v), 4) for v in vals]))
            table = build_table(res, a.horizon_min, net, hops)
            tables[label] = table
            weights = out / "forecast_weights.xml"
            write_weights(table, weights, 0.0, float(a.horizon))
            per = table["pricing"].get("per_corridor") or {}
            row.update(status="ok", model_served=f.get("model"), checkpoint=f.get("checkpoint"),
                       raw_forecast_hash=h(forecasts[label]), raw_forecast=forecasts[label],
                       mapped_classes={k: v.get("predicted_level") for k, v in per.items()},
                       mapped_multipliers={k: v.get("multiplier") for k, v in per.items()},
                       mapped_edges=table["mapped_edges"], priced_edges=table["priced_edges"],
                       edge_cost_hash=h(table["edge_travel_times"]))
        ns = argparse.Namespace(**{**vars(a), "forecast_kind": "model"})
        merged, changed, n_advised = ic.predeparture_routes(ns, seed, weights, out, deliver_p)
        adv = {v: r for v, _d, r in lc.VEH_RE.findall((out / "routes_advised.rou.xml").read_text())} if (out / "routes_advised.rou.xml").exists() else {}
        advised[label] = adv
        alts[label] = parse_alternatives(out / "routes_advised.rou.alt.xml")
        row.update(advised_vehicles=n_advised, vehicles_changed_vs_static=changed,
                   selected_routes_hash=h(adv), candidate_sets_hash=h({v: sorted(e for _, e in c) for v, c in alts[label].items()}),
                   candidate_costs_hash=h({v: sorted(round(c, 2) for c, _ in cc) for v, cc in alts[label].items()}),
                   mean_candidates_per_vehicle=round(float(np.mean([len(c) for c in alts[label].values()])), 2) if alts[label] else None,
                   top20_edge_concentration=concentration(adv))
        rows[label] = row
    # ---- pairwise comparisons against persistence (the floor) and oracle (the ceiling)
    edge_costs = {k: (t["edge_travel_times"] if t else None) for k, t in tables.items()}
    def pct_edges_differ(x, y):
        if edge_costs.get(x) is None or edge_costs.get(y) is None:
            return None
        keys = set(edge_costs[x]) | set(edge_costs[y])
        return round(100 * sum(1 for e in keys if edge_costs[x].get(e) != edge_costs[y].get(e)) / len(keys), 2) if keys else 0.0
    def pct_routes_differ(x, y):
        ids = set(advised.get(x, {})) & set(advised.get(y, {}))
        return round(100 * sum(1 for v in ids if advised[x][v] != advised[y][v]) / len(ids), 2) if ids else None
    def mean_jaccard(x, y):
        ids = set(advised.get(x, {})) & set(advised.get(y, {}))
        return round(float(np.mean([jaccard(advised[x][v], advised[y][v]) for v in ids])), 4) if ids else None
    for label, row in rows.items():
        if row.get("status") != "ok":
            continue
        for ref in ("persistence", "oracle"):
            if ref in rows and rows[ref].get("status") == "ok" and ref != label:
                row[f"pct_edge_costs_differ_vs_{ref}"] = pct_edges_differ(label, ref)
                row[f"pct_vehicles_route_differs_vs_{ref}"] = pct_routes_differ(label, ref)
                row[f"mean_jaccard_vs_{ref}"] = mean_jaccard(label, ref)
    # ---- collapse point among the learned / baseline forecasts
    learned = [k for k in ("GWNet", "STID", "Chronos-Bolt", "persistence", "historical_average", "random") if rows.get(k, {}).get("status") == "ok"]
    stages = {"raw_forecast": {k: rows[k]["raw_forecast_hash"] for k in learned},
              "mapped_classes": {k: h(rows[k]["mapped_classes"]) for k in learned},
              "mapped_multipliers": {k: h(rows[k]["mapped_multipliers"]) for k in learned},
              "edge_costs": {k: rows[k]["edge_cost_hash"] for k in learned},
              "candidate_sets": {k: rows[k]["candidate_sets_hash"] for k in learned},
              "candidate_costs": {k: rows[k]["candidate_costs_hash"] for k in learned},
              "selected_routes": {k: rows[k]["selected_routes_hash"] for k in learned}}
    collapse = {}
    for stage, hs in stages.items():
        groups: dict[str, list[str]] = {}
        for k, v in hs.items():
            groups.setdefault(v, []).append(k)
        collapse[stage] = {"distinct": len(groups), "identical_groups": [g for g in groups.values() if len(g) > 1]}
    first = next((s for s in stages if collapse[s]["distinct"] < len(learned)), None)
    return {"seed": seed, "coverage_hops": hops, "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(a).items()},
            "rows": rows, "collapse": collapse, "first_collapse_stage": first,
            "reading": ("the first stage where two different forecasts become identical is where the forecast stops mattering; "
                        "with corridor-only pricing (hops 0) a class change on one of 6 corridors moves the cost of a few edges "
                        "that few advised vehicles use, so different forecasts often reach the same route decisions")}


def sweep(seed: int, hops: int, a) -> dict:
    """Uniform congestion class on all corridors, level 0 .. 3: at which multiplier does the
    router's selected route set change? This locates the step the collapse sits on."""
    net = ensure_net(Path(a.net))
    deliver_p, _ = ic.delivery_fraction(a.v2x)
    base = fetch_forecast(a.city, a.horizon_min, "persistence", a.api, a.source, a.as_of)
    f = base["forecast"]
    out_rows, ref = [], None
    for lv in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
        res = json.loads(json.dumps(base))
        res["forecast"]["values"] = {k: [lv] * len(f["node_ids"]) for k in f["values"]}
        table = build_table(res, a.horizon_min, net, hops)
        out = OUT / f"s{seed}_h{hops}" / f"sweep_{lv}"
        out.mkdir(parents=True, exist_ok=True)
        weights = out / "forecast_weights.xml"; write_weights(table, weights, 0.0, float(a.horizon))
        ns = argparse.Namespace(**{**vars(a), "forecast_kind": "model"})
        ic.predeparture_routes(ns, seed, weights, out, deliver_p)
        adv = {v: r for v, _d, r in lc.VEH_RE.findall((out / "routes_advised.rou.xml").read_text())}
        if ref is None:
            ref = adv
        ids = set(ref) & set(adv)
        out_rows.append({"level": lv, "multiplier": round(float(table["pricing"]["per_corridor"][next(iter(table["pricing"]["per_corridor"]))]["multiplier"]), 3),
                         "selected_hash": h(adv), "pct_routes_differ_vs_level0": round(100 * sum(1 for v in ids if ref[v] != adv[v]) / len(ids), 2)})
    return {"seed": seed, "coverage_hops": hops, "rows": out_rows}


def markdown(all_runs: list[dict]) -> str:
    L = ["# R1 — forecast-to-action sensitivity (same net, demand, OD, seed, horizon)\n"]
    for r in all_runs:
        L.append(f"## seed {r['seed']}, pricing coverage {r['coverage_hops']} hops\n")
        L.append("| forecast | status | served / checkpoint | raw hash | classes → multipliers (6 corridors) | priced edges | cost hash | % edge costs ≠ persistence | % edge costs ≠ oracle | advised | cand./veh | candidate-set hash | selected hash | % routes ≠ persistence | Jaccard vs persistence | % routes ≠ oracle | Jaccard vs oracle | top-20 concentration |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for k, row in r["rows"].items():
            if row.get("status") != "ok":
                L.append(f"| {k} | {row.get('status')} |" + " |" * 16); continue
            cm = row.get("mapped_multipliers") or {}
            cls = ", ".join(f"{v}" for v in (row.get("mapped_classes") or {}).values()) + " → " + ", ".join(f"{v}" for v in cm.values()) if cm else "—"
            L.append(f"| {k} | ok | {row.get('model_served') or '—'} / {row.get('checkpoint') or '—'} | {row.get('raw_forecast_hash')} | {cls} | {row.get('priced_edges')} | {row.get('edge_cost_hash') or '—'} | "
                     f"{row.get('pct_edge_costs_differ_vs_persistence', '—')} | {row.get('pct_edge_costs_differ_vs_oracle', '—')} | {row.get('advised_vehicles')} | {row.get('mean_candidates_per_vehicle')} | {row.get('candidate_sets_hash')} | {row.get('selected_routes_hash')} | "
                     f"{row.get('pct_vehicles_route_differs_vs_persistence', '—')} | {row.get('mean_jaccard_vs_persistence', '—')} | {row.get('pct_vehicles_route_differs_vs_oracle', '—')} | {row.get('mean_jaccard_vs_oracle', '—')} | {row.get('top20_edge_concentration')} |")
        L.append("")
        L.append("Collapse by stage (distinct hashes among the forecasts that ran; identical groups listed):")
        for st, c in r["collapse"].items():
            L.append(f"- {st}: {c['distinct']} distinct" + (f" — identical: {c['identical_groups']}" if c["identical_groups"] else ""))
        L.append(f"\n**First collapse stage: {r['first_collapse_stage'] or 'none — every stage stays distinct'}.**\n")
        if r.get("sweep"):
            L.append("Uniform-class sweep (every corridor at the same level): where the selected routes move")
            L.append("| level | multiplier | selected hash | % routes ≠ level 0 |")
            L.append("|---|---|---|---|")
            for sr in r["sweep"]["rows"]:
                L.append(f"| {sr['level']} | {sr['multiplier']} | {sr['selected_hash']} | {sr['pct_routes_differ_vs_level0']} |")
            L.append("")
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--hops", default="0,8")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    args = p.parse_args()
    cfg = {**ic.DEFAULTS, "seeds": str(args.seed), "api": args.api}
    sc = RESULTS / "SCALE_CHOICE.json"
    cfg["scale"] = json.loads(sc.read_text()).get("scale", 0.25) if sc.exists() else 0.25
    cfg["net"] = str(pr.DEFAULT_NET); cfg["routes"] = str(pr.DEFAULT_ROUTES)
    a = argparse.Namespace(**cfg)
    runs = []
    for hh in args.hops.split(","):
        r = run(args.seed, int(hh), a)
        r["sweep"] = sweep(args.seed, int(hh), a)
        runs.append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    (RESULTS / "r1_forecast_to_action.json").write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), "runs": runs}, indent=1, default=str))
    md = markdown(runs)
    (RESULTS / "r1_forecast_to_action.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
