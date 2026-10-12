"""The map's forecast layer for Los Angeles: a replay of recorded METR-LA speeds with the D2STGNN forecast made at each moment.

    PYTHONPATH=.:backend python -m core.ml.forecasting.layer.build_la

For every 5-minute step of the METR-LA test split (the last 20 %, 2012-06-04 to 06-27, never used in training), one window as in
RQ1's Protocol B (context 96 steps, 12 steps ahead): the speed recorded now, and D2STGNN's forecast for +15/+30/+60 min from the
trained checkpoint through the RQ1 code path (checkpoint_stage.predict_checkpoints, unchanged). "No change" (persistence) and the
masked MAE are RQ1's own (protocol_b.baselines, protocol_b.scoring). Before anything is written, the same code is run on RQ1's
seed-11 windows and must reproduce the saved RQ1 predictions.

Writes results/forecasting/layer/{metr_la_replay.npz, summary.json} and evidence/forecast_layer/{build.log, SHA256SUMS}.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.common.paths import REPO
from core.ml.forecasting.evaluation.checkpoint_stage import predict_checkpoints
from core.ml.forecasting.evaluation.protocol_b import baselines
from core.ml.forecasting.evaluation.protocol_b.data import load, splits
from core.ml.forecasting.evaluation.protocol_b.scoring import score
from core.ml.forecasting.evaluation.protocol_b.settings import CONTEXT, STEPS

MODEL, DATASET = "D2STGNN", "METR-LA"
HORIZONS = (15, 30, 60)
OUT = REPO / "results/forecasting/layer"
EVID = REPO / "evidence/forecast_layer"
H5 = REPO / "data/forecasting/cities/METR-LA/METR-LA.h5"
RQ1_CHECK = REPO / "results/forecasting/protocol_b/METR-LA_test_w120_n207_s11.npz"


def log(msg: str) -> None:
    print(msg, flush=True)
    with (EVID / "build.log").open("a") as f:
        f.write(msg + "\n")


def windows_from(data: np.ndarray, starts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ctx = np.stack([data[s:s + CONTEXT] for s in starts])
    truth = np.stack([data[s + CONTEXT:s + CONTEXT + STEPS] for s in starts])
    return ctx, truth


def main() -> int:
    from pathlib import Path
    home_loc = Path.home() / ".dhakaflow/upstream/DCRNN/data/sensor_graph/graph_sensor_locations.csv"
    EVID.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (EVID / "build.log").write_text("")
    t0 = time.time()
    data = load(DATASET)                                         # (T, 207) mph, 0 = outage; RQ1's own data file
    T, N = data.shape
    idx = pd.read_hdf(H5).index
    cols = list(pd.read_hdf(H5).columns)
    assert len(idx) == T and len(cols) == N, "the h5 time axis and the evaluation data disagree"
    loc = pd.read_csv(home_loc, dtype={"sensor_id": str}).set_index("sensor_id").loc[cols]
    log(f"{DATASET}: {T} steps x {N} sensors, {idx[0]} to {idx[-1]}; sensor locations from {home_loc.name} in the data's column order")

    # 1. the RQ1 check: same checkpoint, same code, RQ1's seed-11 windows -> RQ1's saved predictions
    z = np.load(RQ1_CHECK)
    ctx, _ = windows_from(data, z["starts"])
    again = predict_checkpoints(DATASET, z["starts"], CONTEXT, STEPS, np.arange(N), ctx, only={MODEL})[MODEL]
    diff = float(np.abs(again - z[f"pred_{MODEL}"]).max())
    log(f"RQ1 check on {len(z['starts'])} seed-11 windows: largest difference to the saved {MODEL} predictions {diff:.2e} mph")
    if diff > 1e-3:
        log("STOP: the layer's predictions do not reproduce RQ1's"); return 1

    # 2. every step of the test split
    _, va_end = splits(T)
    starts = np.arange(va_end, T - CONTEXT - STEPS + 1)
    ctx, truth = windows_from(data, starts)
    pred = predict_checkpoints(DATASET, starts, CONTEXT, STEPS, np.arange(N), ctx, only={MODEL})[MODEL]
    persist = baselines.predict_persistence(ctx, STEPS)
    s_model, s_pers = score(pred, truth, z["threshold"]), score(persist, truth, z["threshold"])
    card = {}
    for h in HORIZONS:
        m, p = s_model[h]["mae"], s_pers[h]["mae"]
        card[str(h)] = {"mae": m, "no_change_mae": p, "skill": round(1 - m / p, 4), "n_observed": s_model[h]["n_observed"]}
        log(f"+{h} min: {MODEL} MAE {m} mph, no change {p} mph, skill {card[str(h)]['skill']}")

    now_i = starts + CONTEXT - 1                                 # the last recorded step of each window = "now"
    k = [h // 5 - 1 for h in HORIZONS]
    np.savez_compressed(OUT / "metr_la_replay.npz",
                        time=np.array(idx[now_i].strftime("%Y-%m-%dT%H:%M"), dtype="U16"),
                        now=data[now_i].astype("float16"),
                        forecast=pred[:, k, :].astype("float16"),
                        sensor_id=np.array(cols), lat=loc["latitude"].to_numpy(), lon=loc["longitude"].to_numpy())
    summary = {"label": "RECORDED (replayed) + FORECAST", "city_id": "los_angeles", "dataset": "METR-LA (DCRNN release, Li et al., ICLR 2018), 207 loop detectors",
               "units": "mph", "replay": {"first": str(idx[now_i[0]]), "last": str(idx[now_i[-1]]), "steps": int(len(starts)), "split": "test (last 20 %), never used in training"},
               "model": {"name": MODEL, "paper": "D2STGNN (Shao et al., VLDB 2022)", "harness": "BasicTS (Apache-2.0), checkpoint D2STGNN_best_val_MAE.pt",
                         "rq1_check": {"windows": int(len(z["starts"])), "max_abs_diff_mph": diff}},
               "horizons_min": list(HORIZONS), "card": card, "metric": "masked MAE (outages excluded), RQ1's protocol_b.scoring",
               "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "wall_s": round(time.time() - t0, 1)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    sums = "".join(f"{hashlib.sha256(f.read_bytes()).hexdigest()}  {f.relative_to(REPO)}\n" for f in (OUT / "metr_la_replay.npz", OUT / "summary.json", EVID / "build.log"))
    (EVID / "SHA256SUMS").write_text(sums)
    log(f"wrote {OUT.relative_to(REPO)} ({len(starts)} steps) in {summary['wall_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
