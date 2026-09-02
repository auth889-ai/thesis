#!/usr/bin/env python3
"""Forecasting floors on REAL city data, under the protocol the papers use.

    python pipeline/forecasting/benchmark_floors.py --cities METR-LA,PEMS-BAY
    python pipeline/forecasting/benchmark_floors.py --cities METR-LA --horizons 3,6,12

STAGE 1 of the system, and the part that must exist before any model result can be believed.

A deep model is only worth reporting if it beats the trivial predictors. Every paper in this area
(DCRNN ICLR'18, Graph WaveNet IJCAI'19, STID CIKM'22) reports MAE/RMSE/MAPE at 15/30/60 minutes on
METR-LA and PEMS-BAY under one protocol, and this file reproduces that protocol exactly so our
numbers are comparable to theirs:

  * chronological 70/10/20 train/val/test split (never shuffled — shuffling leaks the future)
  * 12 input steps -> 12 output steps at 5-minute bins; horizons 3/6/12 = 15/30/60 min
  * a missing reading is EXCLUDED from the metrics, never counted as 0 mph. METR-LA encodes
    outages as 0.0, and scoring them as real zeros silently rewards a model for predicting
    "traffic is stopped" during a sensor failure. 8.1 % of METR-LA is affected.
  * MAPE is computed only where the true value is non-zero (the standard convention)

Floors:
  persistence         y(t+h) = y(t)                    the hardest floor at short horizons
  historical_average  mean of the same time-of-day/day-of-week slot in the training region
  seasonal_naive      y(t+h) = y(t+h - 1 week)         captures weekly structure
  global_mean         the training mean                the do-nothing floor

Published reference numbers are printed next to ours so the gap a model must close is explicit.
No GPU and no training: this is arithmetic over real data.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.forecasting.city_datasets import load_city  # noqa: E402

RESULTS = REPO / "results/forecasting"

# Published FLOOR numbers from the dataset papers. Our floors must match these, because the floors
# depend only on the protocol — so agreement is a proof that our split/masking/metrics are theirs.
PUBLISHED_FLOORS = {
    ("METR-LA", "historical_average"): {"mae": 4.16, "rmse": 7.80, "source": "DCRNN, Li et al. ICLR 2018, Table 1 (HA)"},
    ("PEMS-BAY", "historical_average"): {"mae": 2.88, "rmse": 5.59, "source": "DCRNN, Li et al. ICLR 2018, Table 1 (HA)"},
}

# Published MAE at 15/30/60 min — what a trained model is expected to reach on these datasets.
PUBLISHED = {
    ("METR-LA", "DCRNN (Li et al., ICLR 2018)"): (2.77, 3.15, 3.60),
    ("METR-LA", "Graph WaveNet (Wu et al., IJCAI 2019)"): (2.69, 3.07, 3.53),
    ("PEMS-BAY", "DCRNN (Li et al., ICLR 2018)"): (1.38, 1.74, 2.07),
    ("PEMS-BAY", "Graph WaveNet (Wu et al., IJCAI 2019)"): (1.30, 1.63, 1.95),
}


def metrics(pred: np.ndarray, true: np.ndarray, m: np.ndarray) -> dict:
    """MAE / RMSE / MAPE over observed entries only."""
    if not m.any():
        return {"mae": None, "rmse": None, "mape": None, "n": 0}
    e = pred[m] - true[m]
    t = true[m]
    nz = np.abs(t) > 1e-6
    return {"mae": float(np.abs(e).mean()),
            "rmse": float(np.sqrt((e ** 2).mean())),
            "mape": float((np.abs(e[nz] / t[nz])).mean() * 100) if nz.any() else None,
            "n": int(m.sum())}


def floors_for_city(city: str, horizons: list[int], input_len: int = 12,
                    ratios=(0.7, 0.1, 0.2)) -> dict:
    cd = load_city(city)
    v, mask = cd.values, cd.mask
    T, N = v.shape
    n_train = int(T * ratios[0])
    n_val = int(T * ratios[1])
    test_lo = n_train + n_val
    bins_per_day = max(1, 86400 // cd.bin_seconds)
    week = bins_per_day * 7

    # time-of-day x day-of-week slot mean, computed on the TRAIN region only (no leakage)
    slot = (np.arange(T) % bins_per_day) + bins_per_day * ((np.arange(T) // bins_per_day) % 7)
    n_slots = bins_per_day * 7
    ssum = np.zeros((n_slots, N))
    scnt = np.zeros((n_slots, N))
    np.add.at(ssum, slot[:n_train], np.where(mask[:n_train], v[:n_train], 0.0))
    np.add.at(scnt, slot[:n_train], mask[:n_train].astype(float))
    train_obs = v[:n_train][mask[:n_train]]
    gmean = float(train_obs.mean()) if train_obs.size else 0.0
    ha_table = np.where(scnt > 0, ssum / np.maximum(scnt, 1), gmean)

    out = {}
    for h in horizons:
        # every test target index t, predicted from information available at t-h
        t_idx = np.arange(test_lo + input_len, T)
        t_idx = t_idx[t_idx - h >= 0]
        true = v[t_idx]
        m = mask[t_idx] & mask[t_idx - h]                       # both target and source observed
        preds = {"persistence": v[t_idx - h],
                 "historical_average": ha_table[slot[t_idx]],
                 "global_mean": np.full_like(true, gmean)}
        sn_idx = t_idx - week
        ok = sn_idx >= 0
        if ok.any():
            sn = np.where(ok[:, None], v[np.clip(sn_idx, 0, T - 1)], np.nan)
            sn_mask = mask[t_idx] & ok[:, None] & mask[np.clip(sn_idx, 0, T - 1)]
            out.setdefault("_seasonal", {})[h] = metrics(np.nan_to_num(sn), true, sn_mask)
        row = {name: metrics(p, true, m if name != "historical_average" else mask[t_idx])
               for name, p in preds.items()}
        if "_seasonal" in out and h in out["_seasonal"]:
            row["seasonal_naive"] = out["_seasonal"][h]
        out[h] = row
    out.pop("_seasonal", None)
    return {"city": city, "summary": cd.summary(), "bin_seconds": cd.bin_seconds,
            "split": {"train": n_train, "val": n_val, "test": T - test_lo}, "floors": out}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cities", default="METR-LA,PEMS-BAY")
    p.add_argument("--horizons", default="3,6,12", help="in bins; 3,6,12 = 15,30,60 min at 5-min bins")
    a = p.parse_args()
    hs = [int(x) for x in a.horizons.split(",")]
    t0 = time.time()
    recs = {}
    for city in a.cities.split(","):
        try:
            recs[city] = floors_for_city(city, hs)
        except SystemExit as ex:
            print(f"[floors] skipping {city}: {ex}")
            continue
        s = recs[city]["summary"]
        print(f"[floors] {city}: {s['sensors']} sensors, {s['timesteps']} bins, "
              f"{s['coverage']:.1%} observed, {s['reality']}")

    lines = ["# Forecasting floors on real city data\n",
             "The numbers a trained model must beat. Protocol matches the published baselines: chronological "
             "70/10/20 split, 12 input steps, horizons 3/6/12 bins = 15/30/60 min, metrics over OBSERVED "
             "entries only (a missing reading is excluded, never scored as 0 mph).\n"]
    for city, rec in recs.items():
        s = rec["summary"]
        lines += [f"## {city} — {s['sensors']} sensors, {s['span_days']} days, {s['quantity']}, **{s['reality']}**",
                  f"_{s.get('paper', '')}; coverage {s['coverage']:.1%}; "
                  f"split {rec['split']['train']}/{rec['split']['val']}/{rec['split']['test']}_\n",
                  "| predictor | " + " | ".join(f"MAE@{h * rec['bin_seconds'] // 60}min" for h in hs)
                  + " | " + " | ".join(f"RMSE@{h * rec['bin_seconds'] // 60}" for h in hs) + " |",
                  "|---|" + "---|" * (2 * len(hs))]
        names = ["persistence", "historical_average", "seasonal_naive", "global_mean"]
        for name in names:
            if not any(name in rec["floors"][h] for h in hs):
                continue
            mae = " | ".join(f"{rec['floors'][h][name]['mae']:.2f}" if rec["floors"][h].get(name, {}).get("mae") is not None else "–" for h in hs)
            rmse = " | ".join(f"{rec['floors'][h][name]['rmse']:.2f}" if rec["floors"][h].get(name, {}).get("rmse") is not None else "–" for h in hs)
            lines.append(f"| {name} | {mae} | {rmse} |")
        # protocol check: our floor vs the same floor as published
        for (pc, pname), ref in PUBLISHED_FLOORS.items():
            if pc != city:
                continue
            ours = rec["floors"][hs[0]].get(pname, {})
            if ours.get("mae") is None:
                continue
            dm = 100 * abs(ours["mae"] - ref["mae"]) / ref["mae"]
            dr = 100 * abs(ours["rmse"] - ref["rmse"]) / ref["rmse"]
            verdict = "PROTOCOL MATCHES the published evaluation" if dm < 5 and dr < 5 else \
                      "PROTOCOL DIFFERS — investigate split/masking before trusting any model number"
            rec.setdefault("protocol_check", {})[pname] = {
                "ours_mae": round(ours["mae"], 3), "published_mae": ref["mae"], "mae_diff_pct": round(dm, 2),
                "ours_rmse": round(ours["rmse"], 3), "published_rmse": ref["rmse"], "rmse_diff_pct": round(dr, 2),
                "source": ref["source"], "verdict": verdict}
            lines += ["", f"**Protocol check** — our `{pname}` = {ours['mae']:.2f} MAE / {ours['rmse']:.2f} RMSE; "
                          f"published = {ref['mae']} / {ref['rmse']} ({ref['source']}); "
                          f"difference {dm:.1f} % / {dr:.1f} %. {verdict}.",
                      "", "This matters: the floors depend only on the split, the masking and the metric "
                          "definition. Reproducing the published floor is evidence that our evaluation is the "
                          "same one the papers used, so the model numbers that follow are comparable to theirs."]
        pubs = {k[1]: vv for k, vv in PUBLISHED.items() if k[0] == city}
        if pubs:
            lines += ["", "Published trained models on the same dataset (MAE @ 15/30/60 min):", ""]
            for model, vals in pubs.items():
                lines.append(f"* **{model}** — {vals[0]} / {vals[1]} / {vals[2]}")
            best = min(rec["floors"][hs[0]][n]["mae"] for n in names
                       if rec["floors"][hs[0]].get(n, {}).get("mae") is not None)
            tgt = min(v[0] for v in pubs.values())
            lines.append(f"\nSo at 15 min a model must get below **{tgt}** MAE; the best floor here is "
                         f"**{best:.2f}**. That gap is what the deep model has to earn.")
        lines.append("")
    lines += [f"Computed in {time.time() - t0:.1f} s, no GPU, no training — arithmetic over real data.",
              "", "Regenerate: `python pipeline/forecasting/benchmark_floors.py --cities " + a.cities + "`."]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "benchmark_floors.md").write_text("\n".join(lines) + "\n")
    (RESULTS / "benchmark_floors.json").write_text(json.dumps(recs, indent=1, default=str))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
