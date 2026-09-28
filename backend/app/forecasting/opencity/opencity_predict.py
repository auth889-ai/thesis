#!/usr/bin/env python3
"""OpenCity-plus PREDICTIONS for a city of ours — the authors' model, their loader, their weights.

    python -m app.forecasting.opencity.opencity_predict --source observatory --city dhaka
    python -m app.forecasting.opencity.opencity_predict --source csv --csv city.csv --adj city_rn_adj.npy
    python -m app.forecasting.opencity.opencity_predict --source metrla-smoke --as-of -288    # scored

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

from app.paths import REPO
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


DATASET_START = {"METR_LA": "2012-03-01T00:00:00+00:00", "PEMS_BAY": "2017-01-01T00:00:00+00:00"}
IN_PRETRAINING = {"METR_LA", "PEMS_BAY", "PEMS04", "PEMS08"}


def local_datasets() -> list[dict]:
    """The real datasets present in the pinned OpenCity checkout (their own layout)."""
    out = []
    for d in sorted((OC / "data").iterdir()) if (OC / "data").exists() else []:
        f, a = d / f"{d.name}.npz", d / f"{d.name}_rn_adj.npy"
        if d.name.startswith("DF_"):
            continue                                    # a temporary sub-graph a run is using right now
        if f.exists() and a.exists():
            arr = np.load(f)["data"]
            out.append({"id": d.name, "nodes": int(arr.shape[1]), "steps": int(arr.shape[0]),
                        "start_utc": DATASET_START.get(d.name), "interval_min": 5,
                        "exposure": "IN_PRETRAINING" if d.name in IN_PRETRAINING else "HELD_OUT_ZERO_SHOT"})
    return out


def subgraph(A: np.ndarray, region: int, n_nodes: int) -> list[int]:
    """The region plus its strongest neighbours by adjacency weight — a real sub-graph OpenCity
    can serve zero-shot (it needs >= 9 nodes), small enough for a CPU forward pass."""
    w = np.asarray(A, dtype="float64").copy()
    np.fill_diagonal(w, 0.0)
    score = w[region] + w[:, region]
    order = [int(i) for i in np.argsort(-score) if i != region and score[i] > 0]
    if len(order) < n_nodes - 1:                        # pad with 2-hop neighbours, then anything
        two = (w @ w)[region]
        order += [int(i) for i in np.argsort(-two) if i != region and int(i) not in order]
    return [region] + order[: max(MIN_NODES - 1, n_nodes - 1)]


def from_dataset(name: str, region: int, n_nodes: int):
    d = np.load(OC / "data" / name / f"{name}.npz")["data"].astype("float64")
    if d.ndim == 3:
        d = d[:, :, 0]
    A = np.load(OC / "data" / name / f"{name}_rn_adj.npy")
    idx = subgraph(A, region, n_nodes)
    vals = d[:, idx]
    vals[vals == 0] = np.nan                            # 0 encodes a missing reading in these files
    return vals, [f"{name}#{i}" for i in idx], A[np.ix_(idx, idx)].astype("float32"), {
        "quantity": {"METR_LA": "speed mph", "PEMS_BAY": "speed mph", "PEMS07M": "speed",
                     "TrafficSH": "traffic index"}.get(name, "as released"),
        "reality": "REAL" + (", IN OpenCity's pre-training corpus" if name in IN_PRETRAINING else ", held out (zero-shot)"),
        "first_utc": DATASET_START.get(name), "region_index": region, "subgraph": idx}


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
        from app.forecasting.opencity import _opencity_boot as boot
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
    p.add_argument("--source", choices=["observatory", "recorded", "csv", "metrla-smoke", "dataset"], default="observatory")
    p.add_argument("--city", default="dhaka")
    p.add_argument("--dataset", default="METR_LA", help="--source dataset: a dataset in the OpenCity checkout")
    p.add_argument("--region", type=int, default=0, help="--source dataset: node index to centre the sub-graph on")
    p.add_argument("--nodes", type=int, default=48, help="--source dataset: sub-graph size")
    p.add_argument("--csv", type=Path); p.add_argument("--adj", type=Path)
    p.add_argument("--as-of", type=int, default=None,
                   help="end the input window at this index (negative counts from the end); "
                        "what follows is used to score the prediction")
    p.add_argument("--horizons", default="15,30,60")
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    from app.forecasting.opencity import opencity_city_eval as oce

    if a.source == "csv":
        if not (a.csv and a.adj):
            raise SystemExit("--source csv needs --csv and --adj")
        vals, nodes, A, meta = load_csv(a.csv, a.adj); name = "DF_UPLOAD"
    elif a.source == "metrla-smoke":
        vals, nodes, A, meta = oce.metrla_smoke(steps=2000); name = "DF_SMOKE"
    elif a.source == "dataset":
        vals, nodes, A, meta = from_dataset(a.dataset, a.region, a.nodes); name = f"DF_{a.dataset.upper()}_R{a.region}"
    elif a.source == "observatory":
        vals, nodes, meta = oce.from_observatory(a.city); A = oce.geo_adjacency(nodes)
        name = f"DF_{a.city.upper()}_LIVE"
    else:
        vals, nodes, meta = oce.from_recorded(); A = oce.geo_adjacency(nodes); name = "DF_DHAKA_RECORDED"

    T = vals.shape[0]
    end = T if a.as_of is None else (a.as_of if a.as_of > 0 else T + a.as_of)
    hist = vals[:end]
    first_utc = meta.get("first_utc")
    if first_utc and a.source == "dataset":
        # the window's own clock: the dataset start plus the offset of its first input step
        from datetime import timedelta
        first_utc = (datetime.fromisoformat(first_utc) + timedelta(minutes=5 * max(0, end - HIS))).isoformat()
    pred = forward(name, hist, A, first_utc)
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
                     else "NOT zero-shot: this dataset is inside OpenCity's pre-training corpus"
                     if a.source == "dataset" and a.dataset in IN_PRETRAINING
                     else "zero-shot: the city is absent from OpenCity's pre-training corpus"),
           "region": {"index": meta.get("region_index"), "position_in_subset": 0,
                      "subgraph": meta.get("subgraph")} if a.source == "dataset" else None,
           "history_region": [None if x != x else round(float(x), 3) for x in hist[-72:, 0]] if a.source == "dataset" else None,
           "prediction_region": [round(float(x), 3) for x in pred[:12, 0]] if a.source == "dataset" else None,
           "actual_region": ([None if x != x else round(float(x), 3) for x in vals[end:end + 12, 0]]
                             if a.source == "dataset" and end < T else None),
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
