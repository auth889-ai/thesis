from __future__ import annotations

import argparse
import random
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path

import pandas as pd

from .utils import run, sumo_env, sumo_tool, which_or_fail, write_json


def eligible_edges(net, vclass: str):
    result = []
    for edge in net.getEdges():
        if edge.isSpecial():
            continue
        try:
            allowed = edge.allows(vclass)
        except Exception:
            allowed = any(lane.allows(vclass) for lane in edge.getLanes())
        if allowed:
            result.append(edge)
    return result


def adjacency(net, edges):
    allowed = {e.getID(): e for e in edges}
    forward: dict[str, set[str]] = defaultdict(set)
    backward: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        outgoing = edge.getOutgoing()
        targets = outgoing.keys() if hasattr(outgoing, "keys") else outgoing
        for target in targets:
            if target.getID() in allowed:
                forward[edge.getID()].add(target.getID())
                backward[target.getID()].add(edge.getID())
    return forward, backward


def nearby(start: str, graph: dict[str, set[str]], max_depth: int = 10, max_items: int = 80) -> list[str]:
    seen = {start}
    queue = deque([(start, 0)])
    values = []
    while queue and len(values) < max_items:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for nxt in graph.get(current, set()):
            if nxt in seen:
                continue
            seen.add(nxt)
            values.append(nxt)
            queue.append((nxt, depth + 1))
    return values


def write_taz_trips(taz_csv: Path, output: Path, count: int, begin: int, end: int, seed: int) -> None:
    taz_ids = sorted(pd.read_csv(taz_csv)["taz_id"].dropna().astype(str).unique())
    if len(taz_ids) < 2:
        raise RuntimeError("At least two TAZs are required")
    rng = random.Random(seed)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="passenger", vClass="passenger", accel="2.6", decel="4.5", sigma="0.5")
    for index in range(count):
        origin, destination = rng.sample(taz_ids, 2)
        depart = begin + (end - begin) * (index + rng.random()) / max(count, 1)
        ET.SubElement(root, "trip", id=f"tazTrip_{index}", type="passenger",
                      depart=f"{depart:.2f}", fromTaz=origin, toTaz=destination,
                      departLane="best", departSpeed="max")
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)


def write_coverage_trips(net_path: str, mapping_csv: str, output: Path, routes_per_detector: int,
                         begin: int, end: int, seed: int, vclass: str) -> dict:
    import sumolib  # type: ignore
    net = sumolib.net.readNet(net_path, withInternal=False)
    edges = eligible_edges(net, vclass)
    edge_ids = {edge.getID() for edge in edges}
    forward, backward = adjacency(net, edges)
    mapping = pd.read_csv(mapping_csv).dropna(subset=["edge_id"])
    rng = random.Random(seed)
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="passenger", vClass="passenger", accel="2.6", decel="4.5", sigma="0.5")
    made = 0
    diagnostics = []
    for row in mapping.itertuples(index=False):
        monitored = str(row.edge_id)
        if monitored not in edge_ids:
            diagnostics.append({"detid": row.detid, "edge_id": monitored, "status": "edge_missing"})
            continue
        origins = nearby(monitored, backward)
        destinations = nearby(monitored, forward)
        if not origins or not destinations:
            diagnostics.append({"detid": row.detid, "edge_id": monitored, "status": "no_context"})
            continue
        count = 0
        for local in range(routes_per_detector):
            origin = rng.choice(origins)
            destination = rng.choice(destinations)
            if origin == destination:
                continue
            depart = begin + rng.random() * max(1, end - begin)
            ET.SubElement(root, "trip", id=f"coverage_{row.detid}_{local}", type="passenger",
                          depart=f"{depart:.2f}", **{"from": origin, "to": destination, "via": monitored},
                          departLane="best", departSpeed="max")
            made += 1
            count += 1
        diagnostics.append({"detid": row.detid, "edge_id": monitored, "status": "written", "trips": count})
    ET.ElementTree(root).write(output, encoding="utf-8", xml_declaration=True)
    return {"coverage_trips": made, "diagnostics": diagnostics}


def duarouter(net: str, trips: Path, output: Path, seed: int, random_factor: float,
              additional: Path | None, log: Path) -> None:
    cmd = [
        which_or_fail("duarouter"), "--net-file", net, "--route-files", str(trips),
        "--output-file", str(output), "--ignore-errors", "true", "--repair", "true",
        "--remove-loops", "true", "--routing-algorithm", "astar",
        "--weights.random-factor", str(random_factor), "--seed", str(seed),
    ]
    if additional:
        cmd += ["--additional-files", str(additional)]
    run(cmd, log=log)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--taz", required=True)
    parser.add_argument("--edge-to-taz", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--random-count", type=int, default=30000)
    parser.add_argument("--taz-count", type=int, default=20000)
    parser.add_argument("--coverage-per-detector", type=int, default=30)
    parser.add_argument("--begin", type=int, default=0)
    parser.add_argument("--end", type=int, default=86400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--random-factor", type=float, default=1.7)
    parser.add_argument("--vclass", default="passenger")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    random_trips = out / "random.trips.xml"
    random_routes = out / "random.routes.xml"
    taz_trips = out / "taz.trips.xml"
    taz_routes = out / "taz.routes.xml"
    coverage_trips = out / "coverage.trips.xml"
    coverage_routes = out / "coverage.routes.xml"

    period = max(0.01, (args.end - args.begin) / max(args.random_count, 1))
    random_tool = sumo_tool("randomTrips.py")
    run([
        sys.executable, str(random_tool), "--net-file", args.net,
        "--output-trip-file", str(random_trips), "--begin", str(args.begin),
        "--end", str(args.end), "--period", str(period), "--seed", str(args.seed),
        "--fringe-factor", "5", "--min-distance", "200", "--max-distance", "20000",
        "--vehicle-class", args.vclass, "--prefix", "random_", "--no-validate",
        "--trip-attributes", 'departLane="best" departSpeed="max"',
    ], log=out / "randomTrips.log", env=sumo_env())
    duarouter(args.net, random_trips, random_routes, args.seed, args.random_factor,
              None, out / "duarouter_random.log")

    write_taz_trips(Path(args.edge_to_taz), taz_trips, args.taz_count,
                    args.begin, args.end, args.seed + 1)
    duarouter(args.net, taz_trips, taz_routes, args.seed + 1, args.random_factor,
              Path(args.taz), out / "duarouter_taz.log")

    coverage_info = write_coverage_trips(
        args.net, args.mapping, coverage_trips, args.coverage_per_detector,
        args.begin, args.end, args.seed + 2, args.vclass,
    )
    duarouter(args.net, coverage_trips, coverage_routes, args.seed + 2,
              args.random_factor, None, out / "duarouter_coverage.log")

    manifest = {
        "route_files": [str(random_routes), str(taz_routes), str(coverage_routes)],
        "trip_files": [str(random_trips), str(taz_trips), str(coverage_trips)],
        "random_count_requested": args.random_count,
        "taz_count_requested": args.taz_count,
        **coverage_info,
        "paper_alignment": "randomTrips + duarouter + TAZ routes, with extra targeted candidates to guarantee monitored-edge coverage.",
        "reconstruction_gap": "The paper does not publish candidate counts, TAZ boundaries, or routing parameters.",
    }
    write_json(out / "candidate_manifest.json", manifest)
    print(manifest)


if __name__ == "__main__":
    main()
