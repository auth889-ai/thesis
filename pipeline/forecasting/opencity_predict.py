#!/usr/bin/env python3
"""OpenCity-plus PREDICTIONS for a city of ours — the authors' model, their loader, their weights.

    python pipeline/forecasting/opencity_predict.py --source observatory --city dhaka
    python pipeline/forecasting/opencity_predict.py --source csv --csv city.csv --adj city_rn_adj.npy
    python pipeline/forecasting/opencity_predict.py --source metrla-smoke --as-of -288    # scored

`opencity_city_eval.py` runs the authors' `-mode test` and reports their 24-hour average metric.
This script does what their demo does: takes the last 288 steps of a city's series and returns
the next 288 steps, per node, from a forward pass of `OpenCity-plus.pth` — built with THEIR
`parse_args` / `get_predictor_params` / `Traffic_model` / `load_st_dataset`, under the same
boot shims, with no upstream file edited. With `--as-of` before the end of the series the
prediction is scored against what followed, at 15 / 30 / 60 minutes, beside persistence on the
same window — the horizons our own backtest uses, so the numbers are comparable.

Input contract (the one their Gradio demo uses): a CSV with a `time` column and one column per
region, plus an `<name>_rn_adj.npy` adjacency; or the recorded / persisted windows this project
already holds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
WORKSPACE = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream"))
OC = WORKSPACE / "OpenCity"
CONF = OC / "conf/general_conf/pretrain.conf"
OUT = REPO / "results/forecasting"
HIS = PRED = 288
MIN_NODES = 9


def load_csv(csv: Path, adj: Path):
    import pandas as pd
    df = pd.read_csv(csv)
    tcol = next((c for c in df.columns if c.lower() in ("time", "timestamp", "datetime")), df.columns[0])
    times = pd.to_datetime(df[tcol]).dt.tz_localize("UTC", ambiguous="NaT", nonexistent="NaT") \
        if pd.to_datetime(df[tcol]).dt.tz is None else pd.to_datetime(df[tcol])
    vals = df.drop(columns=[tcol]).to_numpy(dtype="float64")
    nodes = [str(c) for c in df.columns if c != tcol]
    A = np.load(adj)
    if A.shape != (len(nodes), len(nodes)):
        raise SystemExit(f"adjacency is {A.shape}, the CSV has {len(nodes)} regions")
    return vals, nodes, A.astype("float32"), {"quantity": "as uploaded", "reality": "USER_UPLOAD",
                                              "first_utc": times.iloc[0].isoformat(),
                                              "last_utc": times.iloc[-1].isoformat()}


def _write_dataset(name: str, vals: np.ndarray, A: np.ndarray) -> Path:
    ddir = OC / "data" / name
    ddir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(ddir / f"{name}.npz", data=np.nan_to_num(vals, nan=0.0).astype("float32"))
    np.save(ddir / f"{name}_rn_adj.npy", A.astype("float32"))
    return ddir


def forward(name: str, vals: np.ndarray, A: np.ndarray, first_utc: str | None) -> np.ndarray:
    """(T, N) -> (PRED, N) predictions from the last HIS steps, through the authors' stack."""
    T, N = vals.shape
    if N < MIN_NODES:
        raise SystemExit(f"OpenCity needs >= {MIN_NODES} nodes (8 Laplacian eigenvectors); got {N}")
    if T < HIS:
        raise SystemExit(f"OpenCity needs {HIS} input steps; got {T} ({(HIS - T) * 5 / 60:.1f} h more)")
    ddir = _write_dataset(name, vals[-HIS:], A)
    original = CONF.read_text()
    cwd = os.getcwd()
    try:
        CONF.write_text(re.sub(r"^dataset_use\s*=.*$", f"dataset_use = ['{name}']", original,
                               count=1, flags=re.MULTILINE))
        if first_utc:
            t = datetime.fromisoformat(first_utc).astimezone(timezone.utc)
            local_min = (t.hour * 60 + t.minute + 6 * 60) % 1440           # Asia/Dhaka, no DST
            os.environ["DF_OC_DAY_START"] = str(local_min // 5)
            os.environ["DF_OC_WEEK_START"] = str(t.weekday() + 1)
        from pipeline.forecasting import _opencity_boot as boot
        boot.install(); boot.install_torch_cpu_load()
        os.chdir(OC / "model")
        for p in (str(OC / "model"), str(OC)):
            if p not in sys.path:
                sys.path.insert(0, p)
        boot.install_generic_dataset()
        import torch
        from lib.Params_pretrain import parse_args
        from lib.Params_predictor import get_predictor_params
        from lib.data_process import load_st_dataset
        from model.Model import Traffic_model
        sys.argv = ["Run.py", "-mode", "test", "-model", "OpenCity", "-load_pretrain_path",
                    "OpenCity-plus.pth", "-batch_size", "1", "-test_ratio", "1.0", "-val_ratio", "0.0",
                    "--embed_dim", "512", "--skip_dim", "512", "--enc_depth", "6"]
        device = torch.device("cpu")
        args = parse_args(device)
        args.num_nodes_dict = {name: N}
        args.dataset_use = [name]
        args_predictor = get_predictor_params(args)
        for attr in list(vars(args)):                        # exactly Run.py's merge for non-pretrain
            if hasattr(args_predictor, attr):
                setattr(args, attr, getattr(args_predictor, attr))
        data = load_st_dataset(name, args)                    # (HIS, N, 3): value, time-of-day, weekday
        model = Traffic_model(args, args_predictor)
        sd = torch.load(OC / "model_weights/OpenCity/OpenCity-plus.pth", map_location="cpu")
        sd = {k.replace("module.", ""): v for k, v in sd.items()}
        model.load_state_dict(sd)
        model.eval()
        x = torch.from_numpy(data[-HIS:][None].astype("float32"))
        y = torch.zeros((1, PRED, N, data.shape[-1]), dtype=torch.float32)
        with torch.no_grad():
            out = model(x, y, name, batch_seen=None)            # (1, PRED, N, 1), real values
        return out[0, :, :, 0].numpy()
    finally:
        CONF.write_text(original)
        os.chdir(cwd)
        shutil.rmtree(ddir, ignore_errors=True)


def score(pred: np.ndarray, actual: np.ndarray, last: np.ndarray, horizons: list[int]) -> dict:
    """MAE at each horizon vs what followed, beside persistence; masked where actual is missing."""
    rows = {}
    for h in horizons:
        k = h // 5 - 1
        if k >= actual.shape[0]:
            continue
        m = np.isfinite(actual[k]) & (actual[k] > 0)
        if not m.any():
            continue
        rows[h] = {"opencity_mae": round(float(np.abs(pred[k][m] - actual[k][m]).mean()), 4),
                   "persistence_mae": round(float(np.abs(last[m] - actual[k][m]).mean()), 4),
                   "n": int(m.sum())}
        rows[h]["skill_vs_persistence"] = round(1 - rows[h]["opencity_mae"] / rows[h]["persistence_mae"], 4) \
            if rows[h]["persistence_mae"] else None
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["observatory", "recorded", "csv", "metrla-smoke"], default="observatory")
    p.add_argument("--city", default="dhaka")
    p.add_argument("--csv", type=Path); p.add_argument("--adj", type=Path)
    p.add_argument("--as-of", type=int, default=None,
                   help="end the input window at this index (negative counts from the end); "
                        "what follows is used to score the prediction")
    p.add_argument("--horizons", default="15,30,60")
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    from pipeline.forecasting import opencity_city_eval as oce

    if a.source == "csv":
        if not (a.csv and a.adj):
            raise SystemExit("--source csv needs --csv and --adj")
        vals, nodes, A, meta = load_csv(a.csv, a.adj); name = "DF_UPLOAD"
    elif a.source == "metrla-smoke":
        vals, nodes, A, meta = oce.metrla_smoke(steps=2000); name = "DF_SMOKE"
    elif a.source == "observatory":
        vals, nodes, meta = oce.from_observatory(a.city); A = oce.geo_adjacency(nodes)
        name = f"DF_{a.city.upper()}_LIVE"
    else:
        vals, nodes, meta = oce.from_recorded(); A = oce.geo_adjacency(nodes); name = "DF_DHAKA_RECORDED"

    T = vals.shape[0]
    end = T if a.as_of is None else (a.as_of if a.as_of > 0 else T + a.as_of)
    hist = vals[:end]
    pred = forward(name, hist, A, meta.get("first_utc"))
    horizons = [int(h) for h in a.horizons.split(",")]
    last = np.nan_to_num(hist[-1], nan=0.0)
    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(), "model": "OpenCity-plus",
           "weights": "OpenCity-plus.pth (released)", "source": a.source, "city": a.city, "nodes": nodes,
           "input_steps": HIS, "output_steps": PRED, "as_of_index": int(end), "series_length": int(T),
           **{k: v for k, v in meta.items() if k in ("quantity", "reality", "first_utc", "last_utc")},
           "predictions": {str(h): [round(float(x), 3) for x in pred[h // 5 - 1]] for h in horizons},
           "curve_mean": [round(float(np.nanmean(pred[i])), 3) for i in range(PRED)],
           "scored": score(pred, vals[end:end + PRED], last, horizons) if end < T else None,
           "claim": ("MECHANICS ONLY — the slice is inside the pre-training corpus" if a.source == "metrla-smoke"
                     else "zero-shot: the city is absent from OpenCity's pre-training corpus"),
           "stack": "authors' parse_args / get_predictor_params / Traffic_model / load_st_dataset, "
                    "boot shims only (NumPy aliases, CPU load, DF_* loader branch)"}
    out = a.out or OUT / f"opencity_predict_{name.lower()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rec, indent=1))
    print(f"[opencity] {name}: {T} steps x {len(nodes)} nodes -> {PRED}-step prediction from index {end}")
    for h in horizons:
        s = (rec["scored"] or {}).get(h) or (rec["scored"] or {}).get(str(h))
        print(f"   +{h:>3} min  mean {np.nanmean(pred[h // 5 - 1]):8.3f}" +
              (f"   MAE {s['opencity_mae']} vs persistence {s['persistence_mae']} (skill {s['skill_vs_persistence']:+.2f})" if s else ""))
    print(f"[opencity] wrote {out.relative_to(REPO) if out.is_relative_to(REPO) else out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
