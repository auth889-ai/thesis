"""Imputation under the ImputeFormer protocol: 25 % point missing on METR-LA, scored on the masked points only.

    USE_TF=0 python -m core.ml.forecasting.evaluation.imputation --epochs 30

Model: ImputeFormer (Nie et al., KDD 2024) as shipped in PyPOTS (the authors point to that implementation);
the official configuration for METR-LA (window 24, 3 layers, embeddings 32/96, projection 8, FFN 256, 4 heads,
dropout 0.1, batch 32, L1 loss, lr 1e-3) is used as published; only the training BUDGET is a parameter here
(the paper trains 300 epochs x 300 batches), and the record states the budget that produced each number.
Baselines: per-road train mean, linear interpolation in time inside the window, last observation carried.
Split: chronological 70 / 10 / 20 on non-overlapping 24-step windows; masking seeded; outages (0.0) are NaN and
are never scored. Published (paper Table 2, point missing): ImputeFormer 1.80, SPIN 1.93, GRIN 1.91, mean 7.52.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone

import numpy as np

os.environ.setdefault("USE_TF", "0")                    # a broken tensorflow in the environment must not take transformers down

from core.ml.forecasting.evaluation.evaluate_models import OUT, load

WINDOW = 24
MISSING = 0.25
PUBLISHED = {"ImputeFormer": 1.80, "SPIN": 1.93, "GRIN": 1.91, "mean": 7.52}
CFG = dict(n_steps=WINDOW, n_features=207, n_layers=3, d_input_embed=32, d_learnable_embed=96, d_proj=8, d_ffn=256,
           n_temporal_heads=4, dropout=0.1, batch_size=32)


def windows(dataset: str = "METR-LA"):
    data = load(dataset).astype("float32")
    data[data <= 0] = np.nan                            # outages stay unknown
    n = data.shape[0] // WINDOW
    w = data[: n * WINDOW].reshape(n, WINDOW, data.shape[1])
    a, b = int(n * 0.7), int(n * 0.8)
    return w[:a], w[a:b], w[b:]


def mask_points(w: np.ndarray, seed: int, rate: float = MISSING) -> tuple[np.ndarray, np.ndarray]:
    """Hide `rate` of the OBSERVED points; returns (input with NaN at hidden points, boolean mask of hidden points)."""
    rng = np.random.default_rng(seed)
    hidden = np.isfinite(w) & (rng.random(w.shape) < rate)
    x = w.copy(); x[hidden] = np.nan
    return x, hidden


def score(imputed: np.ndarray, truth: np.ndarray, hidden: np.ndarray) -> dict:
    e = np.abs(imputed[hidden] - truth[hidden])
    e = e[np.isfinite(e)]
    mape = np.abs((imputed[hidden] - truth[hidden]) / truth[hidden]); mape = mape[np.isfinite(mape)]
    return {"mae": round(float(e.mean()), 4), "mape_pct": round(float(mape.mean() * 100), 3), "points": int(hidden.sum())}


def baseline_mean(train: np.ndarray, x: np.ndarray) -> np.ndarray:
    m = np.nanmean(train.reshape(-1, train.shape[-1]), axis=0)
    out = x.copy(); idx = np.where(np.isnan(out)); out[idx] = m[idx[2]]
    return out


def baseline_linear(x: np.ndarray) -> np.ndarray:
    out = x.copy()
    t = np.arange(x.shape[1])
    for i in range(x.shape[0]):
        for j in range(x.shape[2]):
            col = out[i, :, j]; ok = np.isfinite(col)
            if ok.sum() >= 2:
                col[~ok] = np.interp(t[~ok], t[ok], col[ok])
            elif ok.sum() == 1:
                col[~ok] = col[ok][0]
    return out


def baseline_last(x: np.ndarray) -> np.ndarray:
    out = x.copy()
    for t in range(1, out.shape[1]):
        out[:, t] = np.where(np.isfinite(out[:, t]), out[:, t], out[:, t - 1])
    for t in range(out.shape[1] - 2, -1, -1):
        out[:, t] = np.where(np.isfinite(out[:, t]), out[:, t], out[:, t + 1])
    return out


def run_imputeformer(train: np.ndarray, val_x: np.ndarray, val_truth: np.ndarray, test_x: np.ndarray, epochs: int, seed: int) -> tuple[np.ndarray, dict]:
    """Fit on z-scored data (the official config sets `scale_target: true`); predictions come back in mph."""
    import torch
    from pypots.imputation import ImputeFormer
    torch.manual_seed(seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    mu, sd = float(np.nanmean(train)), float(np.nanstd(train))
    z = lambda a: (a - mu) / sd
    model = ImputeFormer(**CFG, epochs=epochs, patience=max(1, min(epochs - 1, epochs // 5)) if epochs > 1 else None, device=device, verbose=False)
    t0 = time.time()
    model.fit({"X": z(train)}, {"X": z(val_x), "X_ori": z(val_truth)})      # validation scores the hidden points against the truth
    fit_s = round(time.time() - t0, 1)
    pred = model.predict({"X": z(test_x)})["imputation"] * sd + mu
    return pred, {"device": device, "fit_seconds": fit_s, "epochs": epochs, "config": CFG, "scaling": "z-score on the train split"}


def run(epochs: int, seed: int = 42, dataset: str = "METR-LA") -> dict:
    train, val, test = windows(dataset)
    val_x, _ = mask_points(val, seed + 1)
    test_x, hidden = mask_points(test, seed)
    results = {"mean": score(baseline_mean(train, test_x), test, hidden),
               "linear": score(baseline_linear(test_x), test, hidden),
               "last": score(baseline_last(test_x), test, hidden)}
    pred, info = run_imputeformer(train, val_x, val, test_x, epochs, seed)
    results["ImputeFormer"] = {**score(pred, test, hidden), **info}
    return {"dataset": dataset, "generated_utc": datetime.now(timezone.utc).isoformat(),
            "protocol": {"window": WINDOW, "missing": f"point, {MISSING:.0%} of observed points, seed {seed}", "split": "chronological 70/10/20 on non-overlapping windows",
                         "scored_on": "hidden points only; outages never scored", "budget": f"{epochs} epochs on the laptop (paper: 300 x 300 batches)",
                         "windows": {"train": int(len(train)), "val": int(len(val)), "test": int(len(test))}},
            "published_point_missing_mae": PUBLISHED, "results": results}


def write(rec: dict) -> None:
    (OUT / "imputation.json").write_text(json.dumps(rec, indent=1))
    L = [f"# Imputation on {rec['dataset']}: {rec['protocol']['missing']}\n", f"{rec['protocol']['split']}; {rec['protocol']['scored_on']}; budget: {rec['protocol']['budget']}.\n",
         "| method | MAE on hidden points | MAPE % | published MAE (paper, point missing) |", "|---|---|---|---|"]
    for k, v in rec["results"].items():
        L.append(f"| {k} | {v['mae']} | {v['mape_pct']} | {rec['published_point_missing_mae'].get(k, '–')} |")
    (OUT / "imputation.md").write_text("\n".join(L) + "\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    rec = run(a.epochs, a.seed)
    for k, v in rec["results"].items():
        print(f"{k:<14} MAE {v['mae']}  MAPE {v['mape_pct']} %")
    write(rec)
    print(f"wrote {OUT / 'imputation.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
