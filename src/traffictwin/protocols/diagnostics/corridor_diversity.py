#!/usr/bin/env python3
"""CORRIDOR SELECTION BY ROUTE DIVERSITY — an automatic rule applied BEFORE any outcome is looked at.

For every built scenario, take its development demand (randomTrips, seed 101 — the same draw the
coverage study used), generate diverse alternatives for every trip with the penalty method
(src/pipeline/v2x/network_assignment.diverse_candidates, free-flow weights), and score each OD pair:

    distinct_routes        candidates after the overlap bound (≥ 3 is the rule)
    max_overlap            length-weighted overlap of the best-separated alternative with the shortest route
    bottleneck_disjoint    the min-capacity edge of the shortest route (interior) is NOT on the alternative
    spare_capacity         the alternative's bottleneck has ≥ 2 lanes or ≥ 1800 veh/h capacity
    detour_price_s         free-flow travel-time difference of the alternative (≤ 25 % of the trip)

An OD pair "has real rerouting opportunity" when all of the above hold. A corridor's score is the share
of its trips with real opportunity, weighted by nothing else. The corridor is chosen by this score alone.

    python -m traffictwin.protocols.diagnostics.corridor_diversity --city la_c1_glendale_110_2 --city la_c2_hollywood_101_5 --city la_c3_hollywood_hills --city la_c4_central_wide --city los_angeles_metr
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))
from traffictwin.digital_twin.scenario_builder import scenario_dir          # noqa: E402
from traffictwin.optimization import edge_costs as ec                 # noqa: E402
from traffictwin.optimization import route_optimizer as ro            # noqa: E402
from traffictwin.optimization import network_assignment as na             # noqa: E402

CAP_LANE_H = 1800.0


def score_city(city: str, cc: dict, cfg: dict, out_root: Path, max_trips: int = 400) -> dict:
    from traffictwin.digital_twin.live.trip_comparison import read_any_routes
    man = json.loads((scenario_dir(city) / "MANIFEST.json").read_text())
    net = REPO / man["files"]["net"]; routes = REPO / man["files"]["routes"]
    info = ro.NetInfo(net)
    veh = read_any_routes(routes)[:max_trips]
    trips = [{"id": v, "from": r[0], "to": r[-1], "depart": d, "current_route": r} for v, d, r in veh if len(r) >= 3]
    table = {"edge_travel_times": {}, "model": "free-flow", "horizon_min": 0, "coverage_hops": 0, "analysis_run_id": None, "future_cost_hash": "freeflow"}
    out = out_root / city; out.mkdir(parents=True, exist_ok=True)
    cands, gen = na.diverse_candidates(net, trips, table, out, cfg, cc, 101, info)
    rows = []
    for t in trips:
        cs = cands.get(t["id"], []); cur = cs[0] if cs else None; alts = cs[1:]
        if not cur:
            continue
        interior = cur[1:-1] or cur
        b_edge = min(interior, key=lambda e: info.lanes.get(e, 1)); cur_tt = sum(info.free_tt.get(e, 0.0) for e in cur)
        best = None
        for a in alts:
            ov = na.overlap(a, cur, info.length); tt = sum(info.free_tt.get(e, 0.0) for e in a)
            a_int = a[1:-1] or a; a_b = min(a_int, key=lambda e: info.lanes.get(e, 1)); cap = info.lanes.get(a_b, 1) * CAP_LANE_H
            rec = {"overlap": round(ov, 3), "detour_s": round(tt - cur_tt, 1), "detour_pct": round(100 * (tt - cur_tt) / cur_tt, 1) if cur_tt else None, "bottleneck_disjoint": b_edge not in a, "alt_bottleneck_capacity_veh_h": cap}
            rec["real"] = ov <= cc["candidates"]["max_overlap"] and rec["bottleneck_disjoint"] and cap >= CAP_LANE_H and (rec["detour_pct"] is not None and rec["detour_pct"] <= 25)
            if best is None or (rec["real"], -ov) > (best["real"], -best["overlap"]):
                best = rec
        rows.append({"vehicle": t["id"], "od": [t["from"], t["to"]], "distinct_routes": len(cs), "best": best, "real_opportunity": bool(best and best["real"] and len(cs) >= 3), "trip_free_flow_s": round(cur_tt, 1)})
    n = len(rows); real = sum(1 for r in rows if r["real_opportunity"])
    summary = {"city": city, "trips_scored": n, "share_real_opportunity": round(real / n, 3) if n else None, "share_3plus_distinct": round(sum(1 for r in rows if r["distinct_routes"] >= 3) / n, 3) if n else None,
               "median_distinct_routes": statistics.median(r["distinct_routes"] for r in rows) if rows else None, "median_best_overlap": statistics.median(r["best"]["overlap"] for r in rows if r["best"]) if any(r["best"] for r in rows) else None,
               "share_bottleneck_disjoint": round(sum(1 for r in rows if r["best"] and r["best"]["bottleneck_disjoint"]) / n, 3) if n else None, "median_detour_pct": statistics.median(r["best"]["detour_pct"] for r in rows if r["best"] and r["best"]["detour_pct"] is not None) if rows else None,
               "sumo_edges": len(info.length), "generator": gen}
    (out / "od_diversity.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1))
    return summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", action="append", required=True); p.add_argument("--max-trips", type=int, default=400)
    a = p.parse_args()
    cc = json.loads((REPO / "src/traffictwin/protocols/controller_config.json").read_text()); cfg = ec.load_config()
    out_root = REPO / "results/v2x/corridor_diversity"; out_root.mkdir(parents=True, exist_ok=True)
    rows = []
    for c in a.city:
        s = score_city(c, cc, cfg, out_root, a.max_trips); rows.append(s)
        print(f"[diversity] {c:<26} trips={s['trips_scored']} real_opportunity={s['share_real_opportunity']} 3+distinct={s['share_3plus_distinct']} median_overlap={s['median_best_overlap']} bottleneck_disjoint={s['share_bottleneck_disjoint']} detour%={s['median_detour_pct']}", flush=True)
    rule = "chosen = highest share_real_opportunity (≥3 distinct routes, overlap ≤ max_overlap, bottleneck-disjoint, spare capacity, detour ≤ 25 %) — computed on development demand before any outcome"
    best = max(rows, key=lambda r: r["share_real_opportunity"] or 0)
    (out_root / "summary.json").write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), "rule": rule, "chosen": best["city"], "corridors": rows}, indent=1))
    L = ["# Corridor route-diversity screening", "", rule, "", "| corridor | trips | share real opportunity | ≥3 distinct | median best overlap | bottleneck disjoint | median detour % | SUMO edges |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['city']} | {r['trips_scored']} | **{r['share_real_opportunity']}** | {r['share_3plus_distinct']} | {r['median_best_overlap']} | {r['share_bottleneck_disjoint']} | {r['median_detour_pct']} | {r['sumo_edges']} |" for r in rows]
    L += ["", f"**Chosen by the rule: {best['city']}**", ""]
    (out_root / "summary.md").write_text("\n".join(L)); print("chosen:", best["city"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
