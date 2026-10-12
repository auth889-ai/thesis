"""What Protocol B measures: error by horizon, error inside congestion, the congestion class, and onset lead."""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.evaluation.protocol_b.settings import BIN_MIN, HORIZONS_MIN


def score(pred: np.ndarray, truth: np.ndarray, thr: np.ndarray) -> dict:
    """pred/truth are (W, H, N). Outages (truth == 0) are excluded everywhere."""
    res = {}
    for h in HORIZONS_MIN:
        k = h // BIN_MIN - 1
        p, y = pred[:, k, :], truth[:, k, :]
        m = y > 0
        if not m.any():
            continue
        e = np.abs(p[m] - y[m])
        tc = (y < thr[None, :]) & m
        pc = (p < thr[None, :]) & m
        tp = int((tc & pc).sum()); fp = int((~tc & pc & m).sum()); fn = int((tc & ~pc & m).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        res[h] = {
            "mae": round(float(e.mean()), 4),
            "rmse": round(float(np.sqrt((e ** 2).mean())), 4),
            "mape_pct": round(float((e / y[m]).mean() * 100), 3),
            "congestion_mae": round(float(np.abs(p - y)[tc].mean()), 4) if tc.any() else None,
            "freeflow_mae": round(float(np.abs(p - y)[m & ~tc].mean()), 4) if (m & ~tc).any() else None,
            "congestion_precision": round(prec, 4),
            "congestion_recall": round(rec, 4),
            "congestion_f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0,
            "n_observed": int(m.sum()), "n_congested": int(tc.sum()),
        }
    return res


def onset_lead(pred: np.ndarray, truth: np.ndarray, thr: np.ndarray) -> dict:
    """How early is a congestion ONSET first flagged, in minutes.

    An onset is a not-congested -> congested transition in the ground truth at horizon 1. For each
    onset we ask which is the largest horizon whose forecast already flagged it.
    """
    y1 = truth[:, 0, :]
    obs = y1 > 0
    cong = (y1 < thr[None, :]) & obs
    leads, events, missed = [], 0, 0
    W, N = y1.shape
    for n in range(N):
        c = cong[:, n]
        for i in range(1, W):
            if c[i] and not c[i - 1]:
                events += 1
                flags = [h for h in HORIZONS_MIN if pred[i, h // BIN_MIN - 1, n] < thr[n]]
                if flags:
                    leads.append(max(flags))
                else:
                    missed += 1
    if not leads:
        return {"events": events, "warned": 0, "missed": missed, "mean_lead_min": None}
    a = np.array(leads)
    return {"events": events, "warned": len(leads), "missed": missed,
            "detection_rate": round(len(leads) / events, 4) if events else None,
            "mean_lead_min": round(float(a.mean()), 2),
            "median_lead_min": float(np.median(a)),
            "max_possible_lead_min": max(HORIZONS_MIN)}
