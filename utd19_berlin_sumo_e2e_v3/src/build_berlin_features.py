from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--prediction-date", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--begin-hour", type=int, default=0)
    parser.add_argument("--end-hour", type=int, default=24)
    parser.add_argument("--population", type=float)
    parser.add_argument("--population-density", type=float)
    parser.add_argument("--lane-density", type=float)
    args = parser.parse_args()

    mapping = pd.read_csv(args.mapping)
    required = {
        "detid", "edge_id", "length_km", "pos_km", "fclass",
        "speed_limit_kmh", "monitored_lanes",
    }
    missing = required - set(mapping.columns)
    if missing:
        raise KeyError(f"Accepted mapping is missing: {sorted(missing)}")
    mapping = mapping.drop_duplicates("detid").copy()
    date = pd.Timestamp(args.prediction_date)
    rows = []
    for row in mapping.to_dict("records"):
        for hour in range(args.begin_hour, args.end_hour):
            rec = dict(row)
            rec.update({
                "city": "berlin",
                "day": date.date().isoformat(),
                "hour": hour,
                "weekday": int(date.dayofweek),
                "is_weekend": int(date.dayofweek >= 5),
                "month": int(date.month),
                "day_of_year": int(date.dayofyear),
                "population": args.population if args.population is not None else np.nan,
                "population_density": args.population_density if args.population_density is not None else np.nan,
                "lane_density": args.lane_density if args.lane_density is not None else np.nan,
            })
            rows.append(rec)
    features = pd.DataFrame(rows)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    features.to_parquet(out / "berlin_features.parquet", index=False)
    features.to_csv(out / "berlin_features.csv", index=False)
    write_json(out / "berlin_feature_audit.json", {
        "rows": len(features), "detectors": int(features["detid"].nunique()),
        "prediction_date": str(date.date()), "hours": [args.begin_hour, args.end_hour],
        "note": "Road features come from the accepted SUMO mapping; city-level features remain missing unless explicitly sourced.",
    })
    print(features.head().to_string(index=False))


if __name__ == "__main__":
    main()
