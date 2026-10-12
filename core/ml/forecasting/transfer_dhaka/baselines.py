"""The weekday-aware historical average (RQ1 step 1): for each road, the mean speed at the same time of day on the same weekday,
from the TRAIN split only, outages (0.0) left out. The time-of-day-only average and persistence stay as Protocol B has them.
Timestamps come from each release's own h5 index (METR-LA from 2012-03-01, PEMS-BAY from 2017-01-01), never typed in."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.common.paths import REPO

H5 = {"METR-LA": REPO / "data/forecasting/cities/METR-LA/METR-LA.h5", "PEMS-BAY": REPO / "data/forecasting/cities/PEMS-BAY/PEMS-BAY.h5"}
SLOTS = 288                                                           # 5-minute slots per day


def timestamps(dataset: str) -> pd.DatetimeIndex:
    return pd.read_hdf(H5[dataset]).index


def weekday_table(train: np.ndarray, ts: pd.DatetimeIndex) -> np.ndarray:
    """(7, 288, N) mean of observed (non-zero) values per weekday and slot; NaN where a cell never had a reading."""
    wd, slot = ts.dayofweek.values, (ts.hour.values * 60 + ts.minute.values) // 5
    total, count = np.zeros((7, SLOTS, train.shape[1])), np.zeros((7, SLOTS, train.shape[1]))
    obs = train > 0
    np.add.at(total, (wd, slot), np.where(obs, train, 0.0))
    np.add.at(count, (wd, slot), obs)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(count > 0, total / count, np.nan)


def predict_weekday(table: np.ndarray, ts: pd.DatetimeIndex, starts: np.ndarray, context: int, steps: int, fallback: np.ndarray) -> np.ndarray:
    """(W, steps, N): for window w, step k, the table at the weekday and slot of time index starts[w] + context + k.
    A cell with no train reading falls back to `fallback` (the time-of-day average), so no value is invented."""
    W, N = len(starts), table.shape[2]
    out = np.zeros((W, steps, N), dtype="float32")
    for i, s in enumerate(starts):
        for k in range(steps):
            t = ts[s + context + k]
            v = table[t.dayofweek, (t.hour * 60 + t.minute) // 5]
            out[i, k] = np.where(np.isnan(v), fallback[i, k], v)
    return out
