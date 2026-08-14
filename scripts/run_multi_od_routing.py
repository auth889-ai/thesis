#!/usr/bin/env python3
"""User-optimal vs system-aware routing on multi-OD demand, measured in the twin."""
from __future__ import annotations
import argparse, json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dhakaflow.common.city import get_city
from dhakaflow.digital_twin.sumo_runner import SumoTwin, write_route_file
from dhakaflow.routing.graph_router import NetworkGraph
from dhakaflow.routing.demand import (AssignmentPolicy, assign_routes,
                                      build_multi_od_demand)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="dhaka_r1")
    ap.add_argument("--pairs", type=int, default=20)
    ap.add_argument("--veh-per-pair", type=int, default=60)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--demand-seed", type=int, default=42)
    ap.add_argument("--sim-end", type=float, default=7200.0)
    ap.add_argument("--depart-span", type=float, default=600.0)
    ap.add_argument("--out", default="artifacts/p0_multi_od")
    a = ap.parse_args()

    city = get_city(a.city)
    graph = NetworkGraph.from_sumo_net(city.network_path)
    demand = build_multi_od_demand(graph, n_pairs=a.pairs,
                                   vehicles_per_pair=a.veh_per_pair,
                                   seed=a.demand_seed)
    contention = demand.contention_report()
    if not contention["testable"]:
        print("ABORT: demand has no contended edges — routing is untestable here")
        return 1

    out = Path(a.out); (out / "routes").mkdir(parents=True, exist_ok=True)
    twin = SumoTwin(city)
    results = {}
    for policy in AssignmentPolicy:
        routes, counts = assign_routes(demand, policy, seed=a.demand_seed)
        rf = write_route_file(out / "routes" / f"{policy.value}.rou.xml",
                              routes, counts, a.depart_span)
        per_seed = []
        for s in a.seeds:
            run = twin.run(rf, end_s=a.sim_end, seed=s)
            m = run.metrics
            per_seed.append({
                "seed": s, "comparable": run.comparable,
                "avg_time_loss_s": m.avg_time_loss_s,
                "avg_travel_time_s": m.avg_travel_time_s,
                "p95_travel_time_s": m.p95_travel_time_s,
                "avg_waiting_time_s": m.avg_waiting_time_s,
                "throughput_veh": m.throughput_veh,
                "collisions": m.collisions, "teleports": m.teleports,
                "demand_complete": run.demand.is_complete,
                "inserted": run.demand.inserted, "loaded": run.demand.loaded,
            })
        vals = [r["avg_time_loss_s"] for r in per_seed if r["avg_time_loss_s"] is not None]
        results[policy.value] = {
            "n_routes": len(routes), "vehicles": sum(counts.values()),
            "mean_time_loss_s": statistics.mean(vals) if vals else None,
            "stdev_time_loss_s": statistics.stdev(vals) if len(vals) > 1 else None,
            "all_comparable": all(r["comparable"] for r in per_seed),
            "per_seed": per_seed,
        }

    uo = results[AssignmentPolicy.USER_OPTIMAL.value]["mean_time_loss_s"]
    sa = results[AssignmentPolicy.SYSTEM_AWARE.value]["mean_time_loss_s"]
    verdict = None
    if uo and sa:
        verdict = {"user_optimal_time_loss_s": round(uo, 2),
                   "system_aware_time_loss_s": round(sa, 2),
                   "improvement_percent": round(100.0 * (uo - sa) / uo, 2),
                   "system_aware_wins": sa < uo}
    payload = {"stage": "P0_MULTI_OD_ROUTING", "city": city.city_id,
               "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
               "demand_provenance": demand.metadata.get("provenance"),
               "contention": contention, "seeds": a.seeds,
               "results": results, "verdict": verdict}
    (out / "result.json").write_text(json.dumps(payload, indent=2))
    print(json.dumps({"contention": contention, "verdict": verdict}, indent=2))
    for k, v in results.items():
        print(f"  {k:20} mean_time_loss={v['mean_time_loss_s']} "
              f"stdev={v['stdev_time_loss_s']} comparable={v['all_comparable']}")
    print("artifact:", out / "result.json")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
