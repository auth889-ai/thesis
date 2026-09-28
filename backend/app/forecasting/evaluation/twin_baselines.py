"""P3 forecasting gate — protocol + the two mandatory dumb baselines.

The build plan's forecasting rules, enforced in code:

* Chronological split, never random (leakage-free by construction).
* Horizons 5 / 15 / 30 min — each maps to a real actuation lead time
  (signal ≈ 2–4 min, rerouting 5–15 min, advisory 30 min).
* Metrics: MAE, RMSE always; MAPE only under a validity mask (Dhaka has
  genuine zero-flow intervals, so an unmasked MAPE is undefined, not small).
* Every result names its evidence domain. This module runs on the P2 dataset,
  so results are `DHAKA_SIMULATED_SENSOR_GRAPH` — simulated, never real.

Persistence and Historical Average are not throwaways: they are the floor
every learned model must beat to justify its complexity (strong simple
baselines before fancy methods — standing user rule). BasicTS models plug in
at the gate via the same split indices, hashed here so no candidate can see a
different split.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Mapping

import numpy as np

STEP_S = 300.0
HORIZONS_STEPS = {"5min": 1, "15min": 3, "30min": 6}
EVIDENCE_DOMAIN = "DHAKA_SIMULATED_SENSOR_GRAPH"


@dataclass(frozen=True)
class ChronoSplit:
    """Chronological train/val/test boundaries over T timesteps."""

    n_timesteps: int
    train_end: int
    val_end: int

    @classmethod
    def standard(cls, n_timesteps: int, train: float = 0.7,
                 val: float = 0.1) -> "ChronoSplit":
        if n_timesteps < 20:
            raise ValueError(f"T={n_timesteps} is too short to split")
        return cls(n_timesteps=n_timesteps,
                   train_end=int(n_timesteps * train),
                   val_end=int(n_timesteps * (train + val)))

    def __post_init__(self) -> None:
        if not (0 < self.train_end < self.val_end < self.n_timesteps):
            raise ValueError(
                f"non-chronological split: 0 < {self.train_end} < "
                f"{self.val_end} < {self.n_timesteps} must hold")

    def sha256(self) -> str:
        """Frozen-split hash — identical for every candidate model."""
        return hashlib.sha256(json.dumps(
            [self.n_timesteps, self.train_end, self.val_end]).encode()).hexdigest()


def masked_metrics(pred: np.ndarray, target: np.ndarray,
                   valid: np.ndarray) -> dict:
    """MAE / RMSE over valid points; MAPE additionally masked at |y|>eps.

    `valid` marks points where the target is a real measurement (P2 mask ∧
    finite). Metrics over invented values would be fiction.
    """
    if pred.shape != target.shape or valid.shape != target.shape:
        raise ValueError("pred/target/valid shapes must match")
    v = valid & np.isfinite(target) & np.isfinite(pred)
    if not v.any():
        raise ValueError("no valid points to score")
    err = pred[v] - target[v]
    mae = float(np.abs(err).mean())
    rmse = float(np.sqrt(np.square(err).mean()))
    nz = v & (np.abs(target) > 1e-3)
    mape = (float((np.abs(pred[nz] - target[nz]) / np.abs(target[nz])).mean() * 100)
            if nz.any() else None)
    return {"mae": mae, "rmse": rmse,
            "mape_pct": mape,
            "mape_validity_fraction": float(nz.sum() / v.sum()),
            "n_scored": int(v.sum())}


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def persistence_forecast(series: np.ndarray, horizon_steps: int) -> np.ndarray:
    """ŷ[t+h] = y[t] — the no-model floor. Shape (T, N) → (T-h, N) predictions
    aligned to targets series[h:]."""
    if horizon_steps < 1:
        raise ValueError("horizon must be ≥ 1 step")
    return series[:-horizon_steps]


def historical_average_forecast(series: np.ndarray, horizon_steps: int,
                                split: ChronoSplit,
                                period_steps: int = 288) -> np.ndarray:
    """ŷ[t+h] = mean of train-set values at the same time-of-day slot.

    The average is computed on the TRAIN region only — computing it over the
    full series would leak the test set into the baseline.
    """
    t_len, _ = series.shape
    slots = np.arange(t_len) % period_steps
    with np.errstate(invalid="ignore"):
        slot_mean = np.full((period_steps, series.shape[1]), np.nan)
        for s in range(period_steps):
            rows = series[:split.train_end][slots[:split.train_end] == s]
            if rows.size:
                slot_mean[s] = np.nanmean(rows, axis=0)
    # Fallback for slots never seen in train: overall train mean.
    overall = np.nanmean(series[:split.train_end], axis=0)
    missing = np.isnan(slot_mean)
    slot_mean[missing] = np.broadcast_to(overall, slot_mean.shape)[missing]
    target_slots = slots[horizon_steps:]
    return slot_mean[target_slots]


@dataclass
class BaselineReport:
    """One (model, channel) result block across the mandated horizons."""

    model: str
    channel: str
    split_sha256: str
    horizons: Mapping[str, dict] = field(default_factory=dict)
    evidence_domain: str = EVIDENCE_DOMAIN

    def to_dict(self) -> dict:
        return {"model": self.model, "channel": self.channel,
                "evidence_domain": self.evidence_domain,
                "reality_label": "SIMULATED",
                "split_sha256": self.split_sha256,
                "horizons": dict(self.horizons)}


def run_baselines(data: np.ndarray, mask: np.ndarray, channel_idx: int,
                  channel_name: str, period_steps: int = 288) -> list[BaselineReport]:
    """Score Persistence + Historical Average on the TEST region, all horizons."""
    series = data[:, :, channel_idx]
    split = ChronoSplit.standard(series.shape[0])
    reports = []
    for model in ("persistence", "historical_average"):
        rep = BaselineReport(model=model, channel=channel_name,
                             split_sha256=split.sha256())
        for hname, h in HORIZONS_STEPS.items():
            if model == "persistence":
                pred_all = persistence_forecast(series, h)
            else:
                pred_all = historical_average_forecast(series, h, split,
                                                       period_steps)
            target_all = series[h:]
            valid_all = mask[h:]
            # Score on the TEST region only (indices are into the h-shifted arrays).
            lo = max(split.val_end - h, 0)
            rep.horizons[hname] = masked_metrics(
                pred_all[lo:], target_all[lo:], valid_all[lo:])
        reports.append(rep)
    return reports
