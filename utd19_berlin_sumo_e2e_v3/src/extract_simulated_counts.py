from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .utils import write_json


def parse_edge_data(path: Path) -> pd.DataFrame:
    rows = []
    if not path.exists():
        raise FileNotFoundError(path)
    root = ET.parse(path).getroot()
    for interval in root.findall(".//interval"):
        begin = float(interval.attrib.get("begin", 0))
        hour = int(begin // 3600)
        for edge in interval.findall("edge"):
            rows.append({
                "hour": hour,
                "begin": begin,
                "end": float(interval.attrib.get("end", begin + 3600)),
                "edge_id": edge.attrib.get("id"),
                "simulated_count": float(edge.attrib.get("entered", 0) or 0),
                "departed": float(edge.attrib.get("departed", 0) or 0),
                "arrived": float(edge.attrib.get("arrived", 0) or 0),
                "left": float(edge.attrib.get("left", 0) or 0),
            })
    return pd.DataFrame(rows)


def parse_summary(path: Path) -> pd.DataFrame:
    rows = []
    if not path.exists():
        return pd.DataFrame()
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "step":
            rows.append({key: pd.to_numeric(value, errors="coerce") for key, value in elem.attrib.items()})
        elem.clear()
    return pd.DataFrame(rows)


def parse_statistics(path: Path) -> dict:
    if not path.exists():
        return {}
    root = ET.parse(path).getroot()
    result = {}
    for child in list(root):
        if child.attrib:
            result[child.tag] = {
                key: (float(value) if any(ch in value for ch in ".eE") else int(value))
                if value.replace(".", "", 1).replace("-", "", 1).replace("e", "", 1).replace("E", "", 1).isdigit()
                else value
                for key, value in child.attrib.items()
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edge-data", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--summary")
    parser.add_argument("--statistics")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    edge = parse_edge_data(Path(args.edge_data))
    mapping = pd.read_csv(args.mapping)
    edge.to_csv(out / "simulated_edge_counts.csv", index=False)
    detector = mapping[["detid", "edge_id"]].drop_duplicates().merge(edge, on="edge_id", how="left")
    detector.to_csv(out / "simulated_detector_counts.csv", index=False)
    summary = parse_summary(Path(args.summary)) if args.summary else pd.DataFrame()
    statistics = parse_statistics(Path(args.statistics)) if args.statistics else {}
    if statistics:
        write_json(out / "simulation_statistics.json", statistics)
    if not summary.empty:
        summary.to_csv(out / "summary_steps.csv", index=False)
        if "time" in summary and "running" in summary:
            summary["hour"] = (summary["time"] // 3600).astype(int)
            hourly_summary = summary.groupby("hour", as_index=False).agg(
                running_mean=("running", "mean"),
                running_max=("running", "max"),
                inserted_max=("inserted", "max") if "inserted" in summary else ("running", "count"),
                ended_max=("ended", "max") if "ended" in summary else ("running", "count"),
                waiting_max=("waiting", "max") if "waiting" in summary else ("running", "count"),
            )
            hourly_summary.to_csv(out / "network_hourly_summary.csv", index=False)
    audit = {
        "edge_hour_rows": len(edge), "edges": int(edge["edge_id"].nunique()) if not edge.empty else 0,
        "detector_hour_rows": len(detector), "summary_steps": len(summary),
        "statistics": statistics,
        "inserted_vehicles": statistics.get("vehicles", {}).get("inserted") if statistics else None,
        "teleports": statistics.get("teleports", {}).get("total") if statistics else None,
    }
    write_json(out / "extraction_audit.json", audit)
    print(audit)


if __name__ == "__main__":
    main()
