from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import least_squares


def length_weighted_mean(values, lengths):
    values = np.asarray(values, dtype=float)
    lengths = np.asarray(lengths, dtype=float)
    mask = np.isfinite(values) & np.isfinite(lengths) & (lengths > 0)
    if not mask.any():
        return np.nan
    return float(np.sum(values[mask] * lengths[mask]) / np.sum(lengths[mask]))


def raw_states(df, length_col=None, min_detectors=10):
    """Teaching/sanity aggregation. This is NOT labelled as the paper's final MFD."""
    rows = []
    for (day, interval), group in df.groupby(["day", "interval_s"], sort=True):
        if group["detid"].nunique() < min_detectors:
            continue
        if length_col and length_col in group.columns:
            mean_flow = length_weighted_mean(group.flow, group[length_col])
            mean_occ = length_weighted_mean(group.occ, group[length_col])
        else:
            mean_flow = float(group.flow.mean())
            mean_occ = float(group.occ.mean())
        rows.append((day, interval, mean_flow, mean_occ, group.detid.nunique()))
    return pd.DataFrame(
        rows,
        columns=["day", "interval_s", "mean_flow", "mean_occ", "n_detectors"],
    )


def resample_states(df, draws=300, fraction=0.8, seed=2019, length_col=None):
    """Paper-required re-sampling with a fixed seed for reproducibility."""
    detectors = np.array(sorted(df.detid.dropna().astype(str).unique()))
    if len(detectors) < 2:
        raise ValueError("Need at least two detectors for resampling")
    sample_n = min(len(detectors), max(2, int(round(len(detectors) * fraction))))
    rng = np.random.default_rng(seed)
    out = []
    for draw in range(draws):
        chosen = set(rng.choice(detectors, size=sample_n, replace=False).tolist())
        sub = df[df.detid.astype(str).isin(chosen)]
        agg = raw_states(
            sub,
            length_col=length_col,
            min_detectors=max(2, int(sample_n * 0.5)),
        )
        if agg.empty:
            continue
        agg["draw"] = draw
        out.append(agg)
    if not out:
        return pd.DataFrame(
            columns=["day", "interval_s", "mean_flow", "mean_occ", "n_detectors", "draw"]
        )
    return pd.concat(out, ignore_index=True)


def binned_upper_bound(
    states,
    density_col="mean_occ",
    flow_col="mean_flow",
    bins=40,
    quantiles=(0.95, 0.975),
):
    data = pd.DataFrame(
        {
            "x": pd.to_numeric(states[density_col], errors="coerce"),
            "y": pd.to_numeric(states[flow_col], errors="coerce"),
        }
    ).dropna()
    if len(data) < 20:
        raise ValueError("Not enough states for upper-bound extraction")
    edges = np.linspace(data.x.min(), data.x.max(), bins + 1)
    data["bin"] = pd.cut(data.x, edges, include_lowest=True, duplicates="drop")
    rows = []
    for _, group in data.groupby("bin", observed=True):
        if len(group) < 5:
            continue
        rec = {"x": float(group.x.median()), "n": len(group)}
        for quantile in quantiles:
            rec[f"q{int(round(quantile * 1000)):03d}"] = float(group.y.quantile(quantile))
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("x")


def softmin_trapezoid(k, vf, capacity, w, kj, lam):
    """Smooth minimum of free-flow, plateau, and congested branches.

    This is the physically interpretable soft-min/trapezoid family cited by the Loder
    paper. Exact parameterization must be cross-checked against the full functional-form
    paper before any EXACT_REPRODUCTION claim.
    """
    k = np.asarray(k, dtype=float)
    lam = max(float(lam), 1e-6)
    branches = np.vstack(
        [vf * k, np.full_like(k, capacity), w * np.maximum(kj - k, 0)]
    )
    z = -branches / lam
    zmax = np.max(z, axis=0)
    return -lam * (zmax + np.log(np.exp(z - zmax).sum(axis=0)))


def fit_softmin_trapezoid(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y) & (x >= 0) & (y >= 0)
    x, y = x[mask], y[mask]
    if len(x) < 8:
        raise ValueError("Need >=8 upper-bound points for nonlinear fit")
    xmax, ymax = max(x.max(), 1e-6), max(y.max(), 1e-6)
    slopes = y[1:] / np.maximum(x[1:], 1e-6)
    vf0 = float(np.nanmax(slopes)) if len(slopes) else ymax / xmax
    p0 = np.array([max(vf0, 1e-3), ymax, max(ymax / xmax, 1e-3), xmax * 1.25, ymax * 0.03])
    lo = np.array([1e-6, ymax * 0.25, 1e-6, xmax * 1.001, 1e-6])
    hi = np.array([max(vf0 * 10, 1000), ymax * 3, max(ymax / xmax * 20, 1000), xmax * 10, ymax])

    result = least_squares(
        lambda p: softmin_trapezoid(x, *p) - y,
        p0,
        bounds=(lo, hi),
        max_nfev=20000,
    )
    return {
        "vf": float(result.x[0]),
        "capacity": float(result.x[1]),
        "w": float(result.x[2]),
        "kj": float(result.x[3]),
        "lambda": float(result.x[4]),
        "cost": float(result.cost),
        "success": bool(result.success),
        "message": result.message,
    }


def critical_point(params, xmin=0, xmax=None, grid=20000):
    if xmax is None:
        xmax = float(params["kj"])
    x = np.linspace(xmin, xmax, grid)
    y = softmin_trapezoid(
        x,
        params["vf"],
        params["capacity"],
        params["w"],
        params["kj"],
        params["lambda"],
    )
    idx = int(np.nanargmax(y))
    return {
        "critical_density": float(x[idx]),
        "capacity": float(y[idx]),
        "critical_speed": float(y[idx] / x[idx]) if x[idx] > 0 else np.nan,
    }
