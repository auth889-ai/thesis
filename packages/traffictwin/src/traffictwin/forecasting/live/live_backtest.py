#!/usr/bin/env python3
"""How accurate is the forecast on THIS city's own recorded data? A rolling-origin backtest.

    python -m traffictwin.forecasting.live.live_backtest                 # every model, 15/30/60 min
    python -m traffictwin.forecasting.live.live_backtest --stride 1      # every bin (slower)

At every origin bin t the recorded series is cut at t, each model forecasts t+15/30/60 min from
that history alone, and the forecast is scored against what the recorder later actually wrote.
This is the only honest way to answer "how accurate is it" for a city with no benchmark: the
model never sees the future it is scored on, and every model is scored on the SAME (origin,
node, horizon) pairs so a model cannot look good by abstaining on the hard ones.

Scores per model per horizon: MAE and RMSE in congestion levels (0-3), the class accuracy after
rounding, and SKILL = 1 - MAE/MAE_persistence, so a model that has not beaten the floor shows a
skill <= 0 rather than an MAE that looks fine on its own.

Output: results/forecasting/live_backtest.json — the table, the number of pairs behind every
cell, and a predicted-vs-actual trace at each horizon for the interface to draw.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

from traffictwin.forecasting.live import live_state                      # noqa: E402
from traffictwin.forecasting.adapters.base import CityData, NotAvailable  # noqa: E402
from traffictwin.forecasting.adapters.baselines import (HistoricalAverageAdapter,  # noqa: E402
                                                     PersistenceAdapter)
from traffictwin.forecasting.adapters.chronos_adapter import ChronosAdapter  # noqa: E402

OUT = REPO / "results/forecasting/live_backtest.json"
LEVEL_UNIT = "congestion_level_0_3"
HORIZONS = [15, 30, 60]
MIN_CONTEXT = 8


def adapters(names: list[str]):
    table = {"Chronos-Bolt": ChronosAdapter, "persistence": PersistenceAdapter,
             "historical_average": HistoricalAverageAdapter}
    return [table[n]() for n in names]


def backtest(vals, mask, corridors, bins, models, horizons=HORIZONS, stride=3,
             city="dhaka") -> dict:
    T, N = vals.shape
    hb = {h: int(round(h * 60 / live_state.BIN_S)) for h in horizons}
    last_origin = T - 1 - max(hb.values())
    origins = list(range(MIN_CONTEXT, last_origin + 1, stride))
    preds = {m.name: {h: {} for h in horizons} for m in models}   # name -> h -> (t,n) -> pred
    t0 = time.time()
    for k, t in enumerate(origins):
        cd = CityData(city_id=city, node_ids=list(corridors), values=vals[: t + 1].astype("float32"),
                      interval_s=live_state.BIN_S, target="corridor congestion level",
                      unit=LEVEL_UNIT, reality="REAL_LIVE (recorded)")
        for m in models:
            try:
                f = m.forecast(cd, horizons)
            except NotAvailable:
                continue
            for h in horizons:
                for n, p in enumerate(f.values[h]):
                    if p is not None and np.isfinite(p) and mask[t + hb[h], n]:
                        preds[m.name][h][(t, n)] = float(p)
        if k % 25 == 0:
            print(f"[backtest] origin {k + 1}/{len(origins)} ({time.time() - t0:.0f}s)", flush=True)

    rows, traces = [], {}
    for h in horizons:
        # the SAME pairs for every model
        common = set.intersection(*(set(preds[m.name][h]) for m in models))
        if not common:
            continue
        keys = sorted(common)
        truth = np.array([vals[t + hb[h], n] for t, n in keys])
        per_model = {}
        for m in models:
            p = np.array([preds[m.name][h][k] for k in keys])
            err = p - truth
            per_model[m.name] = {
                "mae": float(np.mean(np.abs(err))), "rmse": float(np.sqrt(np.mean(err ** 2))),
                "class_accuracy": float(np.mean(np.clip(np.rint(p), 0, 3) == truth)),
            }
        base = per_model.get("persistence", {}).get("mae")
        for m in models:
            r = per_model[m.name]
            rows.append({"model": m.name, "is_baseline": bool(m.is_baseline), "horizon_min": h,
                         "mae": round(r["mae"], 4), "rmse": round(r["rmse"], 4),
                         "class_accuracy": round(r["class_accuracy"], 4),
                         "skill_vs_persistence": (round(1 - r["mae"] / base, 4)
                                                  if base else None),
                         "n_pairs": len(keys)})
        # trace: per origin, mean over the nodes scored at that origin, for the overlay chart
        by_t: dict[int, list] = {}
        for i, (t, n) in enumerate(keys):
            by_t.setdefault(t, []).append(i)
        traces[h] = [{"target_utc": datetime.fromtimestamp(float(bins[t + hb[h]]),
                                                            timezone.utc).isoformat(),
                      "actual": round(float(truth[idx].mean()), 3),
                      **{m.name: round(float(np.mean([preds[m.name][h][keys[i]] for i in idx])), 3)
                         for m in models}}
                     for t, idx in sorted(by_t.items())]

    verdict = {}
    for h in horizons:
        hr = {r["model"]: r for r in rows if r["horizon_min"] == h}
        if "Chronos-Bolt" in hr and "persistence" in hr:
            c, p = hr["Chronos-Bolt"], hr["persistence"]
            verdict[h] = {"chronos_beats_persistence": c["mae"] < p["mae"],
                          "mae_chronos": c["mae"], "mae_persistence": p["mae"],
                          "best_model": min(hr.values(), key=lambda r: r["mae"])["model"]}

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "city": city, "unit": LEVEL_UNIT,
        "source": str(live_state.SRC.relative_to(REPO)),
        "reality": "REAL_LIVE derived congestion classes (RUNTIME_REFERENCE)",
        "protocol": ("rolling origin: at every origin bin the series is cut there, each model "
                     "forecasts from that history only, and is scored on what was later recorded; "
                     "all models scored on identical pairs"),
        "bins": int(T), "nodes": int(N), "origins_evaluated": len(origins), "stride_bins": stride,
        "span_utc": [datetime.fromtimestamp(float(bins[0]), timezone.utc).isoformat(),
                     datetime.fromtimestamp(float(bins[-1]), timezone.utc).isoformat()],
        "horizons_min": horizons,
        "rows": rows, "verdict": verdict, "traces": traces,
        "wall_s": round(time.time() - t0, 1),
        "command": "python -m traffictwin.forecasting.live.live_backtest",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", type=Path, default=live_state.SRC)
    p.add_argument("--models", default="Chronos-Bolt,persistence,historical_average")
    p.add_argument("--horizons", default="15,30,60")
    p.add_argument("--stride", type=int, default=3, help="origin spacing in bins (3 = 15 min)")
    p.add_argument("--out", type=Path, default=OUT)
    a = p.parse_args()
    rows = live_state.load_rows(a.src)
    vals, mask, corridors, bins = live_state.build(rows)
    horizons = [int(x) for x in a.horizons.split(",")]
    rec = backtest(vals, mask, corridors, bins, adapters(a.models.split(",")), horizons, a.stride)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(rec, indent=1))
    print(f"\n[backtest] {rec['bins']} bins x {rec['nodes']} nodes, {rec['origins_evaluated']} origins")
    print(f"{'model':<20}{'h':>5}{'MAE':>8}{'RMSE':>8}{'acc':>7}{'skill':>8}{'n':>7}")
    for r in rec["rows"]:
        sk = "" if r["skill_vs_persistence"] is None else f"{r['skill_vs_persistence']:+.3f}"
        print(f"{r['model']:<20}{r['horizon_min']:>5}{r['mae']:>8.3f}{r['rmse']:>8.3f}"
              f"{r['class_accuracy']:>7.1%}{sk:>8}{r['n_pairs']:>7}")
    for h, v in rec["verdict"].items():
        print(f"[backtest] +{h} min: best {v['best_model']}; Chronos beats persistence: "
              f"{v['chronos_beats_persistence']}")
    print(f"[backtest] wrote {a.out.relative_to(REPO)} ({rec['wall_s']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
