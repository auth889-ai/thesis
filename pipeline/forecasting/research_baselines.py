"""CLASSICAL / RESEARCH BASELINES on a prepared dataset — XGBoost and Random Forest.

They exist to be compared against, not to be chosen for their names: a gradient-boosted tree and
a random forest fitted on the same chronological training split the deep models use (their
prepared `data.dat`, 70/10/20, never shuffled), with the same masked metrics on the same
validation and test windows (`train_eval`).

Features per (window, road): the 12 readings before the origin, the slot of day and the day of
week at the origin, and the road index. Targets: the 12 readings after it (one model per
horizon step via multi-output). Library cores are the official ones — xgboost.XGBRegressor and
sklearn.ensemble.RandomForestRegressor — nothing re-implemented.

A card is written beside the deep models' cards (results/forecasting/trained/<name>__<arch>.json)
with the fitted estimator saved by joblib, so the registry lists them and the page can run them.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from pipeline.forecasting import basicts_train as bt
from pipeline.forecasting import train_eval as te

ARCHS = ("XGBoost", "RandomForest")
MAX_TRAIN_ROWS = 60_000                                  # sub-sampled evenly when larger, for speed


def _features(raw: np.ndarray, t: np.ndarray, spd: int):
    """(rows, features), (rows, 12) for all (window, road) pairs at origins t."""
    T, N, _ = raw.shape
    y = np.asarray(raw[:, :, 0])
    X, Y, idx = [], [], []
    for i in t:
        hist = y[i - te.IN_LEN:i].T                       # (N, 12)
        fut = y[i:i + te.OUT_LEN].T                       # (N, 12)
        tod = np.full((N, 1), (i % spd) / spd); dow = np.full((N, 1), float(raw[i, 0, 2]) if raw.shape[2] > 2 else 0.0)
        node = np.arange(N)[:, None] / max(1, N - 1)
        X.append(np.hstack([hist, tod, dow, node])); Y.append(fut); idx.append(np.full(N, i))
    return np.vstack(X), np.vstack(Y), np.concatenate(idx)


def _estimator(arch: str):
    if arch == "XGBoost":
        from xgboost import XGBRegressor
        return XGBRegressor(n_estimators=300, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8,
                            tree_method="hist", multi_strategy="multi_output_tree", n_jobs=4, random_state=11)
    from sklearn.ensemble import RandomForestRegressor
    return RandomForestRegressor(n_estimators=150, max_depth=14, min_samples_leaf=4, n_jobs=4, random_state=11)


def fit(dataset_id: str, arch: str, progress=None) -> dict:
    """Prepare (their script), fit on the training split, score val/test, write the card."""
    import joblib
    prep = bt.prepare(dataset_id)
    name = prep["name"]
    raw, _ = bt._prepared(name)
    T, N, _ = raw.shape
    sp = te.splits(T); spd = prep["steps_per_day"]
    t_train = te.windows(*sp["train"])
    if len(t_train) * N > MAX_TRAIN_ROWS:
        t_train = t_train[np.linspace(0, len(t_train) - 1, max(1, MAX_TRAIN_ROWS // N), dtype=int)]
    X, Y, _ = _features(raw, t_train, spd)
    m = (Y != 0).all(axis=1) & (X[:, :te.IN_LEN] != 0).all(axis=1)   # 0 = missing in their files
    if progress:
        progress(stage=f"fitting {arch} on {int(m.sum())} windows")
    t0 = time.time()
    est = _estimator(arch).fit(X[m], Y[m])
    fit_s = time.time() - t0
    out_dir = bt.CARDS / "research"; out_dir.mkdir(parents=True, exist_ok=True)
    ck = out_dir / f"{name}__{arch}.joblib"
    joblib.dump(est, ck)
    card = {"dataset": dataset_id, "bts_name": name, "arch": arch, "arch_class": type(est).__name__, "epochs": None,
            "checkpoint": str(ck), "run_dir": str(out_dir), "trained_utc": datetime.now(timezone.utc).isoformat(), "trained_on": "this CPU",
            "nodes": N, "node_names": prep["node_names"], "interval_s": prep["interval_s"], "quantity": prep["quantity"],
            "steps": T, "first_utc": prep["first_utc"], "dataset_hash": prep["dataset_hash"], "graph_hash": prep["graph_hash"],
            "quality": prep["quality"], "fit_seconds": round(fit_s, 1), "family": "research",
            "cache_key": te.cache_key(prep["dataset_hash"], prep["graph_hash"], arch, "default", "sklearn"),
            "stack": f"{type(est).__module__}.{type(est).__name__} (official library core), features: 12 lags + slot of day + weekday + road",
            "claim": "a classical baseline fitted on this data — for comparison"}
    card["test_metrics"] = {}                            # filled by evaluate() below
    card["persistence_test"] = {}
    ev = evaluate(card)
    card["evaluation"] = ev
    card["test_metrics"] = {k: {"MAE": v["MAE"], "RMSE": v["RMSE"], "MAPE": v["MAPE"]} for k, v in ev["test"][arch].items() if isinstance(v, dict) and "MAE" in v}
    card["best_val_MAE"] = ev["validation"][arch]["overall"]["MAE"]
    card["verification"] = verify(card)
    sel = ev["selected_by_validation"]
    card["trust"] = te.trust(arch, ev["test"][arch], prep["quality"], card["verification"])
    bt.save_card(card)
    return card


def load(card: dict):
    import joblib
    return joblib.load(card["checkpoint"])


def predict(card: dict, as_of: int) -> np.ndarray:
    """(12, N) — the next 12 steps for every road from the 12 before `as_of`."""
    raw, _ = bt._prepared(card["bts_name"])
    spd = int(round(86400 / card["interval_s"]))
    as_of = max(te.IN_LEN, min(raw.shape[0], as_of))
    X, _, _ = _features(raw, np.array([as_of]), spd)
    return load(card).predict(X).T                       # (N, 12) -> (12, N)


def _table(card: dict, est, split: str, ff):
    raw, _ = bt._prepared(card["bts_name"])
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    T, N, _ = raw.shape
    sp = te.splits(T); spd = int(round(86400 / card["interval_s"]))
    t = te.windows(*sp[split])
    X, _, _ = _features(raw, t, spd)
    P = est.predict(X).reshape(len(t), N, te.OUT_LEN).transpose(0, 2, 1)   # (W, 12, N)
    return te.score(P, vals, t, ff)


def evaluate(card: dict) -> dict:
    est = load(card)
    raw, _ = bt._prepared(card["bts_name"])
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    T, N, _ = raw.shape
    sp = te.splits(T); spd = int(round(86400 / card["interval_s"]))
    speed_like = any(k in (card.get("quantity") or "").lower() for k in ("speed", "km/h", "mph"))
    ff = te.freeflow_from_train(vals, sp["train"][1]) if speed_like else None
    ha = te.historical_average(vals, sp["train"][1], spd)
    tables = {}
    for split in ("val", "test"):
        t = te.windows(*sp[split])
        per = te.score(te.predict_persistence(vals, t), vals, t, ff)
        tab = {"persistence": per, "historical_average": te.score(te.predict_ha(ha, t, spd), vals, t, ff), card["arch"]: _table(card, est, split, ff)}
        for tb in tab.values():
            te.with_skill(tb, per)
        tables[split] = tab
    cands = {k: v["overall"]["MAE"] for k, v in tables["val"].items()}
    return te.to_jsonable({"split_rule": "chronological 70/10/20, never shuffled", "validation": tables["val"], "test": tables["test"],
                           "selected_by_validation": min(cands, key=cands.get), "validation_MAE": cands})


def verify(card: dict) -> dict:
    """Reload the saved estimator and reproduce the test MAE it was scored with."""
    ev = card.get("evaluation") or evaluate(card)
    rep = {k: v["MAE"] for k, v in ev["test"][card["arch"]].items() if k.startswith("horizon_")}
    raw, _ = bt._prepared(card["bts_name"])
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    sp = te.splits(raw.shape[0])
    rec = {k: v["MAE"] for k, v in _table(card, load(card), "test", None).items() if k.startswith("horizon_")}
    diffs = {k: abs(rec[k] - rep[k]) / rep[k] for k in rec}
    return {"passed": all(d <= te.VERIFY_TOL for d in diffs.values()), "tolerance": te.VERIFY_TOL, "recomputed_MAE": rec,
            "reported_MAE": rep, "relative_difference": {k: round(d, 4) for k, d in diffs.items()}, "checkpoint": Path(card["checkpoint"]).name}
