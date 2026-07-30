from __future__ import annotations

import numpy as np


def mae(actual, predicted) -> float:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    return float(np.mean(np.abs(a - p)))


def rmse(actual, predicted) -> float:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    return float(np.sqrt(np.mean(np.square(a - p))))


def smape(actual, predicted, epsilon: float = 1e-9) -> float:
    a = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    denominator = np.abs(a) + np.abs(p)
    return float(100.0 * np.mean(2.0 * np.abs(p - a) / np.maximum(denominator, epsilon)))


def geh(predicted, simulated, epsilon: float = 1e-9):
    c = np.asarray(predicted, dtype=float)
    m = np.asarray(simulated, dtype=float)
    return np.sqrt(2.0 * np.square(m - c) / np.maximum(m + c, epsilon))
