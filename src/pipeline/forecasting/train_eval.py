"""EVALUATION for city-specific training — the rules that make a trained model trustworthy.

Splits are CHRONOLOGICAL, 70 / 10 / 20, exactly the harness's own (`TRAIN_VAL_TEST_RATIO`), read
from the prepared `data.dat` so every number here is on the same windows their runner used.
Temporal data is never shuffled.

    validation  -> choose the model / config          (never the test set)
    test        -> reported ONCE for the chosen model, plus the same baselines for context

Baselines evaluated without training, on the same windows:
    persistence          the last reading holds
    historical average   the training split's mean for that node at that slot of the day
    Chronos-Bolt         zero-shot, on an evenly spaced sample of windows (it is slow per window)

Metrics per horizon (3 / 6 / 12 steps): MAE, RMSE, MAPE (only where the target is > 0 — their
masking), congestion F1 where the quantity is a speed (congested = below 60 % of the road's
free-flow speed, free-flow = 95th percentile of its training split), persistence MAE and skill
= 1 − MAE / MAE_persistence.

TRUST GATE (`trust()`): ROUTING_ELIGIBLE only if data quality passed, the checkpoint reloaded and
reproduced its reported test error, a held-out test exists, and the model beats persistence by
at least MARGIN. Otherwise: MODEL TRAINED, BUT NOT BETTER THAN BASELINE — routing falls back to
the reactive arm.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

HORIZONS = (3, 6, 12)
IN_LEN = OUT_LEN = 12
MARGIN = 0.03                                   # skill vs persistence needed for ROUTING_ELIGIBLE
VERIFY_TOL = 0.03                               # reload must reproduce reported MAE within 3 %
CHRONOS_WINDOWS = 24                            # evenly spaced windows per split for the slow zero-shot model
QUALITY = {"min_steps": 240, "max_missing": 0.30, "max_dead_nodes": 0}


# --------------------------------------------------------------------------------- hashing / cache
def sha256_file(p: Path, n: int = 16) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def cache_key(dataset_hash: str, graph_hash: str, arch: str, config_hash: str, upstream_sha: str) -> str:
    return f"{dataset_hash}-{graph_hash}-{arch}-{config_hash}-{upstream_sha[:7]}"


# --------------------------------------------------------------------------------- splits / windows
def splits(T: int) -> dict:
    n_train = int(T * 0.7); n_val = int(T * 0.1)
    return {"train": (0, n_train), "val": (n_train, n_train + n_val), "test": (n_train + n_val, T)}


def windows(lo: int, hi: int) -> np.ndarray:
    """Origins t such that history [t-12, t) and future [t, t+12) both lie inside [lo, hi) —
    the same windows their dataset class forms for that split."""
    return np.arange(lo + IN_LEN, hi - OUT_LEN + 1)


# --------------------------------------------------------------------------------- data quality
def data_quality(vals: np.ndarray, interval_s: int) -> dict:
    T, N = vals.shape
    missing = float(np.isnan(vals).mean())
    dead = int(np.isnan(vals).all(axis=0).sum())
    const = int((np.nanstd(vals, axis=0) == 0).sum())
    reasons = []
    if T < QUALITY["min_steps"]:
        reasons.append(f"only {T} steps; need {QUALITY['min_steps']}")
    if missing > QUALITY["max_missing"]:
        reasons.append(f"{missing:.0%} missing; max {QUALITY['max_missing']:.0%}")
    if dead > QUALITY["max_dead_nodes"]:
        reasons.append(f"{dead} road(s) have no readings at all")
    if const:
        reasons.append(f"{const} road(s) never change")
    return {"passed": not reasons, "reasons": reasons, "steps": T, "roads": N, "missing_fraction": round(missing, 4),
            "dead_roads": dead, "constant_roads": const, "interval_s": interval_s, "days": round(T * interval_s / 86400, 2)}


# --------------------------------------------------------------------------------- metrics
def _masked(pred: np.ndarray, y: np.ndarray):
    m = np.isfinite(y) & (y != 0) & np.isfinite(pred)
    return pred[m], y[m]


def metrics_at(pred: np.ndarray, y: np.ndarray, freeflow: np.ndarray | None = None) -> dict:
    """pred, y: (W, N) for one horizon. freeflow: (N,) per-road free-flow speed for the F1, or None."""
    p, t = _masked(pred, y)
    if len(t) == 0:
        return {"MAE": None, "RMSE": None, "MAPE": None, "F1": None, "n": 0}
    out = {"MAE": float(np.abs(p - t).mean()), "RMSE": float(np.sqrt(((p - t) ** 2).mean())),
           "MAPE": float((np.abs(p - t) / np.abs(t)).mean() * 100), "n": int(len(t)), "F1": None}
    if freeflow is not None:
        thr = 0.6 * freeflow[None, :]
        m = np.isfinite(y) & (y != 0) & np.isfinite(pred)
        cong_t, cong_p = (y < thr) & m, (pred < thr) & m
        tp = int((cong_t & cong_p).sum()); fp = int((~cong_t & cong_p & m).sum()); fn = int((cong_t & ~cong_p & m).sum())
        out["F1"] = float(2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else None
        out["congested_share"] = float(cong_t.sum() / max(1, m.sum()))
    return out


def freeflow_from_train(vals: np.ndarray, train_hi: int) -> np.ndarray:
    v = vals[:train_hi].copy(); v[v == 0] = np.nan
    return np.nanpercentile(v, 95, axis=0)


# --------------------------------------------------------------------------------- baselines
def predict_persistence(vals: np.ndarray, t: np.ndarray) -> np.ndarray:
    """(W, 12, N): the last observed reading before t, carried forward."""
    last = vals[t - 1]                                   # (W, N)
    return np.repeat(last[:, None, :], OUT_LEN, axis=1)


def historical_average(vals: np.ndarray, train_hi: int, steps_per_day: int) -> np.ndarray:
    """(steps_per_day, N): the training split's mean per slot of the day (0 = missing, masked)."""
    v = vals[:train_hi].astype("float64"); v[v == 0] = np.nan
    slots = np.arange(train_hi) % steps_per_day
    ha = np.full((steps_per_day, v.shape[1]), np.nan)
    for s in range(steps_per_day):
        rows = v[slots == s]
        if len(rows):
            with np.errstate(all="ignore"):
                ha[s] = np.nanmean(rows, axis=0)
    glob = np.nanmean(v, axis=0)
    ha = np.where(np.isnan(ha), glob[None, :], ha)
    return ha


def predict_ha(ha: np.ndarray, t: np.ndarray, steps_per_day: int) -> np.ndarray:
    fut = (t[:, None] + np.arange(OUT_LEN)[None, :]) % steps_per_day
    return ha[fut]                                        # (W, 12, N)


def predict_chronos(vals: np.ndarray, t: np.ndarray, interval_s: int, quantity: str, node_ids: list[str],
                    max_windows: int = CHRONOS_WINDOWS) -> tuple[np.ndarray, np.ndarray]:
    """Zero-shot Chronos-Bolt through the project's own adapter, on an evenly spaced sample of the
    windows (returns the sampled origins too). Gaps are carried forward by the adapter."""
    from pipeline.forecasting.adapters.base import CityData
    from pipeline.forecasting.adapters.registry import forecast as run_forecast
    idx = np.linspace(0, len(t) - 1, min(max_windows, len(t)), dtype=int)
    ts = t[idx]
    step_min = interval_s // 60
    hz = [step_min * k for k in range(1, OUT_LEN + 1)]
    out = np.full((len(ts), OUT_LEN, vals.shape[1]), np.nan)
    predict_chronos.last_reason = None
    for i, t0 in enumerate(ts):
        hist = vals[max(0, t0 - 288):t0].astype("float32").copy(); hist[hist == 0] = np.nan
        cd = CityData(city_id="eval", node_ids=node_ids, values=hist, interval_s=interval_s,
                      target=quantity, unit=quantity, reality="USER_UPLOAD")
        r = run_forecast(cd, hz, "Chronos-Bolt")
        f = r.get("forecast")
        if not f:
            predict_chronos.last_reason = str((r.get("decision") or {}).get("reason") or r.get("error") or "no forecast returned")[:200]
            continue
        for k, h in enumerate(hz):
            v = f["values"].get(h) or f["values"].get(str(h))
            if v is not None:
                out[i, k] = [np.nan if x is None else x for x in v]
    return out, ts


def score(pred: np.ndarray, vals: np.ndarray, t: np.ndarray, freeflow: np.ndarray | None) -> dict:
    """pred (W, 12, N) against the truth after each origin: per-horizon metrics + overall."""
    out = {}
    fut = np.stack([vals[t + k] for k in range(OUT_LEN)], axis=1)          # (W, 12, N)
    for h in HORIZONS:
        out[f"horizon_{h}"] = metrics_at(pred[:, h - 1], fut[:, h - 1], freeflow)
    out["overall"] = metrics_at(pred.reshape(-1, pred.shape[-1]), fut.reshape(-1, fut.shape[-1]), None)
    return out


def with_skill(table: dict, persistence: dict) -> dict:
    """Attach persistence MAE and skill to every horizon of a metrics table."""
    for k, m in table.items():
        if not isinstance(m, dict):
            continue
        p = (persistence.get(k) or {}).get("MAE")
        m["persistence_MAE"] = p
        m["skill_vs_persistence"] = (None if not p or m.get("MAE") is None else round(1 - m["MAE"] / p, 4))
    return table


# --------------------------------------------------------------------------------- the trust gate
def trust(selected: str, test_table: dict, quality: dict, verification: dict | None, margin: float = MARGIN) -> dict:
    quality = quality or {}
    ov = (test_table or {}).get("overall") or {}
    skill = ov.get("skill_vs_persistence")
    checks = {"data_quality": bool(quality.get("passed")),
              "checkpoint_reload": bool(verification and verification.get("passed")) if selected not in ("persistence", "historical_average", "Chronos-Bolt") else True,
              "held_out_test": ov.get("MAE") is not None,
              "beats_persistence": skill is not None and skill >= margin}
    eligible = all(checks.values()) and selected not in ("persistence",)
    if eligible:
        label, message = "ROUTING_ELIGIBLE", f"{selected} beats persistence by {skill:.1%} on the untouched test set"
    elif checks["held_out_test"] and not checks["beats_persistence"]:
        label, message = "NOT_BETTER_THAN_BASELINE", "MODEL TRAINED, BUT NOT BETTER THAN BASELINE — routing uses the reactive fallback"
    else:
        failed = [k for k, v in checks.items() if not v]
        label, message = "NOT_ELIGIBLE", "not eligible: " + ", ".join(failed)
    return {"label": label, "eligible": eligible, "message": message, "checks": checks, "margin": margin, "skill": skill}


def to_jsonable(o):
    if isinstance(o, dict):
        return {k: to_jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return None if isinstance(o, np.floating) and not np.isfinite(o) else o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o
