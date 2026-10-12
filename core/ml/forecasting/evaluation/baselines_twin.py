#!/usr/bin/env python3
"""Floors for the Dhaka twin dataset: persistence + historical average at 5/15/30/60 min.

    python -m core.ml.forecasting.evaluation.baselines_twin                       # data/forecasting/dhaka_twin
    python -m core.ml.forecasting.evaluation.baselines_twin --data data/forecasting/dhaka_twin_smoke --out results/forecasting/twin_floors_smoke

Reuses research/forecasting/baselines.py (persistence_forecast, historical_average_forecast,
masked_metrics, ChronoSplit) unchanged. Protocol:

* chronological 70/10/20 split over the concatenated seeds (same ChronoSplit -> same sha256
  every BasicTS model on this dataset uses);
* scores on the TEST region only, on the target channel (speed_ms by default), over the
  validity mask (speed NaN = no vehicle sampled -> not scored);
* a (t, t+h) pair that straddles a seed boundary is not scored (seeds are independent replays);
* historical average uses period_steps = bins_per_seed (slot = same bin of the window in an
  earlier seed/"day"), averaged on the TRAIN region only.

Writes results/forecasting/twin_floors.json + twin_floors.md. Evidence domain:
DHAKA_SIMULATED_SENSOR_GRAPH (simulated, never a real measurement).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.common.paths import REPO
sys.path.insert(0, str(REPO))

import numpy as np

from core.ml.forecasting.evaluation.twin_baselines import (EVIDENCE_DOMAIN, STEP_S, ChronoSplit,
                                            historical_average_forecast,
                                            masked_metrics, persistence_forecast)

HORIZONS_MIN = (5, 15, 30, 60)


def score(data: np.ndarray, mask: np.ndarray, seed_index: np.ndarray, channel: int,
          period_steps: int) -> dict:
    series = data[:, :, channel].astype(np.float64)
    t_len = series.shape[0]
    split = ChronoSplit.standard(t_len)
    out = {"split": {"train_end": split.train_end, "val_end": split.val_end,
                     "n_timesteps": t_len, "sha256": split.sha256()},
           "models": {}}
    for model in ("persistence", "historical_average"):
        res = {}
        for hmin in HORIZONS_MIN:
            h = int(hmin * 60 / STEP_S)
            if h >= t_len - split.val_end:
                res[f"{hmin}min"] = None
                continue
            pred = (persistence_forecast(series, h) if model == "persistence"
                    else historical_average_forecast(series, h, split, period_steps))
            target = series[h:]
            valid = mask[h:] & (seed_index[h:] == seed_index[:-h])[:, None]   # no cross-seed pairs
            lo = max(split.val_end - h, 0)                             # test region only
            res[f"{hmin}min"] = masked_metrics(pred[lo:], target[lo:], valid[lo:])
        out["models"][model] = res
    return out


def md_table(rep: dict, channel_name: str, unit: str) -> str:
    lines = [f"| model | " + " | ".join(f"MAE@{h} | RMSE@{h}" for h in HORIZONS_MIN) + " |",
             "|---|" + "---|" * (2 * len(HORIZONS_MIN))]
    for model, res in rep["models"].items():
        cells = []
        for h in HORIZONS_MIN:
            r = res.get(f"{h}min")
            cells += ([f"{r['mae']:.3f}", f"{r['rmse']:.3f}"] if r else ["n/a", "n/a"])
        lines.append(f"| {model} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + f"\n\ntarget = {channel_name} ({unit}), test region only, masked"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=REPO / "data/forecasting/dhaka_twin")
    ap.add_argument("--out", type=Path, default=REPO / "results/forecasting/twin_floors",
                    help="output stem (.json and .md are appended)")
    ap.add_argument("--channel", default="speed_ms")
    a = ap.parse_args()

    z = np.load(a.data / "data.npz")
    data, mask, seed_index = z["data"], z["mask"], z["seed_index"]
    channels = [str(c) for c in z["channels"]]
    manifest = json.loads((a.data / "MANIFEST.json").read_text())
    if manifest.get("label", manifest.get("evidence_domain")) != EVIDENCE_DOMAIN:
        raise ValueError("dataset is not labelled DHAKA_SIMULATED_SENSOR_GRAPH")
    ch = channels.index(a.channel)
    bins_per_seed = int(manifest["config"]["bins_per_seed"])
    unit = {"speed_ms": "m/s", "flow_veh": "veh/5min", "occupancy_pct": "%"}.get(a.channel, "")

    rep = score(data, mask, seed_index, ch, bins_per_seed)
    rep.update({"evidence_domain": EVIDENCE_DOMAIN, "reality_label": "SIMULATED",
                "dataset": str(a.data.relative_to(REPO)) if a.data.is_relative_to(REPO) else str(a.data),
                "dataset_data_sha256": manifest.get("files_sha256", {}).get("data.npz"),
                "channel": a.channel, "unit": unit, "horizons_min": list(HORIZONS_MIN),
                "period_steps_for_historical_average": bins_per_seed,
                "shape": list(data.shape), "mask_coverage_pct": round(100 * float(mask.mean()), 1),
                "sensors_with_any_valid_bin": int((mask.sum(0) > 0).sum()),
                "sensors_with_ge50pct_valid_bins": int((mask.mean(0) >= 0.5).sum()),
                "scoring": "test region, validity mask, no cross-seed (t, t+h) pairs"})
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(rep, indent=2))
    md = (f"# Dhaka twin floors ({EVIDENCE_DOMAIN})\n\ndataset `{rep['dataset']}` shape "
          f"{rep['shape']}, split sha256 `{rep['split']['sha256'][:16]}`, "
          f"mask coverage {rep['mask_coverage_pct']}%\n\n" + md_table(rep, a.channel, unit) + "\n")
    a.out.with_suffix(".md").write_text(md)
    print(md)
    print(f"-> {a.out.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
