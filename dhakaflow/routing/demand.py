"""Multi-OD demand — the environment in which system-optimal routing is testable.

P0 measured that with a single O-D pair, splitting traffic across alternatives
never beats the best single path (N = 300…1500, every candidate comparable). The
reason is structural, not a tuning failure: every candidate route leaves the same
origin edge, so they all queue behind the same bottleneck and rerouting cannot
relieve it.

Wardrop's distinction only bites when *different trips* compete for *shared
intermediate links*. That requires many O-D pairs whose paths overlap in the
middle of the network — which is what this module builds.

Two assignment policies are provided, and they are the experiment:

* `USER_OPTIMAL`   — every trip independently takes its own fastest path
                     (selfish routing; what a navigation app does today)
* `SYSTEM_AWARE`   — trips are spread across their alternatives to reduce
                     total network cost

The comparison between them is the routing contribution. Neither is graded by
the router's own cost estimate; both are run through the twin.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence

from ..common.types import EdgeId
from .graph_router import NetworkGraph, diverse_alternatives, usable_edges


class AssignmentPolicy(str, Enum):
    USER_OPTIMAL = "user_optimal"        # selfish: each trip takes its own best path
    SYSTEM_AWARE = "system_aware"        # spread across alternatives
    RANDOM_ALTERNATIVE = "random_alternative"   # control: is spreading itself the cause?


@dataclass(frozen=True)
class ODPair:
    """One origin–destination relation with its alternative paths."""

    od_id: str
    origin: EdgeId
    destination: EdgeId
    paths: Sequence[Sequence[EdgeId]]
    free_flow_costs: Sequence[float]
    n_vehicles: int

    @property
    def n_alternatives(self) -> int:
        return len(self.paths)


@dataclass
class MultiODDemand:
    """A network-wide demand set plus the shared-link structure that makes it interesting."""

    pairs: Sequence[ODPair]
    seed: int
    shared_edge_count: int = 0
    max_edge_load: int = 0
    metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def total_vehicles(self) -> int:
        return sum(p.n_vehicles for p in self.pairs)

    def edge_load(self, policy: AssignmentPolicy = AssignmentPolicy.USER_OPTIMAL
                  ) -> dict[EdgeId, int]:
        """Vehicles per edge under a policy, ignoring congestion dynamics.

        A planning-level estimate only — the real answer comes from the twin.
        Its use here is to check *before* simulating that the demand actually
        creates contention; a demand set with no shared loaded edges cannot test
        system-optimal routing no matter how many vehicles it has.
        """
        load: dict[EdgeId, int] = {}
        for p in self.pairs:
            if policy is AssignmentPolicy.USER_OPTIMAL:
                shares = [1.0] + [0.0] * (p.n_alternatives - 1)
            else:
                shares = [1.0 / p.n_alternatives] * p.n_alternatives
            for path, share in zip(p.paths, shares):
                n = int(round(p.n_vehicles * share))
                for e in path:
                    load[e] = load.get(e, 0) + n
        return load

    def contention_report(self) -> dict:
        """Is this demand set capable of testing system-optimal routing at all?"""
        uo = self.edge_load(AssignmentPolicy.USER_OPTIMAL)
        shared = {e: n for e, n in uo.items() if n > 0}
        # Edges used by more than one O-D pair's primary path are where the
        # externality can appear.
        primary_users: dict[EdgeId, set[str]] = {}
        for p in self.pairs:
            for e in p.paths[0]:
                primary_users.setdefault(e, set()).add(p.od_id)
        contended = {e: sorted(ods) for e, ods in primary_users.items() if len(ods) > 1}
        return {
            "n_od_pairs": len(self.pairs),
            "total_vehicles": self.total_vehicles,
            "n_loaded_edges": len(shared),
            "n_contended_edges": len(contended),
            "max_edge_load_veh": max(uo.values()) if uo else 0,
            "testable": bool(contended),
            "note": ("A demand set with no contended edges cannot exhibit a "
                     "user-vs-system-optimal gap — rerouting would have nothing "
                     "to relieve."),
        }


def build_multi_od_demand(graph: NetworkGraph,
                          n_pairs: int = 20,
                          vehicles_per_pair: int = 60,
                          n_alternatives: int = 3,
                          seed: int = 42,
                          min_speed_ms: float = 8.0,
                          min_cost_s: float = 120.0,
                          max_cost_s: float = 600.0,
                          max_overlap: float = 0.6,
                          hub_fraction: float = 0.5,
                          max_attempts: int = 4000) -> MultiODDemand:
    """Sample O-D pairs that genuinely contend for shared links.

    `hub_fraction` of the pairs are drawn towards a small set of shared
    destinations, because purely uniform random O-D sampling on a 4400-edge
    network produces trips that barely interact — which is precisely the
    degenerate case P0 hit. Real urban demand is hub-directed (CBD, markets,
    interchanges), so this is realism, not a thumb on the scale.
    """
    from .graph_router import GraphRouter

    rng = random.Random(seed)
    router = GraphRouter(graph, strategy="static_shortest")
    pool = usable_edges(graph, min_speed_ms=min_speed_ms, min_length_m=50.0)
    if len(pool) < 10:
        raise ValueError("not enough plausible edges to build demand")

    n_hubs = max(2, n_pairs // 5)
    hubs = rng.sample(pool, n_hubs)

    pairs: list[ODPair] = []
    attempts = 0
    while len(pairs) < n_pairs and attempts < max_attempts:
        attempts += 1
        origin = rng.choice(pool)
        destination = (rng.choice(hubs) if rng.random() < hub_fraction
                       else rng.choice(pool))
        if origin == destination:
            continue

        alts = diverse_alternatives(graph, origin, destination,
                                    router.costs.free_flow,
                                    k=n_alternatives, max_overlap=max_overlap)
        if len(alts) < 2:                      # no real choice ⇒ nothing to route
            continue
        cost0 = alts[0][1]
        if not (min_cost_s <= cost0 <= max_cost_s):
            continue

        pairs.append(ODPair(
            od_id=f"od{len(pairs):03d}",
            origin=origin,
            destination=destination,
            paths=[p for p, _, _ in alts],
            free_flow_costs=[c for _, c, _ in alts],
            n_vehicles=vehicles_per_pair,
        ))

    if len(pairs) < n_pairs:
        # Report the shortfall rather than silently returning a smaller demand.
        pass

    demand = MultiODDemand(
        pairs=pairs, seed=seed,
        metadata={
            "requested_pairs": str(n_pairs),
            "obtained_pairs": str(len(pairs)),
            "attempts": str(attempts),
            "hub_fraction": str(hub_fraction),
            "n_hubs": str(n_hubs),
            "provenance": "SYNTHETIC_STRUCTURED_DEMAND",
            "note": ("Not calibrated Dhaka demand. Structured to create link "
                     "contention so routing policies are distinguishable; "
                     "replaced by calibrated demand at the twin gate."),
        })
    return demand


def assign_routes(demand: MultiODDemand, policy: AssignmentPolicy,
                  seed: int = 42) -> tuple[dict[str, list[EdgeId]], dict[str, int]]:
    """Turn a demand set + policy into SUMO route definitions and vehicle counts."""
    rng = random.Random(seed)
    routes: dict[str, list[EdgeId]] = {}
    counts: dict[str, int] = {}

    for p in demand.pairs:
        if policy is AssignmentPolicy.USER_OPTIMAL:
            shares = [1.0] + [0.0] * (p.n_alternatives - 1)
        elif policy is AssignmentPolicy.SYSTEM_AWARE:
            # Inverse-cost weighting: cheaper alternatives carry more traffic,
            # but no single road absorbs the whole relation.
            inv = [1.0 / max(c, 1e-6) for c in p.free_flow_costs]
            total = sum(inv)
            shares = [x / total for x in inv]
        else:                                   # RANDOM_ALTERNATIVE control
            pick = rng.randrange(p.n_alternatives)
            shares = [1.0 if i == pick else 0.0 for i in range(p.n_alternatives)]

        allocated = [int(round(p.n_vehicles * s)) for s in shares]
        drift = p.n_vehicles - sum(allocated)
        if drift:
            allocated[max(range(len(allocated)), key=lambda k: shares[k])] += drift

        for i, (path, n) in enumerate(zip(p.paths, allocated)):
            if n <= 0:
                continue
            rid = f"{p.od_id}_a{i}"
            routes[rid] = list(path)
            counts[rid] = n

    return routes, counts
