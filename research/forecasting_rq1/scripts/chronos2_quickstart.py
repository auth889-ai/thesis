"""Chronos-2's own README example (chronos-forecasting README, "Forecasting"), run unchanged except device_map="cpu".
The repository publishes no per-dataset numbers for Chronos-2, so nothing can be compared to a published value; the run is
recorded (shapes, the first forecasts, and our own MAE against the example's test file) to show the model loads and works.
Output: evidence/forecasting/reproduce/chronos2/result.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from chronos import Chronos2Pipeline

OUT = Path(__file__).resolve().parents[3] / "evidence/forecasting/reproduce/chronos2/result.json"
pipeline = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
context_df = pd.read_parquet("https://autogluon.s3.amazonaws.com/datasets/timeseries/electricity_price/train.parquet")
test_df = pd.read_parquet("https://autogluon.s3.amazonaws.com/datasets/timeseries/electricity_price/test.parquet")
future_df = test_df.drop(columns="target")
pred_df = pipeline.predict_df(context_df, future_df=future_df, prediction_length=24, quantile_levels=[0.1, 0.5, 0.9],
                              id_column="id", timestamp_column="timestamp", target="target")
merged = pred_df.merge(test_df[["id", "timestamp", "target"]], on=["id", "timestamp"])
OUT.write_text(json.dumps({"example": "chronos-forecasting README 'Forecasting' (electricity_price with covariates)", "device": "cpu",
                           "pred_rows": len(pred_df), "pred_columns": list(map(str, pred_df.columns)), "series": int(pred_df["id"].nunique()),
                           "first_predictions": [round(float(x), 4) for x in pred_df["predictions"].head(5)],
                           "our_mae_vs_example_test": round(float(np.abs(merged["predictions"] - merged["target"]).mean()), 4),
                           "published_reference": None, "note": "no per-dataset Chronos-2 table is published in the repository; nothing to compare against"}, indent=1))
print(OUT.read_text())
