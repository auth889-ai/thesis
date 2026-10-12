"""Model Lab: one forecast computed now, for a sensor and a moment of METR-LA chosen by the person, by RQ1's own code.

    PYTHONPATH=.:backend python -m core.ml.forecasting.layer.lab --sensor 0 --at 2012-06-07T14:30 --model D2STGNN

A trained model runs from its checkpoint through checkpoint_stage.predict_checkpoints (the RQ1 path); "no change" is
protocol_b.baselines.predict_persistence. The window ends at the chosen moment (context 96 steps = 8 h) and the forecast covers the
next hour. The answer has the recorded history and future, both forecasts, this window's errors at 15/30/60 min, and, when the
window is one of RQ1's saved test windows, whether the prediction equals RQ1's saved prediction.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from functools import lru_cache

import numpy as np

from core.common.paths import REPO
from core.ml.forecasting.evaluation.protocol_b import baselines
from core.ml.forecasting.evaluation.protocol_b.data import load, splits
from core.ml.forecasting.evaluation.protocol_b.settings import CONTEXT, STEPS

DATASET = "METR-LA"
H5 = REPO / "data/forecasting/cities/METR-LA/METR-LA.h5"
RQ1 = sorted((REPO / "results/forecasting/protocol_b").glob("METR-LA_test_w120_n207_s*.npz"))
SHOW_HISTORY = 24                                       # 2 h of recorded speed before the moment, on the chart
HORIZONS = (15, 30, 60)


@lru_cache(maxsize=1)
def axis() -> tuple[np.ndarray, list[str], list[str]]:
    import pandas as pd
    df = pd.read_hdf(H5)
    return load(DATASET), [t.strftime("%Y-%m-%dT%H:%M") for t in df.index], [str(c) for c in df.columns]


def models() -> list[str]:
    from core.ml.forecasting.evaluation.checkpoint_stage import ARCH, checkpoints_for
    return ["persistence"] + sorted(ARCH[c["arch"]] for c in checkpoints_for(DATASET))


def sensors() -> dict:
    data, times, cols = axis()
    _, va_end = splits(len(times))
    lay = np.load(REPO / "results/forecasting/layer/metr_la_replay.npz")
    return {"dataset": DATASET, "units": "mph", "models": models(), "sensors": [{"index": i, "id": c, "lat": float(lay["lat"][i]), "lon": float(lay["lon"][i])}
                                                                                for i, c in enumerate(cols)],
            "test_from": times[va_end + CONTEXT - 1], "test_to": times[-STEPS - 1], "first": times[CONTEXT - 1]}


def errors(pred: np.ndarray, truth: np.ndarray) -> dict:
    """Absolute error at 15/30/60 min for one window; None where the sensor was out (0 = outage). Pure."""
    out = {}
    for h in HORIZONS:
        k = h // 5 - 1
        out[str(h)] = None if truth[k] <= 0 else round(float(abs(pred[k] - truth[k])), 3)
    return out


def run(sensor: int, at: str, model: str = "D2STGNN") -> dict:
    data, times, cols = axis()
    if model not in models():
        return {"ok": False, "error": f"unknown model {model}; here: {models()}"}
    if not 0 <= sensor < data.shape[1]:
        return {"ok": False, "error": f"sensor index 0..{data.shape[1] - 1}"}
    want = datetime.fromisoformat(at).strftime("%Y-%m-%dT%H:") + f"{datetime.fromisoformat(at).minute // 5 * 5:02d}"
    if want not in times:
        return {"ok": False, "error": f"{at} is outside METR-LA ({times[0]} to {times[-1]})"}
    i = times.index(want)
    start = i - CONTEXT + 1
    if start < 0 or i + STEPS >= len(times):
        return {"ok": False, "error": "the moment needs 8 h of history before it and 1 h after it"}
    _, va_end = splits(len(times))
    ctx = data[start:start + CONTEXT][None]                                     # (1, 96, 207)
    truth = data[i + 1:i + 1 + STEPS, sensor]
    persist = baselines.predict_persistence(ctx, STEPS)[0, :, sensor]
    if model == "persistence":
        pred = persist
    else:
        from core.ml.forecasting.evaluation.checkpoint_stage import predict_checkpoints
        pred = predict_checkpoints(DATASET, np.array([start]), CONTEXT, STEPS, np.arange(data.shape[1]), ctx, only={model})[model][0, :, sensor]
    check = None
    for f in RQ1:
        z = np.load(f)
        hit = np.nonzero(z["starts"] == start)[0]
        key = f"pred_{model}"
        if len(hit) and key in z.files:
            saved = z[key][hit[0], :, sensor]
            check = {"file": f.name, "window": int(hit[0]), "max_abs_diff_mph": float(np.abs(saved - pred).max()),
                     "equal": bool(np.abs(saved - pred).max() <= 1e-3)}
            break
    return {"ok": True, "dataset": DATASET, "units": "mph", "sensor": {"index": sensor, "id": cols[sensor]}, "model": model, "at": times[i],
            "split": "test (never used in training)" if i >= va_end + CONTEXT - 1 else "training or validation part (the model has seen these days)",
            "history": {"times": times[i - SHOW_HISTORY + 1:i + 1], "speed": [round(float(v), 2) for v in data[i - SHOW_HISTORY + 1:i + 1, sensor]]},
            "future": {"times": times[i + 1:i + 1 + STEPS], "recorded": [round(float(v), 2) for v in truth],
                       "forecast": [round(float(v), 2) for v in pred], "no_change": [round(float(v), 2) for v in persist]},
            "errors": {"model": errors(pred, truth), "no_change": errors(persist, truth)}, "rq1_check": check}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sensor", type=int, default=0)
    ap.add_argument("--at", default=None, help="YYYY-MM-DDTHH:MM in METR-LA (default: the first moment of RQ1's seed-11 test windows)")
    ap.add_argument("--model", default="D2STGNN")
    a = ap.parse_args()
    if a.at is None:
        _, times, _ = axis()
        a.at = times[int(np.load(RQ1[0])["starts"][0]) + CONTEXT - 1]
    print(f"LIVE RUN (RQ1 model, Los Angeles METR-LA, RECORDED data): {a.model} forecasts sensor {a.sensor} for the hour after {a.at}, computed now.", flush=True)
    r = run(a.sensor, a.at, a.model)
    if not r["ok"]:
        print("STOP:", r["error"]); return 1
    f = r["future"]
    print(f"  {'':>6}{'recorded':>10}{a.model:>10}{'no change':>11}   ({r['units']}; {r['split']})")
    for k, t in enumerate(f["times"]):
        print(f"  {t[11:]:>6}{f['recorded'][k]:>10}{f['forecast'][k]:>10}{f['no_change'][k]:>11}")
    print("  error at 15 / 30 / 60 min:", " / ".join(str(r["errors"]["model"][str(h)]) for h in HORIZONS),
          f"({a.model}) against", " / ".join(str(r["errors"]["no_change"][str(h)]) for h in HORIZONS), "(no change); one window, not the thesis average")
    c = r["rq1_check"]
    print("  THESIS CHECK: " + (f"this window is RQ1's {c['file']} window {c['window']}: largest difference {c['max_abs_diff_mph']:.2e} mph -> "
                                + ("REPRODUCED." if c["equal"] else "DIFFERENT.") if c else "not one of RQ1's saved windows; the forecast is new."))
    print(json.dumps({k: r[k] for k in ("sensor", "model", "at", "errors", "rq1_check")}))
    return 0 if not c or c["equal"] else 2


if __name__ == "__main__":
    sys.exit(main())
