"""Which roads are about to tip into congestion at a dataset moment, from the served model's fresh forecast.

A road is 'free now' when its last observed speed is at or above its congestion threshold (0.6 x the road's
free-flow speed, the 85th percentile of its TRAIN-split observations: the same rule Protocol B scores with), and
'onset predicted' at the first horizon whose forecast falls below that threshold. Nothing here is a probability;
it is the model's own forecast against a threshold fixed before any test data was seen.
"""
from __future__ import annotations

import numpy as np

from core.ml.forecasting.evaluation.checkpoint_stage import harness_array
from core.ml.forecasting.evaluation.evaluate_models import CONGESTION_RATIO, free_flow

HORIZONS = {15: 3, 30: 6, 60: 12}
_THR: dict[str, np.ndarray] = {}


def thresholds(dataset: str) -> np.ndarray:
    if dataset not in _THR:
        raw = harness_array(dataset)
        train = np.asarray(raw[: int(raw.shape[0] * 0.7), :, 0], dtype="float64")
        _THR[dataset] = CONGESTION_RATIO * free_flow(train)
    return _THR[dataset]


def flags(now: np.ndarray, pred: np.ndarray, thr: np.ndarray) -> list[dict]:
    """Per road: free now, and the first horizon at which the forecast is below the threshold."""
    out = []
    for i in range(len(now)):
        if not np.isfinite(thr[i]) or now[i] <= 0:
            continue
        free_now = bool(now[i] >= thr[i])
        onset = next((h for h, k in HORIZONS.items() if pred[k - 1, i] < thr[i]), None)
        out.append({"node": f"S{i}", "index": i, "now": round(float(now[i]), 2), "threshold": round(float(thr[i]), 2), "free_now": free_now,
                    "predicted": {str(h): round(float(pred[k - 1, i]), 2) for h, k in HORIZONS.items()},
                    "onset_in_min": onset if free_now else None, "congested_now": not free_now})
    return out


def onsets(dataset: str, as_of: int, model: str | None = None) -> dict:
    from core.ml.forecasting.operations import scientific_prediction as sp
    now, pred, info = sp.forecast(int(as_of), model)
    rows = flags(np.asarray(now, dtype="float64"), np.asarray(pred, dtype="float64"), thresholds("METR-LA" if dataset in {"METR_LA", "METR-LA"} else dataset))
    tipping = sorted((r for r in rows if r["onset_in_min"]), key=lambda r: (r["onset_in_min"], r["predicted"][str(r["onset_in_min"])]))
    return {"dataset": dataset, "as_of": int(as_of), "model": info["resolved_model"], "checkpoint_sha256": info.get("checkpoint_sha256"),
            "rule": f"onset = free now (last observed >= {CONGESTION_RATIO} x free-flow 85th pct of the train split) and forecast below it at the horizon",
            "counts": {"roads": len(rows), "congested_now": sum(r["congested_now"] for r in rows), "onset_predicted": len(tipping)},
            "tipping": tipping, "roads": rows}
