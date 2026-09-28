#!/usr/bin/env python3
"""Live Dhaka congestion stream -> forecastable time series + honest floors.

    python -m app.forecasting.live.live_state                      # build from results/artifacts/live_dhaka
    python -m app.forecasting.live.live_state --report             # + floors table (needs >= --min-bins bins)

Second box of the live chain:

    live APIs -> [traffic-state builder] -> ML forecast -> future edge times -> router -> SUMO test

Input  : results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl
         (written by src/pipeline/forecasting/record_live.py; derived congestion classes only, see its COMPLIANCE note)
Output : data/forecasting/live_dhaka/{series.npz, MANIFEST.json}  and, with --report,
         results/forecasting/live_floors.{json,md}

Encoding: the recorded verdict is ORDINAL, so it is encoded as such and forecast as a level, not a
label — FREE_FLOW 0, SLOW 1, CONGESTED 2, SEVERE 3, UNKNOWN -> gap. A bin with no capture is a gap
(mask=False) and is never imputed silently: gaps are carried in the mask so any model or metric can
exclude them, exactly as METR-LA's zero-masking works.

Floors are arithmetic, not learned (no local training):
  persistence         y(t+h) = y(t)
  historical_average  y(t+h) = mean of the same time-of-day bin in the training region
  global_mean         y(t+h) = training mean            (the do-nothing floor)
A learned model must beat these on the SAME masked test region to be worth reporting.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.paths import REPO
SRC = REPO / "results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl"
OUT_DATA = REPO / "data/forecasting/live_dhaka"
OUT_RES = REPO / "results/forecasting"
LEVELS = {"FREE_FLOW": 0.0, "SLOW": 1.0, "CONGESTED": 2.0, "SEVERE": 3.0}
BIN_S = 300


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("congestion_state") in LEVELS and r.get("corridor_id"):
            rows.append(r)
    return rows


def build(rows: list[dict], bin_s: int = BIN_S):
    """-> (values T x N, mask T x N, corridors, bin_start_epochs). One row per 5-min bin."""
    corridors = sorted({r["corridor_id"] for r in rows})
    idx = {c: i for i, c in enumerate(corridors)}
    ts = [datetime.fromisoformat(r["captured_utc"]).timestamp() for r in rows]
    t0 = (min(ts) // bin_s) * bin_s
    t1 = (max(ts) // bin_s) * bin_s
    n_bins = int((t1 - t0) // bin_s) + 1
    vals = np.full((n_bins, len(corridors)), np.nan)
    for r, t in zip(rows, ts):
        b = int((t - t0) // bin_s)
        vals[b, idx[r["corridor_id"]]] = LEVELS[r["congestion_state"]]   # last capture in the bin wins
    mask = ~np.isnan(vals)
    bins = np.array([t0 + i * bin_s for i in range(n_bins)], dtype=float)
    return vals, mask, corridors, bins


def features(bins: np.ndarray) -> np.ndarray:
    """[time-of-day fraction, day-of-week] per bin, in Asia/Dhaka local time (UTC+6, no DST)."""
    local = bins + 6 * 3600
    tod = (local % 86400) / 86400
    dow = ((local // 86400) + 4) % 7                       # 1970-01-01 was a Thursday
    return np.stack([tod, dow], axis=1)


def floors(vals: np.ndarray, mask: np.ndarray, bins: np.ndarray, horizons: list[int], train_frac=0.7) -> dict:
    """MAE of each arithmetic floor at each horizon (in bins), on the masked test region."""
    T = vals.shape[0]
    split = max(1, int(T * train_frac))
    tod = ((bins + 6 * 3600) % 86400 / BIN_S).astype(int)
    out = {}
    for h in horizons:
        errs = {"persistence": [], "historical_average": [], "global_mean": []}
        tr = vals[:split][mask[:split]]
        gmean = float(np.mean(tr)) if tr.size else 0.0
        ha = {}
        for b in range(split):
            for n in range(vals.shape[1]):
                if mask[b, n]:
                    ha.setdefault((tod[b], n), []).append(vals[b, n])
        for t in range(max(split, h), T - h):
            for n in range(vals.shape[1]):
                if not (mask[t + h, n] and mask[t, n]):
                    continue
                y = vals[t + h, n]
                errs["persistence"].append(abs(y - vals[t, n]))
                key = (tod[t + h], n)
                errs["historical_average"].append(abs(y - (statistics.fmean(ha[key]) if key in ha else gmean)))
                errs["global_mean"].append(abs(y - gmean))
        out[h * BIN_S // 60] = {k: (round(statistics.fmean(v), 4) if v else None) for k, v in errs.items()} | \
                               {"n_pairs": len(errs["persistence"])}
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default=str(SRC))
    p.add_argument("--horizons", default="1,3,6,12", help="lead times in BINS (1=5min, 3=15min, 12=60min)")
    p.add_argument("--report", action="store_true", help="also compute floors (needs enough bins)")
    p.add_argument("--min-bins", type=int, default=24, help="refuse to report floors below this many bins")
    a = p.parse_args()
    src = Path(a.src)
    if not src.exists():
        print(f"[live_state] no live series yet at {src} — start `python -m app.forecasting.live.record_live --live --yes`")
        return 1
    rows = load_rows(src)
    vals, mask, corridors, bins = build(rows)
    T, N = vals.shape
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    np.savez(OUT_DATA / "series.npz", values=vals, mask=mask, bins=bins, features=features(bins),
             corridors=np.array(corridors))
    span_h = (bins[-1] - bins[0]) / 3600 + BIN_S / 3600
    man = {"built_utc": datetime.now(timezone.utc).isoformat(), "source": str(src.relative_to(REPO)),
           "reality": "REAL_LIVE", "provider": "google_routes", "google_data_mode": "RUNTIME_REFERENCE",
           "quantity": "DERIVED_CONGESTION_LEVEL (ordinal 0-3), not a speed and not a Google travel time",
           "rows": len(rows), "bins": int(T), "corridors": corridors, "bin_s": BIN_S,
           "coverage": round(float(mask.mean()), 4), "span_hours": round(float(span_h), 2),
           "first_bin_utc": datetime.fromtimestamp(bins[0], timezone.utc).isoformat(),
           "last_bin_utc": datetime.fromtimestamp(bins[-1], timezone.utc).isoformat(),
           "level_encoding": LEVELS, "gap_policy": "mask=False, never imputed"}
    (OUT_DATA / "MANIFEST.json").write_text(json.dumps(man, indent=1))
    print(f"[live_state] {len(rows)} rows -> {T} bins x {N} corridors, coverage {mask.mean():.0%}, span {span_h:.2f} h")
    print(f"[live_state] wrote {OUT_DATA / 'series.npz'}")
    if not a.report:
        return 0
    if T < a.min_bins:
        print(f"[live_state] only {T} bins (< --min-bins {a.min_bins}); floors would be meaningless. "
              f"Keep the recorder running: {a.min_bins} bins = {a.min_bins * BIN_S / 3600:.1f} h.")
        return 2
    hs = [int(x) for x in a.horizons.split(",")]
    # A constant target makes every predictor look perfect (MAE 0.000). Dhaka is genuinely FREE_FLOW
    # overnight, so this is a property of the WINDOW, not of any model — say so instead of printing
    # a table of zeros that reads like a flawless forecaster.
    obs = vals[mask]
    n_levels = len(np.unique(obs))
    local_h = ((bins + 6 * 3600) % 86400) / 3600
    if n_levels < 2:
        lvl = ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"][int(obs[0])] if obs.size else "?"
        msg = (f"DEGENERATE WINDOW: every observation is {lvl} ({obs.size} readings, "
               f"Dhaka local {local_h.min():.1f}h-{local_h.max():.1f}h). Floors are undefined here — "
               f"a constant series is predicted perfectly by anything. Keep recording through a rush "
               f"hour (Dhaka peaks ~08:00-11:00 and ~17:00-21:00 local) before reporting live floors.")
        print(f"[live_state] {msg}")
        (OUT_RES / "live_floors.md").parent.mkdir(parents=True, exist_ok=True)
        (OUT_RES / "live_floors.md").write_text(
            "# Live Dhaka congestion floors — NOT YET MEANINGFUL\n\n" + msg + "\n\n"
            f"Series so far: {T} bins x {vals.shape[1]} corridors, coverage {mask.mean():.0%}, "
            f"span {span_h:.1f} h.\n")
        (OUT_RES / "live_floors.json").write_text(json.dumps(
            {"status": "DEGENERATE_WINDOW", "distinct_levels": int(n_levels), "reason": msg,
             "manifest": man}, indent=1))
        return 3
    fl = floors(vals, mask, bins, hs)
    OUT_RES.mkdir(parents=True, exist_ok=True)
    (OUT_RES / "live_floors.json").write_text(json.dumps({"manifest": man, "floors": fl}, indent=1))
    # Class balance decides how to read these numbers: if almost everything is FREE_FLOW, a
    # constant predictor already scores well and a small MAE is not evidence of skill.
    names = ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"]
    counts = {names[int(k)]: int(c) for k, c in
              zip(*np.unique(obs, return_counts=True))}
    n_obs = int(obs.size)
    free_pct = 100 * counts.get("FREE_FLOW", 0) / max(n_obs, 1)
    congested = sum(v for k, v in counts.items() if k != "FREE_FLOW")
    lines = ["# Live Dhaka congestion — arithmetic floors (REAL_LIVE, no model)\n",
             f"{len(rows)} captures -> {T} bins x {N} corridors over {span_h:.1f} h, coverage {mask.mean():.0%}; "
             f"target = derived congestion level 0-3 (FREE_FLOW..SEVERE); chronological 70/30 split; gaps masked, never imputed.\n",
             "| horizon | persistence MAE | historical-avg MAE | global-mean MAE | n pairs |", "|---|---|---|---|---|"]
    for m, r in sorted(fl.items()):
        lines.append(f"| {m} min | " + " | ".join(f"{r[k]:.3f}" if r[k] is not None else "–"
                     for k in ("persistence", "historical_average", "global_mean")) + f" | {r['n_pairs']} |")
    names_l = ["FREE_FLOW", "SLOW", "CONGESTED", "SEVERE"]
    uq, cnt = np.unique(obs, return_counts=True)
    counts = {names_l[int(k)]: int(c) for k, c in zip(uq, cnt)}
    n_obs = int(obs.size)
    free_pct = 100 * counts.get("FREE_FLOW", 0) / max(n_obs, 1)
    congested = sum(v for k, v in counts.items() if k != "FREE_FLOW")
    lines += ["", "## How to read these numbers", "",
              f"The target is heavily imbalanced: **{free_pct:.0f} % of the {n_obs} observations are "
              f"FREE_FLOW** ({', '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=lambda t: -t[1]))}). "
              "On a series that is mostly one class a constant predictor already scores a small MAE, so "
              "the absolute values above are NOT evidence of skill on their own -- the comparison between "
              "them is. Persistence beating the historical average at every horizon says short-term "
              "congestion is autocorrelated; both being small says Dhaka was mostly free-flowing here.",
              "",
              f"Only {congested} readings ({100 * congested / max(n_obs, 1):.0f} %) were SLOW or worse, so a "
              "learned model has few congestion events to learn from yet. Recording through more rush "
              "hours is what makes this dataset worth training on."]
    lines += ["", "A learned forecaster must beat these on the same masked test region to be worth reporting.",
              "Regenerate: `python -m app.forecasting.live.live_state --report`."]
    (OUT_RES / "live_floors.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
