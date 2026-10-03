"""One model family's predictions on the protocol's windows, computed in its own process and saved.

torch and the tree libraries cannot share an interpreter here: sklearn/XGBoost leave worker pools that
torch's thread pool deadlocks against, and the run sits at 0 % CPU indefinitely. Two attempts to fix that
in-process both still hung, so the families are isolated at the process boundary, which cannot deadlock.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import baselines
from .data import load, node_index, splits, subsample, windows
from .settings import BIN_MIN, CONTEXT, STEPS

KINDS = ("baselines", "trees", "chronos", "chronos2", "timesfm", "checkpoints")


def stage(kind: str, dataset: str, n_windows: int, seed: int, chronos_model: str,
          max_nodes: int, out_path: Path, region: str = "test") -> None:
    data = subsample(load(dataset), max_nodes)
    starts, ctx, truth = windows(data, n_windows, seed, STEPS, region)
    tr_end, _ = splits(data.shape[0])
    train = data[:tr_end]

    preds: dict[str, np.ndarray] = {}
    if kind == "baselines":
        bpd = 24 * 60 // BIN_MIN
        preds["persistence"] = baselines.predict_persistence(ctx, STEPS)
        preds["historical_average"] = baselines.predict_hist_avg(starts, baselines.build_hist_avg(train, bpd), STEPS, CONTEXT, bpd)
    elif kind == "trees":
        preds.update(baselines.predict_trees(baselines.fit_trees(train, STEPS, lags=12, seed=seed), ctx, truth.shape))
    elif kind == "chronos":
        preds["chronos"] = baselines.predict_chronos(ctx, STEPS, chronos_model)
    elif kind == "chronos2":
        from app.forecasting.evaluation.foundation_stage import predict_chronos2
        preds.update(predict_chronos2(ctx, STEPS))
    elif kind == "timesfm":
        from app.forecasting.evaluation.foundation_stage import predict_timesfm
        preds.update(predict_timesfm(ctx, STEPS))
    elif kind == "checkpoints":
        from app.forecasting.evaluation.checkpoint_stage import predict_checkpoints
        preds.update(predict_checkpoints(dataset, starts, CONTEXT, STEPS, node_index(load(dataset).shape[1], max_nodes), ctx))
    else:
        raise SystemExit(f"unknown stage {kind}")

    np.savez_compressed(out_path, truth=truth, starts=starts, **{f"pred_{k}": v for k, v in preds.items()})
