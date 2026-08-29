from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import duckdb
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, PolynomialFeatures, StandardScaler
from sklearn.svm import LinearSVR
from sklearn.tree import DecisionTreeRegressor

from .metrics import mae, rmse, smape
from .utils import write_json

BASE_NUMERIC = [
    "hour", "weekday", "is_weekend", "month", "day_of_year",
    "length_km", "pos_km", "speed_limit_kmh", "monitored_lanes",
]
OPTIONAL_NUMERIC = ["population", "population_density", "lane_density"]
CATEGORICAL = ["fclass"]
PAPER_RESULTS = {
    "Linear Regression": (72.08, 194.49),
    "Linear SVM": (71.53, 187.16),
    "Polynomial Regression": (69.51, 172.34),
    "Decision Tree": (19.74, 79.85),
    "Random Forest": (17.12, 71.04),
}


def read_table(path: str, max_rows: int | None, seed: int) -> pd.DataFrame:
    con = duckdb.connect()
    cols = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [path]).df()["column_name"].tolist()
    selected = [c for c in BASE_NUMERIC + OPTIONAL_NUMERIC + CATEGORICAL + ["city", "detid", "day", "target_flow"] if c in cols]
    select = ",".join(f'"{c}"' for c in selected)
    if max_rows:
        query = f"SELECT {select} FROM read_parquet(?) USING SAMPLE reservoir({int(max_rows)} ROWS) REPEATABLE({seed})"
    else:
        query = f"SELECT {select} FROM read_parquet(?)"
    return con.execute(query, [path]).df()


def linear_preprocessor(numeric: list[str], categorical: list[str]):
    return ColumnTransformer([
        ("num", Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True)),
        ]), categorical),
    ])


def tree_preprocessor(numeric: list[str], categorical: list[str]):
    return ColumnTransformer([
        ("num", SimpleImputer(strategy="median"), numeric),
        ("cat", Pipeline([
            ("impute", SimpleImputer(strategy="most_frequent")),
            ("ordinal", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)),
        ]), categorical),
    ])


def split(df: pd.DataFrame, seed: int):
    df = df.dropna(subset=["target_flow", "detid", "city"]).reset_index(drop=True)
    numeric = [c for c in BASE_NUMERIC + OPTIONAL_NUMERIC if c in df]
    categorical = [c for c in CATEGORICAL if c in df]
    features = numeric + categorical
    X = df[features]
    y = pd.to_numeric(df["target_flow"], errors="coerce")
    valid = y.notna() & np.isfinite(y) & (y >= 0)
    X, y, df = X.loc[valid].reset_index(drop=True), y.loc[valid].reset_index(drop=True), df.loc[valid].reset_index(drop=True)
    groups = df["city"].astype(str) + "|" + df["detid"].astype(str)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, test_idx = next(splitter.split(X, y, groups=groups))
    return X, y, df, numeric, categorical, train_idx, test_idx


def fit_eval(name: str, pipeline, Xtr, ytr, Xte, yte):
    start = time.time()
    pipeline.fit(Xtr, ytr)
    pred = np.clip(pipeline.predict(Xte), 0, None)
    return pipeline, pred, {
        "model": name,
        "SMAPE_percent": smape(yte, pred),
        "MAE": mae(yte, pred),
        "RMSE": rmse(yte, pred),
        "seconds": time.time() - start,
        "train_rows": len(Xtr),
        "test_rows": len(Xte),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-max-rows", type=int)
    parser.add_argument("--linear-svm-max-rows", type=int)
    parser.add_argument("--polynomial-max-rows", type=int, default=500000)
    parser.add_argument("--random-forest-max-rows", type=int)
    parser.add_argument("--random-forest-trees", type=int, default=200)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    base = read_table(args.data, args.base_max_rows, args.seed)
    X, y, meta, numeric, categorical, tr, te = split(base, args.seed)
    Xtr, Xte, ytr, yte = X.iloc[tr], X.iloc[te], y.iloc[tr], y.iloc[te]
    rows: list[dict] = []
    models: dict[str, object] = {}
    predictions: dict[str, np.ndarray] = {}

    lr = Pipeline([("prep", linear_preprocessor(numeric, categorical)), ("model", LinearRegression())])
    fitted, pred, result = fit_eval("Linear Regression", lr, Xtr, ytr, Xte, yte)
    models[result["model"]], predictions[result["model"]] = fitted, pred
    rows.append(result)

    svm_limit = args.linear_svm_max_rows
    if svm_limit and len(Xtr) > svm_limit:
        rng = np.random.default_rng(args.seed)
        idx = rng.choice(len(Xtr), svm_limit, replace=False)
        svm_X, svm_y = Xtr.iloc[idx], ytr.iloc[idx]
    else:
        svm_X, svm_y = Xtr, ytr
    svm = Pipeline([("prep", linear_preprocessor(numeric, categorical)),
                    ("model", LinearSVR(C=1.0, epsilon=0.1, max_iter=30000, random_state=args.seed))])
    fitted, pred, result = fit_eval("Linear SVM", svm, svm_X, svm_y, Xte, yte)
    models[result["model"]], predictions[result["model"]] = fitted, pred
    rows.append(result)

    poly_numeric = numeric
    poly_limit = args.polynomial_max_rows
    if poly_limit and len(Xtr) > poly_limit:
        rng = np.random.default_rng(args.seed + 1)
        idx = rng.choice(len(Xtr), poly_limit, replace=False)
        poly_X, poly_y = Xtr.iloc[idx][poly_numeric], ytr.iloc[idx]
    else:
        poly_X, poly_y = Xtr[poly_numeric], ytr
    poly = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
        ("poly", PolynomialFeatures(degree=2, include_bias=False)),
        ("model", LinearRegression()),
    ])
    fitted, pred, result = fit_eval("Polynomial Regression", poly, poly_X, poly_y, Xte[poly_numeric], yte)
    models[result["model"]], predictions[result["model"]] = fitted, pred
    rows.append(result)

    tree = Pipeline([("prep", tree_preprocessor(numeric, categorical)),
                     ("model", DecisionTreeRegressor(min_samples_leaf=2, random_state=args.seed))])
    fitted, pred, result = fit_eval("Decision Tree", tree, Xtr, ytr, Xte, yte)
    models[result["model"]], predictions[result["model"]] = fitted, pred
    rows.append(result)

    rf_df = base
    if args.random_forest_max_rows and len(base) > args.random_forest_max_rows:
        rf_df = base.sample(args.random_forest_max_rows, random_state=args.seed)
    rX, ry, rmeta, rnum, rcat, rtr, rte = split(rf_df, args.seed)
    rf = Pipeline([("prep", tree_preprocessor(rnum, rcat)),
                   ("model", RandomForestRegressor(
                       n_estimators=args.random_forest_trees,
                       min_samples_leaf=2,
                       max_features="sqrt",
                       n_jobs=-1,
                       random_state=args.seed,
                   ))])
    fitted, rpred, result = fit_eval("Random Forest", rf, rX.iloc[rtr], ry.iloc[rtr], rX.iloc[rte], ry.iloc[rte])
    models[result["model"]] = fitted
    rows.append(result)

    result_df = pd.DataFrame(rows).sort_values(["SMAPE_percent", "MAE"])
    result_df.to_csv(out / "model_comparison.csv", index=False)
    for name, model in models.items():
        joblib.dump(model, out / (name.lower().replace(" ", "_") + ".joblib"))
    joblib.dump(models["Random Forest"], out / "random_forest_for_berlin.joblib")

    paper_compare = []
    for row in rows:
        ps, pm = PAPER_RESULTS[row["model"]]
        paper_compare.append({
            "model": row["model"], "paper_SMAPE_percent": ps, "paper_MAE": pm,
            "our_SMAPE_percent": row["SMAPE_percent"], "our_MAE": row["MAE"],
            "exact_match_expected": False,
        })
    pd.DataFrame(paper_compare).to_csv(out / "paper_vs_reimplementation.csv", index=False)
    write_json(out / "training_protocol.json", {
        "seed": args.seed,
        "split": "GroupShuffleSplit by city|detector, 80/20",
        "numeric_features": numeric,
        "categorical_features": categorical,
        "base_rows_loaded": len(base),
        "random_forest_rows_loaded": len(rf_df),
        "random_forest_trees": args.random_forest_trees,
        "paper_hyperparameters_available": False,
    })
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()
