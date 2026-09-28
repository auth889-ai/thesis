"""Network graph and routers — including the system-optimal distribution rule.

Three router strategies share one graph:

* `static_shortest`  — free-flow travel time; ignores traffic entirely
* `current_fastest`  — uses the *measured* current state (Mode B: react)
* `forecast_fastest` — uses *predicted* edge costs at arrival time (Mode A: prevent)

`forecast_fastest` implements the point your goal turns on: a vehicle should not
be routed onto the road that is fast *now*, but onto the road that will still be
fast *when it gets there*. Cost is looked up at the estimated arrival time along
the path, not at departure time.

Above the single-vehicle routers sits `RouteDistribution`: the object that makes
SYSTEM_OPTIMAL possible. A best route for one driver is not a best routing for
the network, so candidate *distributions* (e.g. 55% A / 25% B / 20% C) are what
we evaluate in the twin.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

from app.common.types import EdgeId, TrafficObservation, VehicleClass
from app.interfaces.routing import RouteDecision, RouteRequest


@dataclass(frozen=True)
class EdgeInfo:
    edge_id: EdgeId
    length_m: float
    speed_limit_ms: float
    num_lanes: int
    to_node: str
    from_node: str

    @property
    def free_flow_time_s(self) -> float:
        return self.length_m / max(self.speed_limit_ms, 0.1)


class NetworkGraph:
    """Directed graph built from a SUMO network, usable for any city.

    Deliberately thin: it reads the network once via sumolib and exposes exactly
    what routing needs. Heavy simulation stays in the twin.
    """

    def __init__(self, edges: Mapping[EdgeId, EdgeInfo],
                 successors: Mapping[EdgeId, tuple[EdgeId, ...]]):
        self._edges = dict(edges)
        self._successors = dict(successors)

    # ------------------------------------------------------------------ build
    @classmethod
    def from_sumo_net(cls, net_path, allowed_class: str = "passenger") -> "NetworkGraph":
        import sumolib

        net = sumolib.net.readNet(str(net_path))
        edges: dict[EdgeId, EdgeInfo] = {}
        for e in net.getEdges():
            eid = e.getID()
            if eid.startswith(":"):          # internal junction edge
                continue
            if allowed_class and not e.allows(allowed_class):
                continue
            edges[eid] = EdgeInfo(
                edge_id=eid,
                length_m=float(e.getLength()),
                speed_limit_ms=float(e.getSpeed()),
                num_lanes=len(e.getLanes()),
                from_node=e.getFromNode().getID(),
                to_node=e.getToNode().getID(),
            )

        successors: dict[EdgeId, tuple[EdgeId, ...]] = {}
        for eid in edges:
            e = net.getEdge(eid)
            nxt = tuple(o.getID() for o in e.getOutgoing()
                        if o.getID() in edges)
            successors[eid] = nxt
        return cls(edges, successors)

    # ------------------------------------------------------------------ query
    def __len__(self) -> int:
        return len(self._edges)

    @property
    def edge_ids(self) -> tuple[EdgeId, ...]:
        return tuple(self._edges)

    def edge(self, edge_id: EdgeId) -> EdgeInfo:
        return self._edges[edge_id]

    def has_edge(self, edge_id: EdgeId) -> bool:
        return edge_id in self._edges

    def successors(self, edge_id: EdgeId) -> tuple[EdgeId, ...]:
        return self._successors.get(edge_id, ())

    # ---------------------------------------------------------------- routing
    def shortest_path(
        self,
        origin: EdgeId,
        destination: EdgeId,
        cost_fn: Callable[[EdgeId, float], float],
        start_time_s: float = 0.0,
        max_expansions: int = 2_000_000,
    ) -> tuple[list[EdgeId], float, int]:
        """Time-dependent Dijkstra.

        `cost_fn(edge, arrival_time_s)` is evaluated at the time the vehicle
        would *enter* that edge — this is what makes forecast-aware routing
        different from re-running shortest path with today's numbers.

        Returns (edges, total_cost_s, expansions). Empty list ⇒ unreachable.
        """
        if origin not in self._edges or destination not in self._edges:
            return [], math.inf, 0
        if origin == destination:
            return [origin], cost_fn(origin, start_time_s), 0

        best: dict[EdgeId, float] = {origin: start_time_s + cost_fn(origin, start_time_s)}
        prev: dict[EdgeId, EdgeId] = {}
        heap: list[tuple[float, EdgeId]] = [(best[origin], origin)]
        expansions = 0

        while heap:
            t, edge = heapq.heappop(heap)
            if t > best.get(edge, math.inf):
                continue
            if edge == destination:
                break
            expansions += 1
            if expansions > max_expansions:
                break
            for nxt in self.successors(edge):
                nt = t + cost_fn(nxt, t)
                if nt < best.get(nxt, math.inf):
                    best[nxt] = nt
                    prev[nxt] = edge
                    heapq.heappush(heap, (nt, nxt))

        if destination not in best:
            return [], math.inf, expansions

        path = [destination]
        while path[-1] != origin:
            path.append(prev[path[-1]])
        path.reverse()
        return path, best[destination] - start_time_s, expansions


# ---------------------------------------------------------------------------
# Cost models
# ---------------------------------------------------------------------------

def k_shortest_paths(graph: "NetworkGraph", origin: EdgeId, destination: EdgeId,
                     cost_fn: Callable[[EdgeId, float], float], k: int = 3,
                     max_candidates: int = 50,
                     ) -> list[tuple[list[EdgeId], float]]:
    """Yen's k-shortest loopless paths (Yen, 1971).

    Standard algorithm, used as published — alternatives must be *principled*,
    not "the shortest path plus a random detour". Without genuine alternatives a
    route distribution has nothing to distribute over.
    """
    first, cost, _ = graph.shortest_path(origin, destination, cost_fn)
    if not first:
        return []
    accepted: list[tuple[list[EdgeId], float]] = [(first, cost)]
    candidates: list[tuple[float, list[EdgeId]]] = []

    while len(accepted) < k:
        prev_path = accepted[-1][0]
        for i in range(len(prev_path) - 1):
            spur_node = prev_path[i]
            root = prev_path[:i + 1]

            # Edges to remove: the next hop of every accepted path sharing this root.
            banned = {p[i + 1] for p, _ in accepted
                      if len(p) > i + 1 and p[:i + 1] == root}
            # Nodes to avoid: everything already on the root (loopless requirement).
            blocked = set(root[:-1]) | banned

            sub = _MaskedGraph(graph, blocked)
            spur, spur_cost, _ = sub.shortest_path(spur_node, destination, cost_fn)
            if not spur:
                continue
            total = root[:-1] + spur
            if any(total == p for p, _ in accepted):
                continue
            total_cost = sum(cost_fn(e, 0.0) for e in total)
            entry = (total_cost, total)
            if entry not in candidates:
                candidates.append(entry)
            if len(candidates) >= max_candidates:
                break

        if not candidates:
            break
        candidates.sort(key=lambda x: x[0])
        best_cost, best_path = candidates.pop(0)
        accepted.append((best_path, best_cost))

    return accepted


def diverse_alternatives(graph: "NetworkGraph", origin: EdgeId, destination: EdgeId,
                         cost_fn: Callable[[EdgeId, float], float], k: int = 3,
                         penalty: float = 0.5, max_overlap: float = 0.7,
                         max_rounds: int = 12,
                         ) -> list[tuple[list[EdgeId], float, float]]:
    """Alternatives by the iterative edge-penalty method, filtered by overlap.

    Yen's algorithm returns the k *cheapest* loopless paths, which on a dense
    urban grid are usually near-duplicates of each other (one block different) —
    useless as a route distribution, because splitting demand across two copies
    of the same road relieves nothing.

    The penalty method (standard in route-choice practice, and the same idea
    SUMO's own route alternatives use) instead multiplies the cost of an accepted
    path's edges by `1 + penalty` and re-solves, pushing the next solution onto
    genuinely different roads. We then keep only paths whose edge overlap with
    every accepted path is <= `max_overlap`.

    Returns [(path, true_cost_s, max_overlap_with_accepted)].
    """
    accepted: list[tuple[list[EdgeId], float, float]] = []
    multiplier: dict[EdgeId, float] = {}

    def penalised(edge_id: EdgeId, t: float = 0.0) -> float:
        return cost_fn(edge_id, t) * multiplier.get(edge_id, 1.0)

    for _ in range(max_rounds):
        if len(accepted) >= k:
            break
        path, _, _ = graph.shortest_path(origin, destination, penalised)
        if not path:
            break
        true_cost = sum(cost_fn(e, 0.0) for e in path)
        overlap = max((_edge_overlap(path, p) for p, _, _ in accepted), default=0.0)

        if not accepted or overlap <= max_overlap:
            if not any(p == path for p, _, _ in accepted):
                accepted.append((path, true_cost, overlap))
        for e in path:
            multiplier[e] = multiplier.get(e, 1.0) * (1.0 + penalty)

    return accepted


def _edge_overlap(a: Sequence[EdgeId], b: Sequence[EdgeId]) -> float:
    """Fraction of the shorter path's edges shared with the other path."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def usable_edges(graph: "NetworkGraph", min_speed_ms: float = 5.0,
                 min_length_m: float = 20.0) -> list[EdgeId]:
    """Edges defensible as trip endpoints.

    Real OSM extracts contain edges with implausible speed limits — the frozen
    R1 network has 8 edges tagged at 0.56 m/s (2 km/h) whose reverse twins are
    16.67 m/s, an OSM tagging artefact. Routing through them produces route costs
    dominated by a single mis-tagged link, so endpoints are drawn from edges that
    pass a stated plausibility filter rather than uniformly at random.
    """
    out = []
    for e in graph.edge_ids:
        info = graph.edge(e)
        if info.speed_limit_ms >= min_speed_ms and info.length_m >= min_length_m:
            out.append(e)
    return out


def implausible_speed_edges(graph: "NetworkGraph", threshold_ms: float = 2.0
                            ) -> list[tuple[EdgeId, float, float]]:
    """Audit hook: (edge, speed_ms, length_m) for suspiciously slow edges."""
    return [(e, graph.edge(e).speed_limit_ms, graph.edge(e).length_m)
            for e in graph.edge_ids if graph.edge(e).speed_limit_ms < threshold_ms]


class _MaskedGraph:
    """A view of the graph with some edges hidden (used only by Yen's algorithm)."""

    def __init__(self, graph: "NetworkGraph", blocked: set[EdgeId]):
        self._g = graph
        self._blocked = blocked

    def successors(self, edge_id: EdgeId) -> tuple[EdgeId, ...]:
        return tuple(e for e in self._g.successors(edge_id) if e not in self._blocked)

    def shortest_path(self, origin, destination, cost_fn, start_time_s: float = 0.0):
        if origin in self._blocked or not self._g.has_edge(origin):
            return [], math.inf, 0
        best = {origin: start_time_s + cost_fn(origin, start_time_s)}
        prev: dict[EdgeId, EdgeId] = {}
        heap = [(best[origin], origin)]
        expansions = 0
        while heap:
            t, edge = heapq.heappop(heap)
            if t > best.get(edge, math.inf):
                continue
            if edge == destination:
                break
            expansions += 1
            for nxt in self.successors(edge):
                nt = t + cost_fn(nxt, t)
                if nt < best.get(nxt, math.inf):
                    best[nxt] = nt
                    prev[nxt] = edge
                    heapq.heappush(heap, (nt, nxt))
        if destination not in best:
            return [], math.inf, expansions
        path = [destination]
        while path[-1] != origin:
            path.append(prev[path[-1]])
        path.reverse()
        return path, best[destination] - start_time_s, expansions


class EdgeCostModel:
    """Turns network state and forecasts into per-edge traversal times.

    `current` uses measured lane speeds; `forecast` uses predicted values at the
    vehicle's arrival time. Where a road has no observation, we fall back to
    free-flow and record that the fallback happened — an unobserved road must
    never silently look like an empty fast road, which is exactly how naive
    routing sends everyone into an unmonitored jam.
    """

    def __init__(self, graph: NetworkGraph):
        self.graph = graph
        self.fallback_count = 0
        self.observed_count = 0

    def free_flow(self, edge_id: EdgeId, _t: float = 0.0) -> float:
        return self.graph.edge(edge_id).free_flow_time_s

    def current(self, observation: TrafficObservation) -> Callable[[EdgeId, float], float]:
        speeds = _edge_mean_speeds(observation)

        def cost(edge_id: EdgeId, _t: float = 0.0) -> float:
            info = self.graph.edge(edge_id)
            v = speeds.get(edge_id)
            if v is None or v <= 0.1:
                if v is None:
                    self.fallback_count += 1
                    return info.free_flow_time_s
                # observed but stopped: cap at a large finite penalty, not inf,
                # so a fully-jammed network still yields a routable path.
                self.observed_count += 1
                return info.length_m / 0.1
            self.observed_count += 1
            return info.length_m / min(v, info.speed_limit_ms)

        return cost

    def forecast(self,
                 predicted_speed_by_edge: Mapping[float, Mapping[EdgeId, float]],
                 ) -> Callable[[EdgeId, float], float]:
        """Cost from forecast horizons.

        `predicted_speed_by_edge` maps horizon_s → {edge: predicted mean speed}.
        For an arrival time t we use the nearest horizon at or after t, so a
        vehicle arriving in 12 minutes is costed with the 15-minute forecast
        rather than with the state at departure.
        """
        horizons = sorted(predicted_speed_by_edge)

        def cost(edge_id: EdgeId, t: float = 0.0) -> float:
            info = self.graph.edge(edge_id)
            h = next((h for h in horizons if h >= t), horizons[-1] if horizons else None)
            table = predicted_speed_by_edge.get(h, {}) if h is not None else {}
            v = table.get(edge_id)
            if v is None or v <= 0.1:
                if v is None:
                    self.fallback_count += 1
                    return info.free_flow_time_s
                return info.length_m / 0.1
            self.observed_count += 1
            return info.length_m / min(v, info.speed_limit_ms)

        return cost


def _edge_mean_speeds(observation: TrafficObservation) -> dict[EdgeId, float]:
    """Aggregate lane states to edge mean speed (SUMO lane id = '<edge>_<idx>')."""
    acc: dict[EdgeId, list[float]] = {}
    for lane_id, state in observation.lanes.items():
        edge_id = lane_id.rsplit("_", 1)[0] if "_" in lane_id else lane_id
        acc.setdefault(edge_id, []).append(float(state.mean_speed_ms))
    return {e: (sum(v) / len(v)) for e, v in acc.items() if v}


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

class GraphRouter:
    """One router class, three strategies, so comparisons stay fair."""

    def __init__(self, graph: NetworkGraph, strategy: str = "static_shortest"):
        if strategy not in {"static_shortest", "current_fastest", "forecast_fastest"}:
            raise ValueError(f"unknown routing strategy {strategy!r}")
        self.graph = graph
        self.strategy = strategy
        self.costs = EdgeCostModel(graph)

    @property
    def name(self) -> str:
        return self.strategy

    @property
    def uses_forecast(self) -> bool:
        return self.strategy == "forecast_fastest"

    def route(self, request: RouteRequest,
              observation: TrafficObservation | None = None,
              forecast=None) -> RouteDecision:
        if self.strategy == "static_shortest" or (
                self.strategy == "current_fastest" and observation is None):
            cost_fn = self.costs.free_flow
            used_forecast = False
            effective = "static_shortest"
        elif self.strategy == "current_fastest":
            cost_fn = self.costs.current(observation)
            used_forecast = False
            effective = "current_fastest"
        else:
            if not forecast:
                # Honest degradation: say so in the decision rather than
                # pretending a forecast was used.
                cost_fn = (self.costs.current(observation) if observation
                           else self.costs.free_flow)
                used_forecast = False
                effective = "forecast_fastest_degraded"
            else:
                cost_fn = self.costs.forecast(forecast)
                used_forecast = True
                effective = "forecast_fastest"

        edges, total, expansions = self.graph.shortest_path(
            request.origin, request.destination, cost_fn, request.depart_time_s)
        if not edges:
            raise RouteUnreachable(
                f"no path from {request.origin} to {request.destination}")

        distance = sum(self.graph.edge(e).length_m for e in edges)
        return RouteDecision(
            edges=edges,
            estimated_travel_time_s=float(total),
            estimated_distance_m=float(distance),
            strategy=effective,
            used_forecast=used_forecast,
            diagnostics={
                "expansions": float(expansions),
                "n_edges": float(len(edges)),
                "cost_fallback_edges": float(self.costs.fallback_count),
                "cost_observed_edges": float(self.costs.observed_count),
            },
        )


class RouteUnreachable(RuntimeError):
    """Raised when no path exists — never silently returns an empty route."""


# ---------------------------------------------------------------------------
# SYSTEM_OPTIMAL: route distributions, not single paths
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RouteDistribution:
    """A split of demand across alternative paths.

    This is the object the thesis optimises. USER_OPTIMAL asks "what is fastest
    for me"; SYSTEM_OPTIMAL asks "what split minimises total network cost" — and
    those have different answers whenever a road can saturate.
    """

    label: str
    paths: Sequence[Sequence[EdgeId]]
    shares: Sequence[float]
    vehicle_class: VehicleClass = VehicleClass.CAR
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.paths) != len(self.shares):
            raise ValueError("paths and shares must have equal length")
        if not self.paths:
            raise ValueError("a distribution needs at least one path")
        total = sum(self.shares)
        if not math.isclose(total, 1.0, abs_tol=1e-6):
            raise ValueError(f"{self.label}: shares must sum to 1.0, got {total}")
        if any(s < 0 for s in self.shares):
            raise ValueError(f"{self.label}: negative share")

    def assign(self, n_vehicles: int) -> list[int]:
        """Split n vehicles across paths, preserving the total exactly."""
        counts = [int(round(n_vehicles * s)) for s in self.shares]
        drift = n_vehicles - sum(counts)
        if drift:                       # give/take the remainder from the largest share
            i = max(range(len(counts)), key=lambda k: self.shares[k])
            counts[i] += drift
        return counts


def single_path_distribution(path: Sequence[EdgeId], label: str = "all_on_one"
                             ) -> RouteDistribution:
    return RouteDistribution(label=label, paths=[list(path)], shares=[1.0])


def candidate_distributions(paths: Sequence[Sequence[EdgeId]],
                            splits: Sequence[Sequence[float]] | None = None,
                            ) -> list[RouteDistribution]:
    """Build the candidate set to evaluate in the twin.

    Always includes every "100% on one path" candidate (these are the
    USER_OPTIMAL-style extremes) plus an even split and any explicit splits
    given. The winner is chosen by network-wide outcome, never by the cost the
    router itself predicted — a router grading its own homework is how routing
    papers overstate results.
    """
    out: list[RouteDistribution] = []
    n = len(paths)
    for i in range(n):
        shares = [0.0] * n
        shares[i] = 1.0
        out.append(RouteDistribution(label=f"all_path_{i}", paths=paths, shares=shares))
    if n > 1:
        out.append(RouteDistribution(label="even_split", paths=paths,
                                     shares=[1.0 / n] * n))
    for j, s in enumerate(splits or ()):
        out.append(RouteDistribution(label=f"split_{j}", paths=paths, shares=list(s)))
    return out
