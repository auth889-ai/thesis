"""RQ1 step 5, why Dhaka differs, measured from the data. Each series is one day, 06:00-19:00, 5-minute speeds, outages removed
(not interpolated):
  stop_and_go_share  share of steps whose speed changes by more than 30 % of the series' free-flow from the previous reading
  congested_share    share of readings below 0.6 x free-flow (Protocol B's congestion rule)
  cv                 coefficient of variation (sd / mean)
  acf_<k>            autocorrelation at lag k steps (k = 1, 3, 6, 12: 5 to 60 minutes)
free-flow = the series' own 85th percentile (Protocol B uses the road's train split; a one-day Dhaka site has only its day).
For LA, every weekday sensor-day in the test region of METR-LA and PEMS-BAY; for Dhaka, the three DhaTraX site-days."""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 3, 6, 12)
JUMP = 0.30
CONGESTED = 0.6


def acf(x: np.ndarray, k: int) -> float:
    """Autocorrelation at lag k over pairs where both readings exist (NaN = no reading)."""
    a, b = x[:-k], x[k:]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return float("nan")
    a, b = a[ok], b[ok]
    m = np.nanmean(x)
    den = np.nansum((x - m) ** 2) / np.isfinite(x).sum()
    return float(np.mean((a - m) * (b - m)) / den) if den > 0 else float("nan")


def measures(x: np.ndarray) -> dict:
    x = np.where(x > 0, x, np.nan).astype("float64")
    obs = x[np.isfinite(x)]
    if len(obs) < 24:
        return {}
    ff = np.percentile(obs, 85)
    d = np.abs(np.diff(x))
    dd = d[np.isfinite(d)]
    return {"stop_and_go_share": float((dd > JUMP * ff).mean()) if len(dd) else float("nan"),
            "congested_share": float((obs < CONGESTED * ff).mean()), "cv": float(obs.std() / obs.mean()),
            **{f"acf_{k}": acf(x, k) for k in LAGS}, "readings": int(len(obs))}


def la_sensor_days(values: np.ndarray, ts: pd.DatetimeIndex, start: int) -> list[dict]:
    """Every weekday sensor-day from index `start` on, 06:00-19:00."""
    out = []
    day = ts.normalize()
    keep = (ts.hour >= 6) & (ts.hour < 19) & (ts.dayofweek < 5) & (np.arange(len(ts)) >= start)
    for d in np.unique(day[keep]):
        rows = np.flatnonzero(keep & (day == d))
        for n in range(values.shape[1]):
            m = measures(values[rows, n])
            if m:
                out.append(m)
    return out


def summary(rows: list[dict], seed: int = 11, n_boot: int = 1000) -> dict:
    """Median and a bootstrap 95 % CI of the median for each measure."""
    rng = np.random.default_rng(seed)
    out = {"n": len(rows)}
    for k in rows[0]:
        if k == "readings":
            continue
        v = np.array([r[k] for r in rows], dtype="float64")
        v = v[np.isfinite(v)]
        boots = [np.median(rng.choice(v, len(v))) for _ in range(n_boot)]
        out[k] = {"median": round(float(np.median(v)), 4), "ci95": [round(float(np.percentile(boots, 2.5)), 4), round(float(np.percentile(boots, 97.5)), 4)],
                  "p10": round(float(np.percentile(v, 10)), 4), "p90": round(float(np.percentile(v, 90)), 4)}
    return out
