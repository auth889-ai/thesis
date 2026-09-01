from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .metrics import mae, rmse, smape
from .utils import read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--features", required=True)
    parser.add_argument("--actual")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()

    model = joblib.load(args.model)
    protocol = read_json(args.protocol, {})
    feature_names = list(protocol.get("numeric_features", [])) + list(protocol.get("categorical_features", []))
    if not feature_names:
        raise RuntimeError("training_protocol.json does not list feature columns")
    features = pd.read_parquet(args.features)
    for column in feature_names:
        if column not in features:
            features[column] = "unknown" if column == "fclass" else np.nan
    predictions = features[[c for c in ["detid", "edge_id", "lane_id", "day", "hour"] if c in features]].copy()
    predictions["predicted_flow"] = np.clip(model.predict(features[feature_names]), 0, None) * args.scale
    predictions["predicted_flow"] = predictions["predicted_flow"].round(3)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(out / "berlin_predictions.csv", index=False)
    predictions.to_parquet(out / "berlin_predictions.parquet", index=False)

    comparison_metrics = None
    if args.actual and Path(args.actual).exists():
        actual = pd.read_parquet(args.actual) if str(args.actual).endswith(".parquet") else pd.read_csv(args.actual)
        actual["detid"] = actual["detid"].astype(str)
        predictions["detid"] = predictions["detid"].astype(str)
        joined = actual.merge(predictions[["detid", "hour", "predicted_flow"]], on=["detid", "hour"], how="inner")
        joined.to_csv(out / "actual_vs_predicted_all_days.csv", index=False)
        if not joined.empty:
            comparison_metrics = {
                "rows": len(joined),
                "detectors": int(joined["detid"].nunique()),
                "MAE": mae(joined["actual_flow"], joined["predicted_flow"]),
                "RMSE": rmse(joined["actual_flow"], joined["predicted_flow"]),
                "SMAPE_percent": smape(joined["actual_flow"], joined["predicted_flow"]),
            }
            pd.DataFrame([comparison_metrics]).to_csv(out / "actual_vs_predicted_metrics.csv", index=False)
    write_json(out / "prediction_audit.json", {
        "prediction_rows": len(predictions),
        "detectors": int(predictions["detid"].nunique()),
        "feature_names": feature_names,
        "scale": args.scale,
        "actual_comparison": comparison_metrics,
        "warning": "Berlin IDs, per-lane versus detector-total units, and mapping must be verified before interpreting errors.",
    })
    print(predictions.head().to_string(index=False))
    if comparison_metrics:
        print(comparison_metrics)


if __name__ == "__main__":
    main()
