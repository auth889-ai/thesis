from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "demo_flow_history.csv"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for lag in (1, 2, 3, 24):
        df[f"lag_{lag}"] = df["flow_veh_per_hour"].shift(lag)

    # Cyclic time features let the model understand 23:00 is close to 00:00.
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    return df.dropna().reset_index(drop=True)


def main() -> None:
    df = pd.read_csv(DATA)
    df = add_features(df)

    feature_cols = [
        "hour",
        "is_weekend",
        "lag_1",
        "lag_2",
        "lag_3",
        "lag_24",
        "hour_sin",
        "hour_cos",
    ]
    target = "flow_veh_per_hour"

    # Chronological split: final 48 hours are test data.
    split = len(df) - 48
    train = df.iloc[:split].copy()
    test = df.iloc[split:].copy()

    model = RandomForestRegressor(
        n_estimators=300,
        random_state=42,
        min_samples_leaf=2,
        n_jobs=-1,
    )
    model.fit(train[feature_cols], train[target])
    pred = model.predict(test[feature_cols])

    result = test[["time_index", "day_index", "hour", target]].copy()
    result["predicted_flow"] = np.maximum(1, np.rint(pred)).astype(int)
    result["absolute_error"] = (
        result[target] - result["predicted_flow"]
    ).abs()

    mae = mean_absolute_error(result[target], result["predicted_flow"])
    rmse = mean_squared_error(
        result[target], result["predicted_flow"]
    ) ** 0.5
    r2 = r2_score(result[target], result["predicted_flow"])

    metrics = {
        "model": "RandomForestRegressor",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "MAE": round(float(mae), 4),
        "RMSE": round(float(rmse), 4),
        "R2": round(float(r2), 4),
    }

    result.to_csv(OUT / "predictions.csv", index=False)
    (OUT / "ml_metrics.json").write_text(
        json.dumps(metrics, indent=2)
    )

    plt.figure(figsize=(11, 5))
    plt.plot(result["time_index"], result[target], label="Actual")
    plt.plot(
        result["time_index"],
        result["predicted_flow"],
        label="Predicted",
    )
    plt.xlabel("Hour index")
    plt.ylabel("Vehicles per hour")
    plt.title("Traffic flow: actual vs Random Forest prediction")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT / "actual_vs_predicted.png", dpi=160)
    plt.close()

    print("=== ML EXPERIMENT COMPLETE ===")
    print("Input:", DATA)
    print("Features:", feature_cols)
    print("Target:", target)
    print("Train rows:", len(train))
    print("Test rows:", len(test))
    print("Metrics:", metrics)
    print("\nFirst 8 predictions:")
    print(result.head(8).to_string(index=False))
    print("\nCreated:")
    print(" - outputs/predictions.csv")
    print(" - outputs/ml_metrics.json")
    print(" - outputs/actual_vs_predicted.png")


if __name__ == "__main__":
    main()
