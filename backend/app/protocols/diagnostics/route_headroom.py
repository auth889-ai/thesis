#!/usr/bin/env python3
"""ROUTE-CHOICE HEADROOM — are the optimizer's candidates meaningfully different routes, or cosmetic
variants of one path that all rejoin the same bottleneck?

Reads the offline decision replay of an identical-state fork run (src/pipeline/v2x/decision_agreement.py
leaves `s<seed>/decision_replay/r<k>_oracle/routing_record.json` with every vehicle's candidate set,
free-flow cost, ORACLE future cost and overlap) plus the baseline run's edgeData for the CURRENT cost,
and computes per vehicle-round:

    candidates                    K+1 routes duarouter produced
    distinct_alternatives         alternatives after clustering: two routes are the same alternative when
                                  their length-weighted overlap exceeds `same_threshold`
    overlap_with_current          length-weighted share of the alternative on the current route
    edge_disjointness             1 − overlap
    common_core                   edges shared by EVERY candidate (length share of the current route)
    bottleneck_shared             the current route's worst edge (highest oracle tt / free-flow tt) is on
                                  every alternative too — "all alternatives rejoin the same bottleneck"
    free_flow_diff_s              best alternative free-flow tt − current free-flow tt (the detour price)
    current_diff_s                current-traffic tt (last measured interval) difference
    oracle_diff_s                 measured-future tt difference: the saving perfect information could buy
    bottleneck_capacity_veh_h     min over the route of lanes × 1800 veh/h/lane, for the current and the best alternative
    real_alternative              an alternative with overlap ≤ max_overlap AND oracle saving ≥ min_saving_s
                                  AND its bottleneck not shared with the current route

    python -m app.protocols.diagnostics.route_headroom --run results/v2x/closed_loop/<fork run dir>
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from app.paths import REPO
sys.path.insert(0, str(REPO))

from app.twin import runtime as pr     # noqa: E402
from app.routing import route_optimizer as ro        # noqa: E402

CAP_LANE_H = 1800.0


def overlap(a: list[str], b: list[str], length: dict) -> float:
    """length-weighted share of route a that lies on route b."""
    sb = set(b); la = sum(length.get(e, 0.0) for e in a)
    return sum(length.get(e, 0.0) for e in a if e in sb) / la if la else 0.0


def cluster(cands: list[dict], length: dict, same: float) -> list[list[int]]:
    groups: list[list[int]] = []
    for i, c in enumerate(cands):
        for g in groups:
            if overlap(c["edges"], cands[g[0]]["edges"], length) >= same and overlap(cands[g[0]]["edges"], c["edges"], length) >= same:
                g.append(i); break
        else:
            groups.append([i])
    return groups


def current_tt(edgedata: Path, t: float) -> dict[str, float]:
    return {eid: tt for b, e, eid, tt in pr.load_weights(edgedata) if b < t <= e}


def analyse(run_dir: Path, seed: int, info: ro.NetInfo, same: float, max_overlap: float, min_saving: float) -> list[dict]:
    base = run_dir / f"s{seed}" / "baseline"; rows = []
    for rec_path in sorted((run_dir / f"s{seed}" / "decision_replay").glob("r*_oracle/routing_record.json")):
        rec = json.loads(rec_path.read_text()); t = float(rec.get("window_s", 0)) if isinstance(rec.get("window_s"), (int, float)) else None
        k = int(rec_path.parent.name.split("_")[0][1:]); t_round = (k + 2) * 300 if t is None else t   # rounds start at fork 480 → 600, 900, …
        cur_tt = current_tt(base / "edgedata.xml", t_round)
        for d in rec["decisions"]:
            cands = d.get("candidates") or []
            if len(cands) < 2:
                rows.append({"seed": seed, "round": k, "vehicle": d["vehicle"], "candidates": len(cands), "distinct_alternatives": 0, "real_alternative": False}); continue
            cur = cands[0]; alts = cands[1:]
            groups = cluster(alts, info.length, same)
            distinct = [alts[g[0]] for g in groups if overlap(alts[g[0]]["edges"], cur["edges"], info.length) < same]
            interior = cur["edges"][1:-1] or cur["edges"]                    # every candidate shares the trip's first (current) and last (destination) edge by construction
            core = set(interior)
            for c in alts:
                core &= set(c["edges"])
            core_share = sum(info.length.get(e, 0.0) for e in core) / max(sum(info.length.get(e, 0.0) for e in cur["edges"]), 1e-6)
            fut = rec["edge_costs"];
            def route_tt(c, table_key):
                return c["forecast_future_tt_s"] if table_key == "oracle" else sum(cur_tt.get(e, info.free_tt.get(e, 0.0)) for e in c["edges"])
            worst = max(interior, key=lambda e: (cur_tt.get(e, info.free_tt.get(e, 0.0)) / max(info.free_tt.get(e, 1e-6), 1e-6)))
            cap = lambda c: min(info.lanes.get(e, 1) for e in c["edges"]) * CAP_LANE_H
            best = min(alts, key=lambda c: c["forecast_future_tt_s"]) if alts else None
            ov_best = overlap(best["edges"], cur["edges"], info.length)
            oracle_diff = cur["forecast_future_tt_s"] - best["forecast_future_tt_s"]
            current_diff = route_tt(cur, "now") - route_tt(best, "now")
            bottleneck_shared = all(worst in c["edges"] for c in alts)
            rows.append({"seed": seed, "round": k, "vehicle": d["vehicle"], "candidates": len(cands), "distinct_alternatives": len(distinct),
                         "overlap_best_with_current": round(ov_best, 3), "edge_disjointness_best": round(1 - ov_best, 3), "mean_overlap_alternatives": round(statistics.fmean(overlap(c["edges"], cur["edges"], info.length) for c in alts), 3),
                         "common_core_share": round(core_share, 3), "bottleneck_edge": worst, "bottleneck_shared_by_all_alternatives": bottleneck_shared,
                         "free_flow_diff_s": round(best["base_tt_s"] - cur["base_tt_s"], 1), "current_diff_s": round(current_diff, 1), "oracle_diff_s": round(oracle_diff, 1),
                         "capacity_current_veh_h": cap(cur), "capacity_best_veh_h": cap(best), "oracle_decision": d["decision"],
                         "real_alternative": bool(ov_best <= max_overlap and oracle_diff >= min_saving and not bottleneck_shared)})
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--run", required=True); p.add_argument("--same-threshold", type=float, default=0.85); p.add_argument("--max-overlap", type=float, default=0.6); p.add_argument("--min-saving-s", type=float, default=60.0)
    a = p.parse_args(); run_dir = REPO / a.run
    P = json.loads((run_dir / "PROTOCOL.json").read_text()); info = ro.NetInfo(REPO / P["network"])
    seeds = sorted(int(d.name[1:]) for d in run_dir.glob("s*") if (d / "decision_replay").exists())
    rows = [r for s in seeds for r in analyse(run_dir, s, info, a.same_threshold, a.max_overlap, a.min_saving_s)]
    ok = [r for r in rows if r["candidates"] >= 2]
    q = lambda k, f=statistics.median: (round(f([r[k] for r in ok]), 3) if ok else None)
    summary = {"run": a.run, "seeds": seeds, "vehicle_rounds": len(rows), "with_alternatives": len(ok), "thresholds": {"same_alternative_overlap": a.same_threshold, "max_overlap_for_real_alternative": a.max_overlap, "min_oracle_saving_s": a.min_saving_s},
               "median_candidates": q("candidates"), "median_distinct_alternatives": q("distinct_alternatives"), "share_with_zero_distinct_alternatives": round(sum(1 for r in ok if r["distinct_alternatives"] == 0) / len(ok), 3) if ok else None,
               "share_with_3plus_distinct": round(sum(1 for r in ok if r["distinct_alternatives"] >= 3) / len(ok), 3) if ok else None,
               "median_overlap_best_with_current": q("overlap_best_with_current"), "median_mean_overlap_alternatives": q("mean_overlap_alternatives"), "median_common_core_share": q("common_core_share"),
               "share_bottleneck_shared_by_all": round(sum(1 for r in ok if r["bottleneck_shared_by_all_alternatives"]) / len(ok), 3) if ok else None,
               "median_free_flow_diff_s": q("free_flow_diff_s"), "median_current_diff_s": q("current_diff_s"), "median_oracle_diff_s": q("oracle_diff_s"), "p90_oracle_diff_s": (round(sorted(r["oracle_diff_s"] for r in ok)[int(0.9 * len(ok))], 1) if ok else None),
               "share_oracle_saving_ge_60s": round(sum(1 for r in ok if r["oracle_diff_s"] >= 60) / len(ok), 3) if ok else None,
               "share_real_alternative": round(sum(1 for r in ok if r["real_alternative"]) / len(ok), 3) if ok else None,
               "reading": "distinct = alternatives that overlap the current route by less than the same-threshold; real = distinct, saves ≥ min saving under the ORACLE, and does not share the current route's bottleneck edge"}
    out = run_dir / "route_headroom.json"; out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    md = [f"# Route-choice headroom — {a.run}", "", "| statistic | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in summary.items() if k not in ("run", "seeds", "reading", "thresholds")] + ["", summary["reading"], ""]
    (run_dir / "route_headroom.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
