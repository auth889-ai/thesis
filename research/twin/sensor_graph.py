"""P2 — simulated sensor graph on the frozen Dhaka R1 network.

This is the resolution of risk R1 (INTEGRATED_BUILD_PLAN §1): four real camera
sites cannot carry a graph-forecasting benchmark, so the digital twin is
promoted from consumer to producer. We place 100–300 virtual sensors on the
real frozen topology and record 5-minute aggregates, exactly the shape of a
loop-detector benchmark (METR-LA records 207 sensors at 5 min).

Every output is labelled `DHAKA_SIMULATED_SENSOR_GRAPH` and is never described
as a real measurement. The real 4 camera sites remain the held-out validation
anchor (`DHAKA_REAL_VALIDATION_ANCHORS`), and the simulator-circularity guard
in the model registry stands.

Design choices (each tagged per config policy):

* Sensor = SUMO `edgeData` meanData aggregate at `period_s=300`. ASSUMED:
  edge-level aggregation is the loop-detector analog; 300 s matches METR-LA's
  bin width so the forecasting protocol (5/15/30 min horizons) transfers.
* Placement = deterministic rank (lanes, speed limit, length) under a spatial
  grid quota, so sensors cover the region instead of clustering on one
  arterial. ASSUMED, and frozen by sha256 of the node list.
* Adjacency = directed road-network distances + Gaussian kernel with sparsity
  threshold — OFFICIAL: this is DCRNN's own sensor-graph recipe (Li et al.,
  ICLR 2018), reused so graph models receive the graph construction their
  authors published.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

EVIDENCE_DOMAIN = "DHAKA_SIMULATED_SENSOR_GRAPH"
SENSOR_PERIOD_S = 300.0                     # 5-minute bins, METR-LA convention
CHANNELS = ("speed_ms", "density_veh_km", "occupancy_pct", "flow_veh")

# Hourly demand scale factors — two-peak urban day. ASSUMED shape (calibrated
# demand replaces it at the twin gate); the point is non-stationarity, so a
# forecaster has structure to learn.
DAILY_PROFILE: tuple[float, ...] = (
    0.15, 0.10, 0.08, 0.08, 0.12, 0.30,     # 00-05
    0.60, 0.90, 1.00, 0.85, 0.70, 0.65,     # 06-11  (AM peak 08:00)
    0.70, 0.65, 0.60, 0.65, 0.80, 0.95,     # 12-17  (build-up)
    1.00, 0.90, 0.70, 0.50, 0.35, 0.22,     # 18-23  (PM peak 18:00)
)


# ---------------------------------------------------------------------------
# Sensor placement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SensorNode:
    """One virtual sensor: an edge of the frozen network."""

    edge_id: str
    length_m: float
    speed_limit_ms: float
    num_lanes: int
    x: float                                # edge midpoint, network coords
    y: float


def largest_scc(edge_ids: Sequence[str],
                successors: Mapping[str, Sequence[str]]) -> set[str]:
    """Largest strongly-connected component of the edge graph (iterative Kosaraju).

    A sensor outside it sits where traffic structurally cannot circulate — it
    would record zeros forever and poison the forecasting dataset.
    """
    ids = set(edge_ids)
    order: list[str] = []
    seen: set[str] = set()
    for start in edge_ids:
        if start in seen:
            continue
        stack: list[tuple[str, int]] = [(start, 0)]
        seen.add(start)
        while stack:
            node, i = stack[-1]
            nxt = [s for s in successors.get(node, ()) if s in ids]
            if i < len(nxt):
                stack[-1] = (node, i + 1)
                if nxt[i] not in seen:
                    seen.add(nxt[i])
                    stack.append((nxt[i], 0))
            else:
                order.append(node)
                stack.pop()

    rev: dict[str, list[str]] = {e: [] for e in ids}
    for e in ids:
        for s in successors.get(e, ()):
            if s in ids:
                rev[s].append(e)

    best: set[str] = set()
    assigned: set[str] = set()
    for start in reversed(order):
        if start in assigned:
            continue
        comp = {start}
        assigned.add(start)
        stack2 = [start]
        while stack2:
            node = stack2.pop()
            for p in rev[node]:
                if p not in assigned:
                    assigned.add(p)
                    comp.add(p)
                    stack2.append(p)
        if len(comp) > len(best):
            best = comp
    return best


def select_sensor_edges(net_path: Path, n_target: int = 250,
                        min_length_m: float = 50.0,
                        grid: int = 12) -> list[SensorNode]:
    """Deterministic sensor placement on the frozen network.

    Candidates are restricted to the largest strongly-connected component of
    the passenger edge graph (a sensor traffic cannot reach measures nothing),
    then ranked by (lanes, speed limit, length) — arterial capacity — and a
    `grid`×`grid` spatial quota is filled round-robin so coverage is
    network-wide. Same network file ⇒ same node list, byte for byte.
    """
    import sumolib

    if not (100 <= n_target <= 300):
        raise ValueError(
            f"n_target={n_target}: the mandate is a 100-300 node graph")

    net = sumolib.net.readNet(str(net_path))
    passenger = [e for e in net.getEdges()
                 if not e.getID().startswith(":") and e.allows("passenger")]
    succ = {e.getID(): [o.getID() for o in e.getOutgoing()
                        if o.allows("passenger")]
            for e in passenger}
    core = largest_scc([e.getID() for e in passenger], succ)

    candidates: list[SensorNode] = []
    for e in passenger:
        eid = e.getID()
        if eid not in core:
            continue
        if float(e.getLength()) < min_length_m:
            continue
        shape = e.getShape()
        mid = shape[len(shape) // 2]
        candidates.append(SensorNode(
            edge_id=eid,
            length_m=float(e.getLength()),
            speed_limit_ms=float(e.getSpeed()),
            num_lanes=len(e.getLanes()),
            x=float(mid[0]), y=float(mid[1]),
        ))
    if len(candidates) < n_target:
        raise ValueError(
            f"only {len(candidates)} candidate edges for {n_target} sensors")

    xs = [c.x for c in candidates]
    ys = [c.y for c in candidates]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)

    def cell(c: SensorNode) -> tuple[int, int]:
        gx = min(int((c.x - x0) / max(x1 - x0, 1e-9) * grid), grid - 1)
        gy = min(int((c.y - y0) / max(y1 - y0, 1e-9) * grid), grid - 1)
        return gx, gy

    ranked = sorted(candidates,
                    key=lambda c: (-c.num_lanes, -c.speed_limit_ms,
                                   -c.length_m, c.edge_id))
    buckets: dict[tuple[int, int], list[SensorNode]] = {}
    for c in ranked:
        buckets.setdefault(cell(c), []).append(c)

    # Round-robin across occupied cells, best-ranked first within each.
    selected: list[SensorNode] = []
    order = sorted(buckets)                  # deterministic cell order
    depth = 0
    while len(selected) < n_target:
        progressed = False
        for key in order:
            b = buckets[key]
            if depth < len(b):
                selected.append(b[depth])
                progressed = True
                if len(selected) == n_target:
                    break
        if not progressed:                   # every bucket exhausted
            break
        depth += 1
    return sorted(selected[:n_target], key=lambda c: c.edge_id)


def node_list_sha256(nodes: Sequence[SensorNode]) -> str:
    return hashlib.sha256(
        "\n".join(n.edge_id for n in nodes).encode()).hexdigest()


def write_sensor_additional(nodes: Sequence[SensorNode], add_file: Path,
                            output_file: Path,
                            period_s: float = SENSOR_PERIOD_S) -> Path:
    """SUMO additional-file declaring the edgeData sensor aggregation."""
    edges = " ".join(n.edge_id for n in nodes)
    add_file.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<additional>\n'
        f'    <edgeData id="p2_sensor_graph" file="{output_file}" '
        f'period="{period_s:g}" edges="{edges}" excludeEmpty="false"/>\n'
        '</additional>\n')
    return add_file


# ---------------------------------------------------------------------------
# Adjacency — DCRNN's published recipe on road-network distances
# ---------------------------------------------------------------------------

def road_distances(graph, sensor_edges: Sequence[str]) -> np.ndarray:
    """Directed road-network distance (m) between sensor edges.

    `graph` is a `dhakaflow.routing.graph_router.NetworkGraph`. Distance i→j is
    the shortest driven length from the END of edge i to the END of edge j
    (i.e. traversing j), via Dijkstra over edge lengths. inf where unreachable.
    """
    index = {e: k for k, e in enumerate(sensor_edges)}
    n = len(sensor_edges)
    dist = np.full((n, n), np.inf)
    np.fill_diagonal(dist, 0.0)

    for src_i, src in enumerate(sensor_edges):
        # Dijkstra over edges: cost to have fully traversed each edge, starting
        # after src (cost of src itself excluded — it is the sensor location).
        best: dict[str, float] = {src: 0.0}
        heap: list[tuple[float, str]] = [(0.0, src)]
        while heap:
            d, eid = heapq.heappop(heap)
            if d > best.get(eid, np.inf):
                continue
            for nxt in graph.successors(eid):
                nd = d + graph.edge(nxt).length_m
                if nd < best.get(nxt, np.inf):
                    best[nxt] = nd
                    heapq.heappush(heap, (nd, nxt))
        for tgt, k in index.items():
            if tgt in best and k != src_i:
                dist[src_i, k] = best[tgt]
    return dist


def gaussian_kernel_adjacency(dist_m: np.ndarray,
                              threshold: float = 0.1) -> np.ndarray:
    """DCRNN (Li et al., ICLR 2018): W_ij = exp(-d_ij²/σ²), sparsified.

    σ is the standard deviation of the finite distances; entries below
    `threshold` are zeroed. Directed — Dhaka one-ways stay one-way.
    """
    finite = dist_m[np.isfinite(dist_m) & (dist_m > 0)]
    if finite.size == 0:
        raise ValueError("no finite inter-sensor distances — graph is disconnected")
    sigma = finite.std()
    if sigma <= 0:
        raise ValueError("degenerate distance distribution (σ=0)")
    with np.errstate(over="ignore"):
        w = np.exp(-np.square(dist_m / sigma))
    w[~np.isfinite(dist_m)] = 0.0
    w[w < threshold] = 0.0
    np.fill_diagonal(w, 1.0)
    return w


# ---------------------------------------------------------------------------
# Time-series extraction from SUMO edgeData output
# ---------------------------------------------------------------------------

def parse_edgedata(xml_path: Path, sensor_edges: Sequence[str]
                   ) -> tuple[np.ndarray, np.ndarray]:
    """meanData XML → (T, N, C) float array + (T, N) validity mask.

    Channels follow `CHANNELS`. An interval with zero traffic on an edge is a
    REAL zero for flow/density/occupancy, but speed is UNDEFINED there — speed
    becomes NaN and the mask goes False (missing is never silently 0; Lab 00
    lesson, platform decision 4).
    """
    index = {e: k for k, e in enumerate(sensor_edges)}
    n = len(sensor_edges)
    frames: list[np.ndarray] = []
    masks: list[np.ndarray] = []

    for _, elem in ET.iterparse(str(xml_path)):
        if elem.tag != "interval":
            continue
        frame = np.full((n, len(CHANNELS)), np.nan)
        mask = np.zeros(n, dtype=bool)
        for edge in elem.iter("edge"):
            k = index.get(edge.get("id"))
            if k is None:
                continue
            speed = float(edge.get("speed", -1.0))
            entered = float(edge.get("entered", 0.0))
            density = float(edge.get("density", 0.0))
            occupancy = float(edge.get("occupancy", 0.0))
            sampled = float(edge.get("sampledSeconds", 0.0))
            if sampled > 0 and speed >= 0:
                frame[k] = (speed, density, occupancy, entered)
                mask[k] = True
            else:                            # zero traffic: true zeros, no speed
                frame[k] = (np.nan, 0.0, 0.0, 0.0)
        frames.append(frame)
        masks.append(mask)
        elem.clear()

    if not frames:
        raise ValueError(f"{xml_path}: no intervals parsed — SUMO produced no sensor data")
    return np.stack(frames), np.stack(masks)


# ---------------------------------------------------------------------------
# Dataset assembly + manifest
# ---------------------------------------------------------------------------

def save_dataset(out_dir: Path, data: np.ndarray, mask: np.ndarray,
                 adjacency: np.ndarray, dist_m: np.ndarray,
                 nodes: Sequence[SensorNode], *,
                 network_sha256: str, seeds: Sequence[int],
                 config: Mapping[str, object]) -> Path:
    """Write the benchmark bundle: arrays + node table + labelled manifest."""
    out_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_dir / "sensor_graph_data.npz",
                        data=data, mask=mask, adjacency=adjacency,
                        distances_m=dist_m)
    (out_dir / "sensor_nodes.json").write_text(json.dumps(
        [vars(nd) for nd in nodes], indent=1))

    t, n, c = data.shape
    manifest = {
        "evidence_domain": EVIDENCE_DOMAIN,
        "never_described_as": "real sensor measurements",
        "reality_label": "SIMULATED",
        "shape": {"timesteps": t, "nodes": n, "channels": c},
        "channels": list(CHANNELS),
        "period_s": SENSOR_PERIOD_S,
        "node_list_sha256": node_list_sha256(nodes),
        "network_sha256": network_sha256,
        "seeds": list(seeds),
        "adjacency_recipe": "DCRNN gaussian kernel on directed road distances "
                            "(Li et al., ICLR 2018), threshold 0.1  [OFFICIAL]",
        "missing_value_policy": "speed NaN + mask=False when no vehicle sampled; "
                                "flow/density/occupancy true zeros",
        "config": dict(config),
    }
    p = out_dir / "MANIFEST.json"
    p.write_text(json.dumps(manifest, indent=2))
    return p
