"""Best-route computation on the real frozen Dhaka R1 network.

The REACT demo's routing layer: given live congestion evidence (edge →
slowdown factor, from the perception pipeline or the forecaster), compute

  * the naive route     — fastest under free-flow assumptions, and
  * the informed route  — fastest under CURRENT/predicted edge costs,

on the real 6,527-edge Lab 02 network (read in place from the frozen lab,
never copied — graduation rule). The difference between the naive route's
*actual* cost under congestion and the informed route's cost is the delay
avoided by routing intelligence — the number the demo prints.

This is the same DUE-style edge-cost machinery the frozen E4 experiment used;
the full twin-simulated proof (SUMO branches, multi-seed statistics) remains
the integration-gate deliverable. Nothing here is video-specific or hardcoded:
origins/destinations are arbitrary coordinates, congestion is an arbitrary
edge->factor mapping.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from pathlib import Path

NET_PATH = (Path(__file__).resolve().parents[2] / "paper_labs" / "02_dhaka_osm"
            / "outputs" / "lab02_v2" / "network" / "dhaka_r1.net.xml")


@dataclass
class RouteResult:
    edges: list[str]
    free_flow_s: float                 # cost of this path with no congestion
    experienced_s: float               # cost of this path under given congestion
    meta: dict = field(default_factory=dict)


class R1Router:
    def __init__(self, net_path: Path = NET_PATH):
        import sumolib
        self.net = sumolib.net.readNet(str(net_path))
        self._edges = {e.getID(): e for e in self.net.getEdges()}

    # ------------------------------------------------------------------ util
    def nearest_edge(self, lat: float, lon: float, radius_m: float = 300.0) -> str:
        x, y = self.net.convertLonLat2XY(lon, lat)
        cands = self.net.getNeighboringEdges(x, y, radius_m)
        if not cands:
            raise ValueError(f"no edge within {radius_m} m of {lat},{lon}")
        edge, _dist = min(cands, key=lambda c: c[1])
        return edge.getID()

    def _base_cost(self, edge_id: str) -> float:
        e = self._edges[edge_id]
        return e.getLength() / max(e.getSpeed(), 0.1)

    # -------------------------------------------------------------- dijkstra
    def _dijkstra(self, src: str, dst: str,
                  congestion: dict[str, float]) -> list[str] | None:
        """Edge-based Dijkstra; congestion maps edge_id -> cost multiplier ≥ 1."""
        dist = {src: self._base_cost(src) * congestion.get(src, 1.0)}
        prev: dict[str, str] = {}
        pq = [(dist[src], src)]
        seen: set[str] = set()
        while pq:
            d, eid = heapq.heappop(pq)
            if eid in seen:
                continue
            seen.add(eid)
            if eid == dst:
                path = [eid]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return path[::-1]
            for nxt in self._edges[eid].getOutgoing():
                nid = nxt.getID()
                nd = d + self._base_cost(nid) * congestion.get(nid, 1.0)
                if nd < dist.get(nid, float("inf")):
                    dist[nid] = nd
                    prev[nid] = eid
                    heapq.heappush(pq, (nd, nid))
        return None

    def _path_cost(self, path: list[str], congestion: dict[str, float]) -> float:
        return sum(self._base_cost(e) * congestion.get(e, 1.0) for e in path)

    # ----------------------------------------------------------------- route
    def best_route(self, origin: tuple[float, float],
                   dest: tuple[float, float],
                   congestion: dict[str, float] | None = None) -> dict:
        """Compare naive (free-flow) vs congestion-aware routing.

        origin/dest are (lat, lon). congestion maps edge ids to slowdown
        multipliers (e.g. 4.0 = takes 4x as long), typically produced from the
        perception verdict or the forecaster.
        """
        congestion = congestion or {}
        src = self.nearest_edge(*origin)
        dst = self.nearest_edge(*dest)

        naive_edges = self._dijkstra(src, dst, {})
        if naive_edges is None:
            raise ValueError(f"no path {src} -> {dst}")
        informed_edges = self._dijkstra(src, dst, congestion)

        naive = RouteResult(
            edges=naive_edges,
            free_flow_s=self._path_cost(naive_edges, {}),
            experienced_s=self._path_cost(naive_edges, congestion))
        informed = RouteResult(
            edges=informed_edges,
            free_flow_s=self._path_cost(informed_edges, {}),
            experienced_s=self._path_cost(informed_edges, congestion))

        return {
            "src_edge": src, "dst_edge": dst,
            "congested_edges_applied": len(congestion),
            "naive": {"n_edges": len(naive.edges),
                      "free_flow_s": round(naive.free_flow_s, 1),
                      "experienced_s": round(naive.experienced_s, 1)},
            "informed": {"n_edges": len(informed.edges),
                         "free_flow_s": round(informed.free_flow_s, 1),
                         "experienced_s": round(informed.experienced_s, 1)},
            "delay_avoided_s": round(naive.experienced_s
                                     - informed.experienced_s, 1),
            "rerouted": naive.edges != informed.edges,
            "note": "edge-cost estimate on the frozen R1 network; the "
                    "twin-simulated multi-seed proof is the integration-gate "
                    "deliverable (E4 precedent: 19.5-22.2%, p<=1.3e-03)",
        }


if __name__ == "__main__":
    import json
    r = R1Router()
    farmgate = (23.7573, 90.3854)
    shahbagh = (23.7389, 90.3958)
    free = r.best_route(farmgate, shahbagh)
    # Congest the naive route's spine and watch the router divert.
    jam = {e: 5.0 for e in r._dijkstra(free["src_edge"], free["dst_edge"], {})[2:12]}
    jammed = r.best_route(farmgate, shahbagh, jam)
    print(json.dumps({"free_flow_case": free, "jam_case": jammed}, indent=1))
