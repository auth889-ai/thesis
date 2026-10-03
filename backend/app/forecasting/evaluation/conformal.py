"""Regime-aware conformal intervals on top of every Protocol B model, with MAPIE.

    python -m app.forecasting.evaluation.conformal --dataset METR-LA

The point forecasts are the ones Protocol B persisted (`results/forecasting/protocol_b/*.npz`): the
VALIDATION block calibrates, the TEST block is scored, so coverage is measured on data the calibration
never saw. Two calibrators per model and horizon, both MAPIE `SplitConformalRegressor` with the absolute
conformity score at 90 %:

    global             one quantile for every window, as a paper would report
    regime-aware       one quantile per regime KNOWN AT PREDICTION TIME: the last observed speed of the
                       context is above or below the road's congestion threshold
    predicted-regime   one quantile per regime the MODEL PREDICTS at the horizon (its own point forecast
                       above or below the threshold); also known at prediction time, and the only one of the
                       three that can react to a transition the model itself foresees

Coverage is then reported where it matters: on all windows, in free flow, in congestion, and at the
transition (free flow at prediction time, congested at the horizon), which is where the 2026 regime
paper found 90 % intervals covering about half. The base models are external checkpoints, so the
estimator handed to MAPIE is the identity on the stored prediction; MAPIE still owns the quantile.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin

from app.forecasting.evaluation.evaluate_models import CONTEXT, OUT, load

LEVEL = 0.9
HORIZONS = {15: 3, 30: 6, 60: 12}


class Precomputed(BaseEstimator, RegressorMixin):
    """The 'model' MAPIE sees: its prediction is the stored point forecast passed in as the feature."""
    def fit(self, X, y=None):
        return self
    def predict(self, X):
        return np.asarray(X)[:, 0]
    def __sklearn_is_fitted__(self):
        return True


def _quantile_model(pred_cal: np.ndarray, y_cal: np.ndarray):
    from mapie.regression import SplitConformalRegressor
    m = SplitConformalRegressor(estimator=Precomputed(), confidence_level=LEVEL, conformity_score="absolute", prefit=True)
    return m.conformalize(pred_cal.reshape(-1, 1), y_cal)


def _interval(m, pred: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _, iv = m.predict_interval(pred.reshape(-1, 1))
    return iv[:, 0, 0], iv[:, 1, 0]


def _block(dataset: str, region: str, windows: int, nodes: int, seed: int):
    z = np.load(OUT / "protocol_b" / f"{dataset}_{region}_w{windows}_n{nodes}_s{seed}.npz")
    data = load(dataset)
    full_n = data.shape[1]
    idx = np.linspace(0, full_n - 1, nodes).astype(int) if nodes and full_n > nodes else np.arange(full_n)
    last = np.stack([data[s + CONTEXT - 1, idx] for s in z["starts"]])          # last observed value, (W, N)
    preds = {k[5:]: z[k] for k in z.files if k.startswith("pred_")}
    return z["truth"], z["threshold"], last, preds


def _regimes(truth_h: np.ndarray, last: np.ndarray, thr: np.ndarray) -> dict[str, np.ndarray]:
    obs = (truth_h > 0) & (last > 0) & np.isfinite(thr)
    free_now, cong_h = last >= thr, truth_h < thr
    return {"all": obs, "free_flow": obs & ~cong_h, "congested": obs & cong_h, "transition": obs & free_now & cong_h}


def run(dataset: str, windows: int = 120, nodes: int = 80, seed: int = 11) -> dict:
    y_cal, thr, last_cal, p_cal = _block(dataset, "val", windows, nodes, seed)
    y_te, _, last_te, p_te = _block(dataset, "test", windows, nodes, seed)
    rows = []
    for name in sorted(set(p_cal) & set(p_te)):
        for h_min, h in HORIZONS.items():
            k = h - 1
            yc, pc, lc = y_cal[:, k], p_cal[name][:, k], last_cal
            yt, pt, lt = y_te[:, k], p_te[name][:, k], last_te
            thr_b = np.broadcast_to(thr, yc.shape)
            cal_ok = (yc > 0) & (lc > 0) & np.isfinite(thr_b)
            # global calibrator
            g = _quantile_model(pc[cal_ok], yc[cal_ok])
            lo_g, hi_g = _interval(g, pt.ravel())
            # regime-aware: one calibrator per prediction-time regime
            lo_r, hi_r = np.full(pt.size, np.nan), np.full(pt.size, np.nan)
            now_cong_cal, now_cong_te = (lc < thr_b), (lt < np.broadcast_to(thr, yt.shape))
            for cong in (False, True):
                sel = cal_ok & (now_cong_cal == cong)
                if sel.sum() < 20:
                    continue
                m = _quantile_model(pc[sel], yc[sel])
                tsel = (now_cong_te == cong).ravel()
                lo_r[tsel], hi_r[tsel] = _interval(m, pt.ravel()[tsel])
            # predicted-regime: the model's own forecast at the horizon decides which quantile applies
            lo_p, hi_p = np.full(pt.size, np.nan), np.full(pt.size, np.nan)
            pred_cong_cal, pred_cong_te = (pc < thr_b), (pt < np.broadcast_to(thr, yt.shape))
            for cong in (False, True):
                sel = cal_ok & (pred_cong_cal == cong)
                if sel.sum() < 20:
                    continue
                m = _quantile_model(pc[sel], yc[sel])
                tsel = (pred_cong_te == cong).ravel()
                lo_p[tsel], hi_p[tsel] = _interval(m, pt.ravel()[tsel])
            reg = _regimes(yt, lt, np.broadcast_to(thr, yt.shape))
            # the calibrated half-widths themselves (absolute score: interval = prediction +/- q), so the departure
            # advice can reuse exactly the quantile that produced the coverage numbers above
            def _q(hi, sel):
                i = np.flatnonzero(sel & np.isfinite(hi))
                return round(float(hi[i[0]] - pt.ravel()[i[0]]), 3) if len(i) else None
            quantiles = {"global": round(float(hi_g[0] - pt.ravel()[0]), 3),
                         "regime_aware": {"free": _q(hi_r, ~now_cong_te.ravel()), "congested": _q(hi_r, now_cong_te.ravel())},
                         "predicted_regime": {"free": _q(hi_p, ~pred_cong_te.ravel()), "congested": _q(hi_p, pred_cong_te.ravel())}}
            row = {"model": name, "horizon_min": h_min, "level": LEVEL, "quantiles": quantiles}
            for label, (lo, hi) in {"global": (lo_g, hi_g), "regime_aware": (lo_r, hi_r), "predicted_regime": (lo_p, hi_p)}.items():
                lo2, hi2 = lo.reshape(yt.shape), hi.reshape(yt.shape)
                for rname, mask in reg.items():
                    m2 = mask & np.isfinite(lo2)
                    row[f"{label}_coverage_{rname}"] = round(float(((yt >= lo2) & (yt <= hi2))[m2].mean()), 4) if m2.any() else None
                    row[f"{label}_width_{rname}"] = round(float((hi2 - lo2)[m2].mean()), 3) if m2.any() else None
                    row[f"n_{rname}"] = int(mask.sum())
            rows.append(row)
    return {"dataset": dataset, "generated_utc": datetime.now(timezone.utc).isoformat(), "level": LEVEL,
            "protocol": {"calibration": "validation block", "scored": "test block", "windows": windows, "nodes": nodes, "seed": seed,
                         "regime_at_prediction_time": "last observed context value vs the road's congestion threshold",
                         "transition": "free flow at prediction time, congested at the horizon",
                         "method": "MAPIE SplitConformalRegressor, absolute conformity score, prefit identity estimator"},
            "rows": rows}


def write(rec: dict) -> None:
    path = OUT / "conformal.json"
    prior = json.loads(path.read_text()) if path.exists() else []
    by = {r["dataset"]: r for r in prior}
    by[rec["dataset"]] = rec
    allr = sorted(by.values(), key=lambda r: r["dataset"])
    path.write_text(json.dumps(allr, indent=1))
    L = ["# Conformal intervals per regime — calibrated on the validation block, scored on the test block\n",
         f"Level {LEVEL:.0%}. `global` is one quantile for all windows; `regime_aware` is one per regime known at prediction time. "
         "Coverage is reported on all test windows, in free flow, in congestion, and at the transition into congestion.\n"]
    for r in allr:
        L += [f"\n## {r['dataset']}\n", "Each cell: global → regime-aware → predicted-regime.\n",
              "| model | h | cov all | cov free | cov congested | cov transition | width all | n transition |", "|---|---|---|---|---|---|---|---|"]
        for w in r["rows"]:
            c = lambda k: " → ".join(str(w.get(f"{l}_coverage_{k}")) for l in ("global", "regime_aware", "predicted_regime"))
            wd = " → ".join(str(w.get(f"{l}_width_all")) for l in ("global", "regime_aware", "predicted_regime"))
            L.append(f"| {w['model']} | {w['horizon_min']} | {c('all')} | {c('free_flow')} | {c('congested')} | **{c('transition')}** | {wd} | {w.get('n_transition')} |")
    L.append("\nRegenerate: `python -m app.forecasting.evaluation.conformal --dataset <name>` after Protocol B has run with `--region val` and `--region test`.\n")
    (OUT / "conformal.md").write_text("\n".join(L))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="METR-LA")
    p.add_argument("--windows", type=int, default=120)
    p.add_argument("--nodes", type=int, default=80)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    rec = run(a.dataset, a.windows, a.nodes, a.seed)
    for w in rec["rows"]:
        print(f"{w['model']:<20} {w['horizon_min']:>3} min  transition coverage {w.get('global_coverage_transition')} → "
              f"{w.get('regime_aware_coverage_transition')} → {w.get('predicted_regime_coverage_transition')}   congested {w.get('global_coverage_congested')} → "
              f"{w.get('regime_aware_coverage_congested')} → {w.get('predicted_regime_coverage_congested')}")
    write(rec)
    print(f"wrote {OUT / 'conformal.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
