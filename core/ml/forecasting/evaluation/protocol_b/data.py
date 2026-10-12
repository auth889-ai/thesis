"""A benchmark as (time, road) speeds, its chronological split, the free-flow rule, and contiguous windows."""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.evaluation.protocol_b.settings import CONTEXT, WORKSPACE

PATHS = {
    "METR-LA": WORKSPACE / "OpenCity/data/METR_LA/METR_LA.npz",
    "PEMS-BAY": WORKSPACE / "OpenCity/data/PEMS_BAY/PEMS_BAY.npz",
    "PEMS07M": WORKSPACE / "OpenCity/data/PEMS07M/PEMS07M.npz",
}


def load(dataset: str) -> np.ndarray:
    """(T, N) of the traffic variable, observed-as-is. 0.0 means sensor outage in these releases."""
    p = PATHS.get(dataset)
    if not p or not p.exists():
        raise SystemExit(f"{dataset} not available at {p}")
    a = np.load(p)["data"]
    return a[:, :, 0] if a.ndim == 3 else a


def splits(T: int) -> tuple[int, int]:
    return int(T * 0.7), int(T * 0.8)          # train end, val end (test is the last 20 %)


def free_flow(train: np.ndarray) -> np.ndarray:
    """Per road, the 85th percentile of its observed TRAIN-split speeds: the free-flow reference."""
    return np.array([np.percentile(train[:, n][train[:, n] > 0], 85)
                     if (train[:, n] > 0).any() else np.nan
                     for n in range(train.shape[1])])


def node_index(full_n: int, max_nodes: int) -> np.ndarray:
    """A deterministic, evenly spaced subset of roads; every road when max_nodes is 0 or large enough."""
    return np.linspace(0, full_n - 1, max_nodes).astype(int) if max_nodes and full_n > max_nodes else np.arange(full_n)


def subsample(data: np.ndarray, max_nodes: int) -> np.ndarray:
    return data[:, node_index(data.shape[1], max_nodes)] if max_nodes and data.shape[1] > max_nodes else data


def windows(data: np.ndarray, n_windows: int, seed: int, steps: int, region: str = "test"):
    """A CONTIGUOUS block of consecutive windows from the test region (or the validation region,
    `region="val"`, which the conformal layer uses for calibration so that test coverage is honest).

    Randomly scattered windows make the error metrics fine but the onset lead time meaningless:
    "an onset between window i-1 and window i" then compares two unrelated points in time, so the
    events counted are artefacts of the sampling. Consecutive starts keep the time axis intact, so
    a congestion onset is a real transition.
    """
    T = data.shape[0]
    tr_end, va_end = splits(T)
    rng = np.random.default_rng(seed)
    lo, hi = (va_end, T - CONTEXT - steps) if region == "test" else (tr_end, va_end - CONTEXT - steps)
    span = min(n_windows, hi - lo)
    first = int(rng.integers(lo, max(lo + 1, hi - span)))
    starts = np.arange(first, first + span)
    ctx = np.stack([data[s:s + CONTEXT] for s in starts])
    truth = np.stack([data[s + CONTEXT:s + CONTEXT + steps] for s in starts])
    return starts, ctx, truth
