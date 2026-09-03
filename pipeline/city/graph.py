"""The road graph for any city, and the STABLE OBSERVATION NODES a forecast is defined on.

This replaces the mistake at the centre of the old design: treating an origin-destination route
query as if it were a sensor. An OD route is not a stable object — it changes with traffic, the
router can return a different path minute to minute, and two routes that overlap double-count the
same tarmac. A forecasting node must be a fixed piece of road that means the same thing tomorrow.

So a node here is a MAJOR ROAD EDGE, chosen deterministically from the city's OSM graph:

    node_id      stable, derived from the OSM edge identity — same city, same nodes, every run
    edge_id      the OSM edge it observes
    lat, lon     the edge midpoint, where a reading is attributed
    road_class   motorway / trunk / primary / secondary — why it was selected
    neighbors    node_ids sharing an intersection, from real topology

Adjacency comes from the road network itself, not from route overlap. The resulting tensor is
T x N x F over fixed road segments, which is the shape every spatio-temporal model in this project
— and OpenCity in particular — actually expects.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path

# Road classes worth observing, most important first. A city's arterial network is where
# congestion is decided; residential streets add nodes without adding signal.
ROAD_CLASSES = ("motorway", "trunk", "primary", "secondary", "tertiary")
CUSTOM_FILTER = ('["highway"~"motorway|trunk|primary|secondary|tertiary"]')


@dataclass
class ObservationNode:
    node_id: str
    edge_id: str
    lat: float
    lon: float
    road_class: str
    road_name: str
    length_m: float
    speed_kph: float | None
    neighbors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _stable_id(u, v, key, name: str) -> str:
    """Deterministic node id: the same road edge yields the same id on every machine and run."""
    raw = f"{u}|{v}|{key}|{name}"
    return "n" + hashlib.sha1(raw.encode()).hexdigest()[:12]


def _cls(highway) -> str:
    if isinstance(highway, list):
        for c in ROAD_CLASSES:
            if any(c in str(h) for h in highway):
                return c
        return str(highway[0])
    h = str(highway)
    for c in ROAD_CLASSES:
        if c in h:
            return c
    return h


class CityGraph:
    """A city's drivable road network plus its selected observation nodes."""

    def __init__(self, city_id: str, G, nodes: list[ObservationNode]):
        self.city_id = city_id
        self.G = G
        self.nodes = nodes

    # ------------------------------------------------------------------ build
    @classmethod
    def build(cls, city_id: str, *, bbox=None, place: str | None = None,
              max_nodes: int = 250, network_type: str = "drive") -> "CityGraph":
        """Download (or load) the road network and select observation nodes.

        `bbox` is (south, west, north, east) in this project's convention; osmnx 2.x wants
        (west, south, east, north), so it is converted here rather than at every call site.
        """
        import osmnx as ox
        if bbox is not None:
            s, w, n, e = bbox
            G = ox.graph_from_bbox((w, s, e, n), network_type=network_type,
                                   simplify=True, truncate_by_edge=True,
                                   custom_filter=CUSTOM_FILTER)
        elif place:
            G = ox.graph_from_place(place, network_type=network_type, simplify=True,
                                    custom_filter=CUSTOM_FILTER)
        else:
            raise ValueError("need either bbox or place")
        return cls(city_id, G, cls.select_nodes(G, max_nodes))

    # ------------------------------------------------------- node selection
    @staticmethod
    def select_nodes(G, max_nodes: int) -> list[ObservationNode]:
        """Deterministically pick the most significant road segments as observation points.

        Ranked by road class first (motorway before tertiary) and then by length, with the stable
        id as the final tie-break so the ordering never depends on dictionary iteration order.
        A city therefore yields the same node set on every run, which is what makes a time series
        over these nodes meaningful at all.
        """
        cand = []
        for u, v, key, data in G.edges(keys=True, data=True):
            rc = _cls(data.get("highway", ""))
            if rc not in ROAD_CLASSES:
                continue
            name = data.get("name", "")
            name = name[0] if isinstance(name, list) and name else (name if isinstance(name, str) else "")
            length = float(data.get("length", 0.0) or 0.0)
            nid = _stable_id(u, v, key, name)
            cand.append((ROAD_CLASSES.index(rc), -length, nid, u, v, key, rc, name, length, data))

        # Ranking purely by road class fills the whole quota with motorways and trunks before a
        # single primary road is considered, which produces a disconnected set of long highway
        # stretches rather than a city network. Allocate the quota ACROSS classes in proportion to
        # what the city actually has, so the observed graph resembles the road network.
        by_class: dict[str, list] = {}
        for c in cand:
            by_class.setdefault(c[6], []).append(c)
        for v in by_class.values():
            v.sort(key=lambda t: (t[1], t[2]))          # longest first, stable tie-break

        total = sum(len(v) for v in by_class.values()) or 1
        quota = {rc: max(1, round(max_nodes * len(v) / total)) for rc, v in by_class.items()}
        chosen = []
        for rc in ROAD_CLASSES:                          # deterministic class order
            chosen.extend(by_class.get(rc, [])[:quota.get(rc, 0)])
        # top up (or trim) to the requested size, keeping the deterministic ordering
        if len(chosen) < max_nodes:
            taken = {c[2] for c in chosen}
            rest = [c for c in cand if c[2] not in taken]
            rest.sort(key=lambda t: (t[0], t[1], t[2]))
            chosen.extend(rest[:max_nodes - len(chosen)])
        chosen = sorted(chosen, key=lambda t: (t[0], t[1], t[2]))[:max_nodes]

        # Neighbours by hop-limited BFS through the FULL road graph, not just shared endpoints.
        # Two observed segments on the same arterial are genuinely connected even when the short
        # stretch between them was not selected; requiring a shared intersection would declare
        # most of a real city's network isolated, which is a modelling error, not a property of
        # the roads.
        import collections
        at: dict[object, list[str]] = {}
        for _, _, nid, u, v, *_ in chosen:
            at.setdefault(u, []).append(nid)
            at.setdefault(v, []).append(nid)

        HOPS = 3
        undirected = collections.defaultdict(set)
        for a, b in G.edges():
            undirected[a].add(b)
            undirected[b].add(a)

        reach: dict[str, set] = {}
        for _, _, nid, u, v, *_ in chosen:
            seen, frontier = {u, v}, {u, v}
            for _ in range(HOPS):
                nxt = set()
                for x in frontier:
                    nxt |= undirected.get(x, set())
                nxt -= seen
                seen |= nxt
                frontier = nxt
                if not frontier:
                    break
            reach[nid] = seen

        out = []
        for _, _, nid, u, v, key, rc, name, length, data in chosen:
            ux, uy = G.nodes[u].get("x"), G.nodes[u].get("y")
            vx, vy = G.nodes[v].get("x"), G.nodes[v].get("y")
            lat = (uy + vy) / 2 if uy is not None and vy is not None else uy
            lon = (ux + vx) / 2 if ux is not None and vx is not None else ux
            nb = sorted({m for endpoint in reach.get(nid, set())
                         for m in at.get(endpoint, []) if m != nid})
            spd = data.get("maxspeed")
            if isinstance(spd, list):
                spd = spd[0] if spd else None
            try:
                spd = float(str(spd).split()[0]) if spd else None
            except (ValueError, IndexError):
                spd = None
            out.append(ObservationNode(node_id=nid, edge_id=f"{u}-{v}-{key}",
                                       lat=float(lat), lon=float(lon), road_class=rc,
                                       road_name=name, length_m=round(length, 1),
                                       speed_kph=spd, neighbors=nb))
        return out

    # ---------------------------------------------------------- adjacency
    def adjacency(self) -> "list[list[float]]":
        """N x N from real road topology: 1.0 where two observed segments share an intersection."""
        idx = {n.node_id: i for i, n in enumerate(self.nodes)}
        N = len(self.nodes)
        A = [[0.0] * N for _ in range(N)]
        for i, n in enumerate(self.nodes):
            A[i][i] = 1.0
            for m in n.neighbors:
                j = idx.get(m)
                if j is not None:
                    A[i][j] = A[j][i] = 1.0
        return A

    # ------------------------------------------------------------- persist
    def summary(self) -> dict:
        by_class: dict[str, int] = {}
        for n in self.nodes:
            by_class[n.road_class] = by_class.get(n.road_class, 0) + 1
        deg = [len(n.neighbors) for n in self.nodes]
        return {
            "city_id": self.city_id,
            "graph_nodes": self.G.number_of_nodes(),
            "graph_edges": self.G.number_of_edges(),
            "observation_nodes": len(self.nodes),
            "by_road_class": by_class,
            "mean_degree": round(sum(deg) / len(deg), 2) if deg else 0.0,
            "isolated_nodes": sum(1 for d in deg if d == 0),
            "total_km": round(sum(n.length_m for n in self.nodes) / 1000, 2),
            "node_selection": ("deterministic: road class, then length, then stable hash id — "
                               "the same city yields the same nodes on every run"),
            "adjacency": ("connected within 3 road-graph hops in the OSM network — real "
                          "topology, not route overlap"),
        }

    def save(self, out: Path) -> dict:
        out.mkdir(parents=True, exist_ok=True)
        (out / "nodes.json").write_text(json.dumps([n.to_dict() for n in self.nodes], indent=1))
        (out / "adjacency.json").write_text(json.dumps(self.adjacency()))
        s = self.summary()
        (out / "graph_summary.json").write_text(json.dumps(s, indent=1))
        return s

    @classmethod
    def load(cls, city_id: str, out: Path) -> "CityGraph":
        nodes = [ObservationNode(**d) for d in json.loads((out / "nodes.json").read_text())]
        return cls(city_id, None, nodes)
