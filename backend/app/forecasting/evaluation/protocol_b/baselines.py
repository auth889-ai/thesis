"""The floors every model must beat, and the classical and zero-shot controls."""
from __future__ import annotations

import numpy as np

from .settings import BIN_MIN, HORIZONS_MIN, N_JOBS


def predict_persistence(ctx: np.ndarray, steps: int) -> np.ndarray:
    """Last OBSERVED value per node, held flat.

    Taking ctx[-1] blindly propagates an outage as a predicted speed of zero, which is not what
    persistence means and would understate the baseline every model is measured against.
    """
    obs = np.where(ctx > 0, ctx, np.nan)
    idx = np.where(np.isfinite(obs).any(axis=1, keepdims=True),
                   (np.isfinite(obs) * np.arange(ctx.shape[1])[None, :, None]).max(axis=1, keepdims=True),
                   0)
    last = np.take_along_axis(np.nan_to_num(obs, nan=0.0), idx, axis=1)
    fallback = np.nanmean(np.where(np.isfinite(obs), obs, np.nan))
    last = np.where(last > 0, last, np.nan_to_num(fallback, nan=0.0))
    return np.repeat(last, steps, axis=1)


def build_hist_avg(train: np.ndarray, bins_per_day: int) -> np.ndarray:
    """The literature's historical average: per node, per time-of-day slot, from the TRAIN split.

    A rolling mean of the recent context is a different and much weaker thing — it averages peak
    with off-peak and scores far worse, which would understate the baseline every model has to
    beat. This is the HA that DCRNN and its successors report.
    """
    T, N = train.shape
    table = np.zeros((bins_per_day, N), dtype="float32")
    for b in range(bins_per_day):
        sl = train[b::bins_per_day]
        m = np.where(sl > 0, sl, np.nan)
        with np.errstate(invalid="ignore"):
            col = np.nanmean(m, axis=0)
        table[b] = np.nan_to_num(col, nan=float(np.nanmean(np.where(train > 0, train, np.nan))))
    return table


def predict_hist_avg(starts: np.ndarray, table: np.ndarray, steps: int, context: int, bins_per_day: int) -> np.ndarray:
    """Look the forecast slot up in the time-of-day table."""
    W, N = len(starts), table.shape[1]
    out = np.zeros((W, steps, N), dtype="float32")
    for i, s in enumerate(starts):
        for k in range(steps):
            out[i, k, :] = table[(s + context + k) % bins_per_day]
    return out


def fit_trees(train: np.ndarray, steps: int, lags: int, seed: int, n_fit: int = 20000):
    """One model per horizon, pooled across nodes — the standard tabular framing.

    Fitted under joblib's THREADING backend: the default process backend forks workers that
    deadlock against torch's thread pool once Chronos has been loaded in the same interpreter.
    """
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor
    rng = np.random.default_rng(seed)
    T, N = train.shape
    starts = rng.integers(0, T - lags - steps, size=min(n_fit, max(1, (T - lags - steps) * 2)))
    nodes = rng.integers(0, N, size=len(starts))
    X = np.stack([train[s:s + lags, n] for s, n in zip(starts, nodes)])
    ok = (X > 0).all(axis=1)
    X = X[ok]
    starts, nodes = starts[ok], nodes[ok]
    models = {}
    for h in HORIZONS_MIN:
        k = h // BIN_MIN
        y = np.array([train[s + lags + k - 1, n] for s, n in zip(starts, nodes)])
        good = y > 0
        rf = RandomForestRegressor(n_estimators=60, max_depth=12, random_state=seed, n_jobs=N_JOBS)
        xg = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.08, random_state=seed, n_jobs=N_JOBS, verbosity=0)
        with joblib.parallel_backend("threading", n_jobs=N_JOBS):
            rf.fit(X[good], y[good])
        xg.fit(X[good], y[good])
        models[h] = (rf, xg)
    return models


def predict_trees(trees: dict, ctx: np.ndarray, truth_shape: tuple, lags: int = 12) -> dict[str, np.ndarray]:
    """Lag features carry outages as zeros, which the trees would read as 'stationary'; replace them with the
    road's last observed value in that window."""
    lag = ctx[:, -lags:, :].copy()
    obs = np.where(lag > 0, lag, np.nan)
    for w in range(1, lag.shape[1]):
        obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w - 1, :])
    for w in range(lag.shape[1] - 2, -1, -1):
        obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w + 1, :])
    lag = np.nan_to_num(obs, nan=float(np.nanmean(obs)) if np.isfinite(np.nanmean(obs)) else 0.0)
    flat = lag.transpose(0, 2, 1).reshape(-1, lags)
    W, _, N = truth_shape
    out = {}
    for name, i in (("random_forest", 0), ("xgboost", 1)):
        pred = np.zeros(truth_shape, dtype="float32")
        for h in HORIZONS_MIN:
            pred[:, h // BIN_MIN - 1, :] = trees[h][i].predict(flat).reshape(W, N)
        out[name] = pred
    return out


def predict_chronos(ctx: np.ndarray, steps: int, model_id: str, batch: int = 512) -> np.ndarray:
    """Chronos-Bolt, released weights, one series per road. Outages become NaN and STAY IN PLACE: deleting them
    compresses the time axis (with 8.1 % of METR-LA missing, 12 steps ahead would stop meaning 60 minutes);
    Chronos accepts NaN context natively, which is the correct way to carry a gap."""
    import torch
    from chronos import BaseChronosPipeline
    torch.set_num_threads(N_JOBS)
    pipe = BaseChronosPipeline.from_pretrained(model_id, device_map="cpu", torch_dtype=torch.float32)
    W, C, N = ctx.shape
    flat = ctx.transpose(0, 2, 1).reshape(W * N, C)
    out = np.zeros((W * N, steps), dtype="float32")
    for i in range(0, len(flat), batch):
        chunk = [torch.tensor(np.where(r > 0, r, np.nan)) for r in flat[i:i + batch]]
        q, _ = pipe.predict_quantiles(chunk, prediction_length=steps, quantile_levels=[0.5])
        out[i:i + len(chunk)] = q[:, :, 0].detach().cpu().numpy()
        print(f"\r  chronos {min(i + batch, len(flat))}/{len(flat)} series", end="", flush=True)
    print()
    return out.reshape(W, N, steps).transpose(0, 2, 1)
