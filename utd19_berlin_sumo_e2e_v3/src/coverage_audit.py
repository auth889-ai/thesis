from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .utils import write_json


def route_edge_sets(path: Path) -> list[set[str]]:
    result: list[set[str]] = []
    route_defs: dict[str, set[str]] = {}
    for event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "route":
            edges = set((elem.attrib.get("edges") or "").split())
            if elem.attrib.get("id"):
                route_defs[elem.attrib["id"]] = edges
            if edges:
                result.append(edges)
        elif elem.tag in {"vehicle", "flow"}:
            route_id = elem.attrib.get("route")
            if route_id and route_id in route_defs:
                result.append(route_defs[route_id])
        elem.clear()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--route-files", nargs="+", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    mapping = pd.read_csv(args.mapping).dropna(subset=["edge_id"])
    coverage_count: dict[str, int] = {str(edge): 0 for edge in mapping["edge_id"].astype(str).unique()}
    total_routes = 0
    for path_string in args.route_files:
        paths = route_edge_sets(Path(path_string))
        total_routes += len(paths)
        for edges in paths:
            for monitored in set(coverage_count).intersection(edges):
                coverage_count[monitored] += 1
    rows = []
    for row in mapping.itertuples(index=False):
        count = coverage_count.get(str(row.edge_id), 0)
        rows.append({"detid": row.detid, "edge_id": row.edge_id,
                     "candidate_route_count": count, "covered": count > 0})
    report = pd.DataFrame(rows)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report.to_csv(out / "candidate_coverage.csv", index=False)
    summary = {
        "route_instances_parsed": total_routes,
        "detectors": len(report),
        "covered_detectors": int(report["covered"].sum()),
        "coverage_percent": float(100 * report["covered"].mean()) if len(report) else 0,
        "uncovered": report.loc[~report["covered"], ["detid", "edge_id"]].to_dict("records"),
    }
    write_json(out / "candidate_coverage_summary.json", summary)
    print(summary)
    if args.require_complete and not report["covered"].all():
        raise RuntimeError("Candidate route coverage is incomplete; routeSampler cannot calibrate uncovered edges.")


if __name__ == "__main__":
    main()
