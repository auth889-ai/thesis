#!/usr/bin/env python3
"""One protocol, every model, on datasets where the future is actually known.

    python -m app.forecasting.evaluation.evaluate_models --dataset METR-LA --windows 300
    python -m app.forecasting.evaluation.evaluate_models --all

Chronos produces real numbers for Dhaka, but a number is not evidence. This is where the models
are made comparable: the SAME test windows, the SAME context length, the SAME horizons, scored
with the SAME metrics, on data whose future exists.

WHO IS COMPARED
    persistence           the last observed value, held flat
    historical_average    per-node mean of the context
    random_forest         classical ML on lagged features, trained on the train split
    xgboost               the same features, gradient boosted
    chronos               Chronos-Bolt, pretrained univariate foundation model, zero-shot
    chronos2, chronos2_mv Chronos-2 zero-shot, per road and with all roads as one multivariate input
    timesfm               TimesFM 2.5 (200M) zero-shot, per road
    GWNet, STID, STAEformer, DCRNN   the trained official checkpoints (checkpoint_stage.py)

WHAT IS MEASURED
    overall MAE / RMSE / masked-MAPE, and then the operational metrics that a routing system
    actually depends on: error DURING congestion, congestion precision/recall/F1, and how early an
    onset is flagged. A model can win on average error and still miss every jam.

PROTOCOL DISCIPLINE
    Congestion is defined per node as a share of that node's own free-flow speed, computed on the
    TRAIN split only — a threshold fitted on test data would leak. Sensor outages, encoded 0.0 in
    these datasets, are excluded from every metric rather than scored as a legal speed of zero.
    The tree models are fitted on the train split and never see test data.

    This harness does NOT compare against OpenCity: OpenCity is scored on a 288-step horizon under
    its authors' split, and mixing that with 5/15/30/60-minute DCRNN-style horizons would be
    exactly the incompatible comparison this project keeps refusing to make.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# Bound the thread pools BEFORE torch or sklearn are imported. Left unbounded, sklearn's joblib
# workers (n_jobs=-1) and torch's intra-op pool deadlock on this machine: the process sits at 0 %
# CPU forever after the Chronos weights load. Diagnosed by finding an idle process an hour in.
import os as _os
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    _os.environ.setdefault(_v, "4")

N_JOBS = 4

from app.paths import REPO
sys.path.insert(0, str(REPO))
OUT = REPO / "results/forecasting"
WORKSPACE = Path.home() / ".dhakaflow/upstream"

HORIZONS_MIN = (5, 15, 30, 60)
BIN_MIN = 5
CONTEXT = 96                # 8 hours; enough for Chronos, cheap for the trees
CONGESTION_RATIO = 0.6      # of the node's own free-flow (85th pct of TRAIN observed)


def load(dataset: str) -> np.ndarray:
    """(T, N) of the traffic variable, observed-as-is. 0.0 means sensor outage in these releases."""
    paths = {
        "METR-LA": WORKSPACE / "OpenCity/data/METR_LA/METR_LA.npz",
        "PEMS-BAY": WORKSPACE / "OpenCity/data/PEMS_BAY/PEMS_BAY.npz",
        "PEMS07M": WORKSPACE / "OpenCity/data/PEMS07M/PEMS07M.npz",
    }
    p = paths.get(dataset)
    if not p or not p.exists():
        raise SystemExit(f"{dataset} not available at {p}")
    a = np.load(p)["data"]
    return a[:, :, 0] if a.ndim == 3 else a


def splits(T: int) -> tuple[int, int]:
    return int(T * 0.7), int(T * 0.8)          # train end, val end (test is the last 20 %)


def free_flow(train: np.ndarray) -> np.ndarray:
    return np.array([np.percentile(train[:, n][train[:, n] > 0], 85)
                     if (train[:, n] > 0).any() else np.nan
                     for n in range(train.shape[1])])


# ------------------------------------------------------------------ predictors
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


def predict_hist_avg(starts: np.ndarray, table: np.ndarray, steps: int,
                     context: int, bins_per_day: int) -> np.ndarray:
    """Look the forecast slot up in the time-of-day table."""
    W, N = len(starts), table.shape[1]
    out = np.zeros((W, steps, N), dtype="float32")
    for i, s in enumerate(starts):
        for k in range(steps):
            out[i, k, :] = table[(s + context + k) % bins_per_day]
    return out


def _tree_features(series: np.ndarray, lags: int) -> np.ndarray:
    """Lagged values + time-of-day index. Deliberately simple: this is the classical-ML control."""
    return series[:, -lags:]


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
        xg = XGBRegressor(n_estimators=200, max_depth=6, learning_rate=0.08,
                          random_state=seed, n_jobs=N_JOBS, verbosity=0)
        with joblib.parallel_backend("threading", n_jobs=N_JOBS):
            rf.fit(X[good], y[good])
        xg.fit(X[good], y[good])
        models[h] = (rf, xg)
    return models


def predict_chronos(ctx: np.ndarray, steps: int, model_id: str, batch: int = 512) -> np.ndarray:
    import torch
    from chronos import BaseChronosPipeline
    torch.set_num_threads(N_JOBS)
    pipe = BaseChronosPipeline.from_pretrained(model_id, device_map="cpu", torch_dtype=torch.float32)
    W, C, N = ctx.shape
    flat = ctx.transpose(0, 2, 1).reshape(W * N, C)
    out = np.zeros((W * N, steps), dtype="float32")
    # Outages become NaN and STAY IN PLACE. Deleting them (as an earlier version did) compresses
    # the time axis: with 8.1 % of METR-LA missing, a 96-step context spans 96 real intervals but
    # only ~88 values, so "12 steps ahead" silently stops meaning 60 minutes. Chronos accepts NaN
    # context natively, which is the correct way to carry a gap.
    for i in range(0, len(flat), batch):
        chunk = [torch.tensor(np.where(r > 0, r, np.nan)) for r in flat[i:i + batch]]
        q, _ = pipe.predict_quantiles(chunk, prediction_length=steps, quantile_levels=[0.5])
        out[i:i + len(chunk)] = q[:, :, 0].detach().cpu().numpy()
        print(f"\r  chronos {min(i + batch, len(flat))}/{len(flat)} series", end="", flush=True)
    print()
    return out.reshape(W, N, steps).transpose(0, 2, 1)


# --------------------------------------------------------------------- scoring
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
                flags = [h for h in HORIZONS_MIN
                         if pred[i, h // BIN_MIN - 1, n] < thr[n]]
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


def _windows(data: np.ndarray, n_windows: int, seed: int, steps: int, region: str = "test"):
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


def stage(kind: str, dataset: str, n_windows: int, seed: int, chronos_model: str,
          max_nodes: int, out_path: Path, region: str = "test") -> None:
    """Compute one model family's predictions and save them. Run as its OWN process.

    torch and the tree libraries cannot share an interpreter here: sklearn/XGBoost leave worker
    pools that torch's thread pool deadlocks against, and the run sits at 0 % CPU indefinitely.
    Two attempts to fix that in-process (bounding threads, then joblib's threading backend) both
    still hung, so the families are isolated at the process boundary, which cannot deadlock.
    """
    data = load(dataset)
    if max_nodes and data.shape[1] > max_nodes:
        data = data[:, np.linspace(0, data.shape[1] - 1, max_nodes).astype(int)]
    steps = max(HORIZONS_MIN) // BIN_MIN
    starts, ctx, truth = _windows(data, n_windows, seed, steps, region)
    tr_end, _ = splits(data.shape[0])
    train = data[:tr_end]

    preds = {}
    if kind == "baselines":
        bpd = 24 * 60 // BIN_MIN
        preds["persistence"] = predict_persistence(ctx, steps)
        preds["historical_average"] = predict_hist_avg(starts, build_hist_avg(train, bpd),
                                                       steps, CONTEXT, bpd)
    elif kind == "trees":
        trees = fit_trees(train, steps, lags=12, seed=seed)
            # Lag features carry outages as zeros, which the trees would read as "stationary".
        # Replace them with the node's last observed value in that window.
        lag = ctx[:, -12:, :].copy()
        obs = np.where(lag > 0, lag, np.nan)
        for w in range(1, lag.shape[1]):
            obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w - 1, :])
        for w in range(lag.shape[1] - 2, -1, -1):
            obs[:, w, :] = np.where(np.isfinite(obs[:, w, :]), obs[:, w, :], obs[:, w + 1, :])
        lag = np.nan_to_num(obs, nan=float(np.nanmean(obs)) if np.isfinite(np.nanmean(obs)) else 0.0)
        flat = lag.transpose(0, 2, 1).reshape(-1, 12)
        N = data.shape[1]
        for name, i in (("random_forest", 0), ("xgboost", 1)):
            out = np.zeros_like(truth)
            for h in HORIZONS_MIN:
                out[:, h // BIN_MIN - 1, :] = trees[h][i].predict(flat).reshape(len(starts), N)
            preds[name] = out
    elif kind == "chronos":
        preds["chronos"] = predict_chronos(ctx, steps, chronos_model)
    elif kind == "chronos2":
        from app.forecasting.evaluation.foundation_stage import predict_chronos2
        preds.update(predict_chronos2(ctx, steps))
    elif kind == "timesfm":
        from app.forecasting.evaluation.foundation_stage import predict_timesfm
        preds.update(predict_timesfm(ctx, steps))
    elif kind == "checkpoints":
        from app.forecasting.evaluation.checkpoint_stage import predict_checkpoints
        full_n = load(dataset).shape[1]
        node_idx = (np.linspace(0, full_n - 1, max_nodes).astype(int) if max_nodes and full_n > max_nodes
                    else np.arange(full_n))
        preds.update(predict_checkpoints(dataset, starts, CONTEXT, steps, node_idx, ctx))
    else:
        raise SystemExit(f"unknown stage {kind}")

    np.savez_compressed(out_path, truth=truth, starts=starts,
                        **{f"pred_{k}": v for k, v in preds.items()})


def evaluate(dataset: str, n_windows: int, seed: int, chronos_model: str,
             skip_chronos: bool = False, max_nodes: int = 0, region: str = "test") -> dict:
    import tempfile
    data = load(dataset)
    if max_nodes and data.shape[1] > max_nodes:
        data = data[:, np.linspace(0, data.shape[1] - 1, max_nodes).astype(int)]
    T, N = data.shape
    tr_end, _ = splits(T)
    thr = CONGESTION_RATIO * free_flow(data[:tr_end])
    steps = max(HORIZONS_MIN) // BIN_MIN

    from app.forecasting.evaluation.checkpoint_stage import checkpoints_for
    kinds = (["baselines", "trees"] + ([] if skip_chronos else ["chronos", "chronos2", "timesfm"])
             + (["checkpoints"] if checkpoints_for(dataset) else []))
    preds, truth, timings = {}, None, {}
    with tempfile.TemporaryDirectory() as td:
        for kind in kinds:
            f = Path(td) / f"{kind}.npz"
            t0 = time.time()
            print(f"  [{kind}] …", flush=True)
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--stage", kind,
                            "--dataset", dataset, "--windows", str(n_windows), "--seed", str(seed),
                            "--chronos-model", chronos_model, "--max-nodes", str(max_nodes),
                            "--region", region, "--stage-out", str(f)], check=True)
            timings[kind] = round(time.time() - t0, 1)
            z = np.load(f)
            truth = z["truth"] if truth is None else truth
            starts = z["starts"]
            for k in z.files:
                if k.startswith("pred_"):
                    preds[k[5:]] = z[k]

    # every prediction is kept: the conformal layer calibrates on the validation block and is scored on
    # the test block, and a reviewer can re-score any model without re-running it
    keep = OUT / "protocol_b"
    keep.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(keep / f"{dataset}_{region}_w{n_windows}_n{N}_s{seed}.npz", truth=truth, starts=starts,
                        threshold=thr, **{f"pred_{k}": v for k, v in preds.items()})
    results = {name: {"horizons": score(p, truth, thr), "onset_lead": onset_lead(p, truth, thr)}
               for name, p in preds.items()}
    return {
        "dataset": dataset, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "windows": int(len(starts)), "context_steps": CONTEXT, "nodes_scored": int(N),
            "horizons_min": list(HORIZONS_MIN), "bin_min": BIN_MIN,
            "split": ("chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows "
                      "from the TEST region, so onset transitions are real"),
            "congestion_threshold": (f"{CONGESTION_RATIO} x per-node free-flow (85th percentile of "
                                     f"that node's TRAIN-split observed values)"),
            "missing": "values of 0.0 are sensor outages and are excluded from every metric",
            "trees_trained_on": "TRAIN split only", "seed": seed, "stage_seconds": timings,
            "isolation": ("each model family runs in its own process: torch and the tree libraries "
                          "deadlock when they share an interpreter"),
            "not_compared_with": ("OpenCity — it is scored on a 288-step horizon under its authors' "
                                  "split; mixing protocols would be meaningless"),
        },
        "nodes": int(N), "timesteps": int(T), "results": results,
    }


def merge(dataset: str, region: str, n_windows: int, max_nodes: int, seed: int, stage_files: list[Path]) -> dict | None:
    """Add one or more staged prediction files to the persisted block and re-score every model on it.

    A new model family (a foundation model that took an hour on the laptop's GPU) joins the comparison
    without re-running the families already there; the windows must match exactly or the merge refuses.
    """
    data = load(dataset)
    N = min(max_nodes, data.shape[1]) if max_nodes else data.shape[1]
    keep = OUT / "protocol_b" / f"{dataset}_{region}_w{n_windows}_n{N}_s{seed}.npz"
    base = dict(np.load(keep))
    for f in stage_files:
        z = np.load(f)
        if not np.array_equal(z["starts"], base["starts"]):
            raise SystemExit(f"{f}: windows differ from the persisted block; re-run the stage with the same seed/windows/nodes")
        base.update({k: z[k] for k in z.files if k.startswith("pred_")})
    np.savez_compressed(keep, **base)
    if region != "test":
        return None
    truth, thr = base["truth"], base["threshold"]
    preds = {k[5:]: v for k, v in base.items() if k.startswith("pred_")}
    path = OUT / "model_comparison.json"
    prior = {r["dataset"]: r for r in json.loads(path.read_text())} if path.exists() else {}
    rec = prior.get(dataset) or {"dataset": dataset, "protocol": {}, "nodes": int(N), "timesteps": int(data.shape[0])}
    rec["results"] = {name: {"horizons": score(p, truth, thr), "onset_lead": onset_lead(p, truth, thr)} for name, p in preds.items()}
    rec["generated_utc"] = datetime.now(timezone.utc).isoformat()
    rec["protocol"]["merged_stages"] = sorted(set(rec["protocol"].get("merged_stages", [])) | {f.name for f in stage_files})
    return rec


def write(records: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "model_comparison.json"
    prior = json.loads(path.read_text()) if path.exists() else []
    by = {r["dataset"]: r for r in prior if isinstance(r, dict)}
    for r in records:
        by[r["dataset"]] = r
    allr = sorted(by.values(), key=lambda r: r["dataset"])
    path.write_text(json.dumps(allr, indent=1))

    L = ["# Model comparison — one protocol, models that can be compared\n",
         "Every model below sees the SAME test windows, the SAME context and the SAME horizons, on "
         "datasets where the future is known. This is what turns a forecast into evidence.\n",
         "OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' "
         "split, and mixing that with 5/15/30/60-minute horizons would be the incompatible "
         "comparison this project keeps refusing to make.\n"]
    for r in allr:
        p = r["protocol"]
        L += [f"\n## {r['dataset']} — {r['nodes']} nodes, {p['windows']} test windows\n",
              f"Context {p['context_steps']} steps; {p['split']}. Congestion: {p['congestion_threshold']}. "
              f"{p['missing']}.\n",
              "| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |",
              "|---|---|---|---|---|---|---|---|---|"]
        for name, res in sorted(r["results"].items()):
            h15 = res["horizons"].get(15, {})
            h60 = res["horizons"].get(60, {})
            ol = res["onset_lead"]
            L.append(f"| {name} | {h15.get('mae','–')} | {h15.get('rmse','–')} | "
                     f"{h15.get('mape_pct','–')} | **{h15.get('congestion_mae','–')}** | "
                     f"{h15.get('congestion_f1','–')} | {h60.get('mae','–')} | "
                     f"{ol.get('detection_rate','–')} | {ol.get('mean_lead_min','–')} min |")
    L.append("\nRegenerate: `python -m app.forecasting.evaluation.evaluate_models --all`. "
             "Machine-readable: `model_comparison.json`.\n")
    (OUT / "model_comparison.md").write_text("\n".join(L))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="METR-LA")
    p.add_argument("--all", action="store_true")
    p.add_argument("--windows", type=int, default=200)
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--chronos-model", default="amazon/chronos-bolt-small")
    p.add_argument("--skip-chronos", action="store_true")
    p.add_argument("--stage", default="", help="internal: run one model family")
    p.add_argument("--stage-out", type=Path, default=None)
    p.add_argument("--max-nodes", type=int, default=0,
                   help="deterministic node subsample; 0 uses every node")
    p.add_argument("--region", default="test", choices=["test", "val"],
                   help="score the test block (the comparison) or the validation block (conformal calibration)")
    p.add_argument("--merge", type=Path, nargs="*", default=None,
                   help="staged prediction files (--stage ... --stage-out) to add to the persisted block, then re-score")
    a = p.parse_args()

    if a.merge:
        rec = merge(a.dataset, a.region, a.windows, a.max_nodes, a.seed, a.merge)
        if rec:
            for name, res in sorted(rec["results"].items()):
                h = res["horizons"].get(15, {})
                print(f"   {name:<20} MAE@15={h.get('mae'):<8} congMAE={h.get('congestion_mae')} onset={res['onset_lead'].get('detection_rate')}")
            write([rec])
        print(f"merged into the {a.region} block of {a.dataset}")
        return 0

    if a.stage:
        stage(a.stage, a.dataset, a.windows, a.seed, a.chronos_model, a.max_nodes, a.stage_out, a.region)
        return 0

    targets = ["METR-LA", "PEMS-BAY", "PEMS07M"] if a.all else [a.dataset]
    out = []
    for ds in targets:
        print(f"[eval] {ds} …", flush=True)
        r = evaluate(ds, a.windows, a.seed, a.chronos_model, a.skip_chronos, a.max_nodes, a.region)
        for name, res in sorted(r["results"].items()):
            h = res["horizons"].get(15, {})
            print(f"   {name:<20} MAE@15={h.get('mae'):<8} congMAE={h.get('congestion_mae')} "
                  f"F1={h.get('congestion_f1')}")
        if a.region == "test":
            out.append(r)
    write(out)
    print(f"\nwrote {(OUT / 'model_comparison.md').relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
