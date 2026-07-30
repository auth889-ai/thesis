from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--merge", choices=["max", "sum", "mean"], default="max")
    parser.add_argument("--scale-counts", type=float, default=1.0)
    parser.add_argument("--begin", type=int, default=0)
    parser.add_argument("--end", type=int, default=86400)
    args = parser.parse_args()

    predictions = pd.read_csv(args.predictions)
    mapping = pd.read_csv(args.mapping)
    if "edge_id" not in predictions:
        predictions = predictions.merge(mapping[["detid", "edge_id"]], on="detid", how="left")
    predictions = predictions.dropna(subset=["edge_id", "hour", "predicted_flow"]).copy()
    predictions["count_scaled"] = (
        pd.to_numeric(predictions["predicted_flow"], errors="coerce")
        .fillna(0).clip(lower=0) * args.scale_counts
    )
    aggregation = {"max": "max", "sum": "sum", "mean": "mean"}[args.merge]
    edge = predictions.groupby(["hour", "edge_id"], as_index=False)["count_scaled"].agg(aggregation)
    edge["count_scaled"] = edge["count_scaled"].round().astype(int)
    edge = edge[(edge["hour"] * 3600 >= args.begin) & (edge["hour"] * 3600 < args.end)]
    edge = edge.rename(columns={"count_scaled": "predicted_count"})

    root = ET.Element("meandata")
    for hour, block in edge.groupby("hour"):
        begin = int(hour) * 3600
        interval = ET.SubElement(root, "interval", id=f"hour_{int(hour):02d}",
                                 begin=str(begin), end=str(begin + 3600))
        for row in block.itertuples(index=False):
            ET.SubElement(interval, "edge", id=str(row.edge_id), entered=str(int(row.predicted_count)))

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    xml_path = out / "predicted_edge_counts.xml"
    ET.ElementTree(root).write(xml_path, encoding="utf-8", xml_declaration=True)
    edge.to_csv(out / "edge_predictions.csv", index=False)
    write_json(out / "edge_count_audit.json", {
        "edge_hour_rows": len(edge), "edges": int(edge["edge_id"].nunique()),
        "total_predicted_vehicles_across_monitored_edges": int(edge["predicted_count"].sum()),
        "merge_same_edge": args.merge, "scale_counts": args.scale_counts,
        "warning": "Counts on several detectors mapped to one edge are merged; inspect edge_predictions.csv.",
    })
    print(edge.head().to_string(index=False))


if __name__ == "__main__":
    main()
