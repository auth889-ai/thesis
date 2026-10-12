"""P0 vertical slice — the end-to-end loop, running on real infrastructure.

    traffic input → (detector → tracker → sensing) → TrafficObservation
    → forecast → edge costs → candidate route DISTRIBUTIONS
    → SUMO twin (one branch per candidate) → network-wide metrics
    → SYSTEM_OPTIMAL selection → API-compatible result

Baseline components here are TEMPORARY SCAFFOLDING whose purpose is to validate
the interfaces. Each is replaced by a paper-qualified winner at its gate:

    persistence forecast  → forecasting gate winner (DCRNN/GWNet/STID/STAEformer/Chronos-2)
    fixed-time signals    → control gate winner → Forecast-Aware MAPPO
    stub perception       → RT-DETR + ByteTrack (official, GPU, Colab)

The selection rule is the part that is NOT scaffolding: candidates are ranked by
*measured network-wide outcome from the twin*, never by the cost the router
predicted for itself.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from core.common.city import CityProfile, get_city
from core.common.types import EdgeId, TrafficObservation
from core.simulation.twin.sumo_runner import SumoTwin, TwinRunResult, write_route_file
from core.simulation.routing.graph_router import (GraphRouter, NetworkGraph, RouteDistribution,
                                    candidate_distributions, diverse_alternatives)

SCAFFOLDING_COMPONENTS = ("persistence_forecast", "fixed_time_signals", "no_perception")


@dataclass
class SliceConfig:
    city_id: str = "dhaka_r1"
    origin_edge: str = ""
    destination_edge: str = ""
    n_alternatives: int = 3
    max_overlap: float = 0.6        # alternatives sharing more than this are duplicates
    n_vehicles: int = 200
    depart_span_s: float = 300.0
    sim_end_s: float = 900.0
    seeds: Sequence[int] = (42,)
    explicit_splits: Sequence[Sequence[float]] = ()
    out_dir: Path = Path("results/artifacts/p0_vertical_slice")


@dataclass
class CandidateResult:
    label: str
    shares: Sequence[float]
    per_seed: list[dict] = field(default_factory=list)

    def mean(self, metric: str) -> float | None:
        vals = [r[metric] for r in self.per_seed if r.get(metric) is not None]
        return sum(vals) / len(vals) if vals else None

    def all_clean(self) -> bool:
        return all(r.get("clean") for r in self.per_seed) and bool(self.per_seed)

    def all_comparable(self) -> bool:
        """Every seed ran cleanly AND ran all of its demand to completion."""
        return all(r.get("comparable") for r in self.per_seed) and bool(self.per_seed)


def run_vertical_slice(cfg: SliceConfig) -> dict:
    """Execute the slice and return the API-compatible result dict."""
    t0 = time.time()
    city = get_city(cfg.city_id)

    ok, actual_sha = city.verify_network()
    if not ok:
        raise RuntimeError(
            f"network integrity failed for {city.city_id}: expected "
            f"{city.network_sha256}, got {actual_sha}")

    graph = NetworkGraph.from_sumo_net(city.network_path)
    router = GraphRouter(graph, strategy="static_shortest")

    origin, destination = cfg.origin_edge, cfg.destination_edge
    if not graph.has_edge(origin) or not graph.has_edge(destination):
        raise KeyError(f"origin/destination not routable in {city.city_id}: "
                       f"{origin} -> {destination}")

    # --- alternatives: penalty method with an overlap constraint -----------
    # Yen's k-shortest returns near-duplicate paths on a dense urban grid;
    # splitting demand across two copies of the same road relieves nothing.
    alts = diverse_alternatives(graph, origin, destination, router.costs.free_flow,
                                k=cfg.n_alternatives, max_overlap=cfg.max_overlap)
    paths = [p for p, _, _ in alts]
    predicted_costs = [c for _, c, _ in alts]
    overlaps = [o for _, _, o in alts]
    if not paths:
        raise RuntimeError(f"no route from {origin} to {destination}")

    distributions = candidate_distributions(paths, cfg.explicit_splits)

    # --- evaluate every candidate in the twin ------------------------------
    twin = SumoTwin(city)
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    route_dir = cfg.out_dir / "routes"
    route_dir.mkdir(exist_ok=True)

    results: list[CandidateResult] = []
    for dist in distributions:
        cr = CandidateResult(label=dist.label, shares=list(dist.shares))
        counts = dist.assign(cfg.n_vehicles)
        route_map = {f"r{i}": list(p) for i, p in enumerate(dist.paths)}
        veh_map = {f"r{i}": counts[i] for i in range(len(dist.paths))}

        rf = write_route_file(route_dir / f"{dist.label}.rou.xml",
                              route_map, veh_map, cfg.depart_span_s)
        for seed in cfg.seeds:
            run: TwinRunResult = twin.run(rf, end_s=cfg.sim_end_s, seed=seed)
            m = run.metrics
            cr.per_seed.append({
                "seed": seed,
                "returncode": run.sumo_returncode,
                "clean": run.usable,
                "comparable": run.comparable,
                "throughput_veh": m.throughput_veh,
                "avg_travel_time_s": m.avg_travel_time_s,
                "avg_waiting_time_s": m.avg_waiting_time_s,
                "avg_time_loss_s": m.avg_time_loss_s,
                "p95_travel_time_s": m.p95_travel_time_s,
                "collisions": m.collisions,
                "teleports": m.teleports,
                "demand": {
                    "loaded": run.demand.loaded,
                    "inserted": run.demand.inserted,
                    "running_at_end": run.demand.running_at_end,
                    "waiting_at_end": run.demand.waiting_at_end,
                    "insertion_rate": round(run.demand.insertion_rate, 4),
                    "complete": run.demand.is_complete,
                },
                "avg_depart_delay_s": m.metadata.get("avg_depart_delay_s", ""),
            })
        results.append(cr)

    # --- SYSTEM_OPTIMAL selection -----------------------------------------
    # A candidate may only be compared if the SAME amount of traffic actually
    # ran. SUMO trip statistics cover completed trips only, so a run whose demand
    # never got inserted would otherwise look fast while hiding its congestion in
    # the insertion backlog. Such runs are reported and excluded, not silently
    # ranked.
    comparable = [r for r in results
                  if r.all_comparable() and r.mean("avg_time_loss_s") is not None]
    incomparable = [r.label for r in results if not r.all_comparable()]
    ranked = sorted(comparable, key=lambda r: r.mean("avg_time_loss_s"))
    system_optimal = ranked[0].label if ranked else None

    # USER_OPTIMAL = everyone on the router's own cheapest path.
    user_optimal = "all_path_0"
    uo = next((r for r in results if r.label == user_optimal), None)
    so = ranked[0] if ranked else None
    externality = None
    if uo and so and uo.mean("avg_time_loss_s") and so.mean("avg_time_loss_s"):
        externality = {
            "user_optimal_time_loss_s": uo.mean("avg_time_loss_s"),
            "system_optimal_time_loss_s": so.mean("avg_time_loss_s"),
            "improvement_percent": 100.0 * (uo.mean("avg_time_loss_s")
                                            - so.mean("avg_time_loss_s"))
            / uo.mean("avg_time_loss_s"),
        }

    result = {
        "schema_version": 1,
        "stage": "P0_VERTICAL_SLICE",
        "city": {
            "city_id": city.city_id,
            "display_name": city.display_name,
            "country": city.country,
            "traffic_side": city.traffic_side.value,
            "network_sha256": actual_sha,
            "network_verified": ok,
            "signal_timing_provenance": city.signal_timing_provenance,
        },
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "evidence_note": (
            "All numbers below are SIMULATED SUMO outputs on a real, verified "
            "network topology. They are not real traffic measurements."),
        "scaffolding_components": list(SCAFFOLDING_COMPONENTS),
        "graph": {"routable_edges": len(graph)},
        "od_pair": {"origin": origin, "destination": destination},
        "alternatives": [
            {"index": i, "n_edges": len(p),
             "router_predicted_cost_s": round(predicted_costs[i], 1),
             "overlap_with_previous": round(overlaps[i], 3)}
            for i, p in enumerate(paths)
        ],
        "candidates": [
            {"label": r.label, "shares": r.shares,
             "mean_avg_time_loss_s": r.mean("avg_time_loss_s"),
             "mean_avg_travel_time_s": r.mean("avg_travel_time_s"),
             "mean_throughput_veh": r.mean("throughput_veh"),
             "all_runs_clean": r.all_clean(),
             "all_runs_comparable": r.all_comparable(),
             "per_seed": r.per_seed}
            for r in results
        ],
        "selection": {
            "rule": ("min mean avg_time_loss_s over COMPARABLE runs "
                     "(all demand inserted and completed)"),
            "excluded_incomparable_candidates": incomparable,
            "system_optimal": system_optimal,
            "user_optimal": user_optimal,
            "user_vs_system": externality,
        },
        "runtime_s": round(time.time() - t0, 2),
    }

    out = cfg.out_dir / "result.json"
    out.write_text(json.dumps(result, indent=2))
    result["artifact"] = str(out)
    return result
