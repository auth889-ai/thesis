"""RQ1 step 4, the unseen-city test. Our trained graph models learn one embedding / adjacency entry per METR-LA sensor, so they
cannot run on another network: they are reported "cannot transfer" with that reason. What can move: Protocol B's random forest
and XGBoost (same settings, `protocol_b/baselines.py`), trained on METR-LA's TRAIN split only, on speeds scaled by each window's
own context mean, so the model never sees the target city's data or its units; on the target the forecast is scaled back by that
window's context mean. The same recipe trained on the target's own train split (PEMS-BAY) gives the in-place reference."""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.evaluation.protocol_b.settings import N_JOBS
from core.ml.forecasting.transfer_dhaka.metrics import BIN_MIN, HORIZONS_MIN

LAGS = 12


def _scale(lag: np.ndarray) -> np.ndarray:
    """Per row, the mean of its observed (non-zero) lag values; rows with none get NaN."""
    obs = np.where(lag > 0, lag, np.nan)
    with np.errstate(invalid="ignore"):
        return np.nanmean(obs, axis=1)


def fit(train: np.ndarray, seed: int, n_fit: int = 20000) -> dict:
    """Trees on scaled lags -> scaled target, per horizon. Same sampling and settings as protocol_b.baselines.fit_trees."""
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor
    steps = max(HORIZONS_MIN) // BIN_MIN
    rng = np.random.default_rng(seed)
    T, N = train.shape
    starts = rng.integers(0, T - LAGS - steps, size=min(n_fit, max(1, (T - LAGS - steps) * 2)))
    nodes = rng.integers(0, N, size=len(starts))
    X = np.stack([train[s:s + LAGS, n] for s, n in zip(starts, nodes)])
    ok = (X > 0).all(axis=1)
    X, starts, nodes = X[ok], starts[ok], nodes[ok]
    sc = _scale(X)
    Xs = X / sc[:, None]
    models = {}
    for h in HORIZONS_MIN:
        k = h // BIN_MIN
        y = np.array([train[s + LAGS + k - 1, n] for s, n in zip(starts, nodes)])
        good = y > 0
        rf = RandomForestRegressor(n_estimators=60, max_depth=12, random_state=seed, n_jobs=N_JOBS)
        xg = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.08, random_state=seed, n_jobs=N_JOBS, verbosity=0)
        with joblib.parallel_backend("threading", n_jobs=N_JOBS):
            rf.fit(Xs[good], (y / sc)[good])
        xg.fit(Xs[good], (y / sc)[good])
        models[h] = (rf, xg)
    return models


def predict(models: dict, ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """ctx (W, C, N) in the target's own units -> {random_forest, xgboost}: (W, steps, N); horizons between the scored ones are
    left at 0 (never scored). Outages inside the lag window are filled with the window's last observed value, as Protocol B does."""
    lag = ctx[:, -LAGS:, :].astype("float64").copy()
    obs = np.where(lag > 0, lag, np.nan)
    for w in range(1, LAGS):
        obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w - 1, :])
    for w in range(LAGS - 2, -1, -1):
        obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w + 1, :])
    W, _, N = ctx.shape
    flat = obs.transpose(0, 2, 1).reshape(-1, LAGS)
    sc = _scale(flat)
    good = np.isfinite(sc)
    Xs = np.where(good[:, None], flat / np.where(good, sc, 1.0)[:, None], 1.0)
    out = {}
    for name, i in (("random_forest", 0), ("xgboost", 1)):
        pred = np.zeros((W, steps, N), dtype="float32")
        for h in HORIZONS_MIN:
            p = models[h][i].predict(Xs) * np.where(good, sc, 0.0)
            pred[:, h // BIN_MIN - 1, :] = p.reshape(W, N)
        out[name] = pred
    return out


CANNOT_TRANSFER = {
    m: "cannot transfer: it learns one embedding or adjacency entry per METR-LA sensor (207), so it has no input for another network"
    for m in ("DCRNN", "GWNet", "MegaCRN", "STAEformer", "STID", "D2STGNN")
}
