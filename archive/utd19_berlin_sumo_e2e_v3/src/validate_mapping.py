from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--vclass", default="passenger")
    args = parser.parse_args()

    try:
        import sumolib  # type: ignore
    except Exception as exc:
        raise RuntimeError("sumolib is required") from exc

    mapping = pd.read_csv(args.mapping)
    required = {"detid", "edge_id", "lane_id"}
    missing = required - set(mapping.columns)
    if missing:
        raise KeyError(f"Mapping missing columns: {sorted(missing)}")
    duplicate_detectors = mapping[mapping.duplicated("detid", keep=False)]["detid"].astype(str).unique().tolist()
    net = sumolib.net.readNet(args.net, withInternal=False)
    valid_edges = {e.getID(): e for e in net.getEdges() if not e.isSpecial()}
    rows = []
    for row in mapping.itertuples(index=False):
        edge_id = str(row.edge_id)
        lane_id = str(row.lane_id)
        edge = valid_edges.get(edge_id)
        reasons = []
        if edge is None:
            reasons.append("edge_missing")
        else:
            lane_ids = {lane.getID() for lane in edge.getLanes()}
            if lane_id not in lane_ids:
                reasons.append("lane_not_on_edge")
            try:
                if not edge.allows(args.vclass):
                    reasons.append("passenger_not_allowed")
            except Exception:
                pass
        rows.append({"detid": row.detid, "edge_id": edge_id, "lane_id": lane_id,
                     "valid": not reasons, "reasons": "|".join(reasons)})
    report = pd.DataFrame(rows)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report.to_csv(out / "mapping_validation.csv", index=False)
    summary = {
        "rows": len(report),
        "unique_detectors": int(mapping["detid"].nunique()),
        "duplicate_detector_ids": duplicate_detectors,
        "valid_rows": int(report["valid"].sum()),
        "invalid_rows": int((~report["valid"]).sum()),
        "mapping_status_values": mapping["status"].astype(str).value_counts().to_dict() if "status" in mapping else {},
    }
    write_json(out / "mapping_validation_summary.json", summary)
    print(summary)
    if duplicate_detectors or not report["valid"].all():
        raise RuntimeError("Accepted detector mapping failed structural validation")


if __name__ == "__main__":
    main()
