#!/usr/bin/env python3
"""Load a trained checkpoint and forecast an unseen test window — proof the model is usable, not just scored.

    python predict/infer_from_checkpoint.py --list
    python predict/infer_from_checkpoint.py --model GWNet --dataset METR-LA
    python predict/infer_from_checkpoint.py --model GWNet --dataset METR-LA --window 500 --sensors 3

A metrics table proves a training run finished. It does not prove the artefact can be reloaded and
used, which is what "reproducible" actually requires. This script:

  1. loads the saved checkpoint with the OFFICIAL architecture from the pinned BasicTS-legacy repo,
  2. rebuilds the same z-score scaler from the training split,
  3. feeds it one window the model never saw (from the chronological TEST region),
  4. prints and saves ACTUAL vs PREDICTED at 5 / 15 / 30 / 60 minutes,
  5. recomputes MAE from those predictions and compares it to the metrics reported during training —
     if the reloaded model does not reproduce its own reported error, the checkpoint is not the model
     that was scored, and everything downstream is unsafe.

Checkpoints come from `predict/aws_train.py --collect-checkpoints` (S3) and are never trained here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
CKPT_DIR = REPO / "predict/results/checkpoints"
RESULTS = REPO / "predict/results"
BTS = Path.home() / ".dhakaflow/upstream/BasicTS_legacy"


def find_checkpoints() -> list[dict]:
    out = []
    for pt in sorted(CKPT_DIR.rglob("*.pt")):
        parts = pt.relative_to(CKPT_DIR).parts
        arch = parts[0] if parts else "?"
        ds = next((p.split("_")[0] for p in parts if "_" in p and p.split("_")[0].replace("-", "").isalnum()), "?")
        out.append({"path": pt, "arch": arch, "dataset_dir": ds,
                    "size_mb": round(pt.stat().st_size / 1e6, 2),
                    "test_results": next(iter(pt.parent.glob("test_results.npz")), None),
                    "test_metrics": next(iter(pt.parent.glob("test_metrics.json")), None)})
    return out


def load_official_cfg(model_dir: str, dataset: str):
    """Load the OFFICIAL config from the pinned upstream repo — never a local re-implementation.

    Three things the upstream layout requires, each found by running it:
      1. the config does `from .arch import ...`, so it must be executed with a real parent package;
      2. it reads `datasets/<name>/desc.json` by RELATIVE path, so the CWD must be the harness root;
      3. the model consumes only `MODEL.FORWARD_FEATURES` (GWNet: [speed, time-of-day]), not every
         channel — feeding all three raises "expected input to have 2 channels, but got 3".
    """
    import importlib
    import importlib.util
    if not BTS.exists():
        raise SystemExit(f"pinned harness missing at {BTS}")
    cfg_path = BTS / f"baselines/{model_dir}/{dataset}.py"
    if not cfg_path.exists():
        raise SystemExit(f"official config not found: {cfg_path}")
    sys.path.insert(0, str(BTS))
    pkg = f"baselines.{model_dir}"
    importlib.import_module(pkg)                                   # (1) parent package
    name = f"{pkg}.cfg_{dataset.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(name, cfg_path)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg
    sys.modules[name] = mod
    cwd = os.getcwd()
    os.chdir(BTS)                                                  # (2) relative desc.json
    try:
        spec.loader.exec_module(mod)
    finally:
        os.chdir(cwd)
    return mod.CFG, cfg_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true")
    p.add_argument("--model", default="GWNet")
    p.add_argument("--dataset", default="METR-LA")
    p.add_argument("--window", type=int, default=0, help="index into the test region")
    p.add_argument("--sensors", type=int, default=3, help="how many sensors to print")
    p.add_argument("--verify-windows", type=int, default=200,
                   help="evaluate this many spaced test windows to check the checkpoint reproduces "
                        "its reported MAE (0 to skip)")
    a = p.parse_args()

    cks = find_checkpoints()
    if a.list or not cks:
        if not cks:
            print(f"no checkpoints under {CKPT_DIR}\n"
                  f"fetch them:  python predict/aws_train.py --job <job> --collect-checkpoints")
            return 1
        print(f"{'arch':<16} {'size MB':>8}  path")
        for c in cks:
            print(f"{c['arch']:<16} {c['size_mb']:>8}  {c['path'].relative_to(REPO)}")
        return 0

    arch_alias = {"GWNet": "GraphWaveNet", "STID": "STID", "DCRNN": "DCRNN", "STAEformer": "STAEformer"}
    want = arch_alias.get(a.model, a.model)
    cand = [c for c in cks if c["arch"] == want]
    if not cand:
        print(f"no checkpoint for {a.model} (arch {want}); available: {sorted({c['arch'] for c in cks})}")
        return 1
    ck = cand[0]
    print(f"[infer] checkpoint {ck['path'].relative_to(REPO)} ({ck['size_mb']} MB)")

    import torch
    cfg, cfg_path = load_official_cfg(a.model, a.dataset)
    model = cfg.MODEL.ARCH(**cfg.MODEL.PARAM)
    fwd = list(cfg.MODEL.get("FORWARD_FEATURES", [0]))             # (3) channels the model expects
    state = torch.load(ck["path"], map_location="cpu", weights_only=False)
    sd = state.get("model_state_dict", state)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print(f"[infer] official {cfg.MODEL.ARCH.__name__} from {cfg_path.relative_to(BTS)}, "
          f"forward_features={fwd}")
    print(f"[infer] loaded weights: {sum(p.numel() for p in model.parameters()):,} parameters; "
          f"missing={len(missing)} unexpected={len(unexpected)}")
    if missing or unexpected:
        print(f"[infer] WARNING: key mismatch — missing {list(missing)[:3]}, unexpected {list(unexpected)[:3]}")
    model.eval()

    # data: the same prepared tensors the harness trained on
    ds_dir = BTS / "datasets" / a.dataset
    dat, desc = ds_dir / "data.dat", ds_dir / "desc.json"
    if not dat.exists():
        print(f"prepared dataset missing at {ds_dir}. Prepare it once with the harness's own script:\n"
              f"  cd {BTS} && python scripts/data_preparation/{a.dataset}/generate_training_data.py")
        return 1
    d = json.loads(desc.read_text())
    shape = d["shape"] if "shape" in d else [d["num_time_steps"], d["num_nodes"], d["num_features"]]
    raw = np.memmap(dat, dtype="float32", mode="r", shape=tuple(shape))
    T, N, C = raw.shape
    L = int(cfg.DATASET.PARAM.input_len)
    H = int(cfg.DATASET.PARAM.output_len)
    n_train = int(T * 0.7)
    test_lo = n_train + int(T * 0.1)
    mu = raw[:n_train, :, 0].mean()
    sd_ = raw[:n_train, :, 0].std()
    print(f"[infer] {a.dataset}: T={T} N={N} C={C}; z-score from TRAIN split mu={mu:.3f} sd={sd_:.3f}; "
          f"test region starts at t={test_lo}")

    t0 = test_lo + max(0, a.window)
    if t0 + L + H > T:
        print("window past the end of the series")
        return 1
    x = np.array(raw[t0:t0 + L], dtype="float32")[None]        # (1, L, N, C)
    y = np.array(raw[t0 + L:t0 + L + H, :, 0], dtype="float32")  # (H, N)
    xn = x.copy()
    xn[..., 0] = (xn[..., 0] - mu) / sd_
    xt = torch.tensor(xn)[..., fwd]                                # only FORWARD_FEATURES
    with torch.no_grad():
        out = model(history_data=xt, future_data=None, batch_seen=0, epoch=1, train=False)
        pred = (out if isinstance(out, torch.Tensor) else out["prediction"]).numpy()
    pred = pred[0, ..., 0] * sd_ + mu                          # (H, N) back in mph
    print(f"[infer] forecast produced: {pred.shape} (horizon x sensors)")

    steps = {5: 1, 15: 3, 30: 6, 60: 12}
    obs = np.where(y > 0)                                       # observed only (0 = sensor outage)
    mae_all = float(np.abs(pred[obs] - y[obs]).mean())
    rows = []
    print(f"\n{'horizon':>8} {'sensor':>7} {'actual':>9} {'predicted':>10} {'error':>8}")
    for mnt, st in steps.items():
        if st > H:
            continue
        good = np.where(y[st - 1] > 0)[0][: a.sensors]
        for s in good:
            act, prd = float(y[st - 1, s]), float(pred[st - 1, s])
            rows.append({"horizon_min": mnt, "sensor_index": int(s), "actual_mph": round(act, 2),
                         "predicted_mph": round(prd, 2), "abs_error_mph": round(abs(prd - act), 2)})
            print(f"{mnt:>6} min {s:>7} {act:>9.2f} {prd:>10.2f} {abs(prd - act):>8.2f}")
        m = y[st - 1] > 0
        rows.append({"horizon_min": mnt, "sensor_index": "ALL", "actual_mph": None, "predicted_mph": None,
                     "abs_error_mph": round(float(np.abs(pred[st - 1][m] - y[st - 1][m]).mean()), 3)})

    reported = None
    tr = RESULTS / "trained_results.json"
    if tr.exists():
        for r in json.loads(tr.read_text())["runs"]:
            if r["model"] == a.model and r["dataset"] == a.dataset:
                # JSON object keys are strings; normalise so the lookup cannot silently miss
                reported = {int(k): v for k, v in r["metrics_by_horizon_min"].items()}

    # ---- the actual G6 check: does the RELOADED model reproduce its reported test error? ----
    verify = None
    if a.verify_windows:
        idx = np.linspace(test_lo, T - L - H - 1, a.verify_windows, dtype=int)
        errs = {st: [] for st in steps.values() if st <= H}
        for t in idx:
            xw = np.array(raw[t:t + L], dtype="float32")[None]
            xw[..., 0] = (xw[..., 0] - mu) / sd_
            yw = np.array(raw[t + L:t + L + H, :, 0], dtype="float32")
            with torch.no_grad():
                o = model(history_data=torch.tensor(xw)[..., fwd], future_data=None,
                          batch_seen=0, epoch=1, train=False)
            pw = (o if isinstance(o, torch.Tensor) else o["prediction"]).numpy()[0, ..., 0] * sd_ + mu
            for st in errs:
                m = yw[st - 1] > 0                              # observed only; 0 = sensor outage
                if m.any():
                    errs[st].append(np.abs(pw[st - 1][m] - yw[st - 1][m]).mean())
        verify = {}
        print(f"\n[verify] {len(idx)} spaced test windows — reloaded checkpoint vs training report")
        for st, v in errs.items():
            mnt = st * 5
            got = float(np.mean(v))
            rep = (reported or {}).get(mnt, {}).get("mae")
            d = (100 * (got / rep - 1)) if rep else None
            verify[mnt] = {"reloaded_mae": round(got, 4), "reported_mae": rep,
                           "diff_pct": round(d, 2) if d is not None else None, "windows": len(v)}
            print(f"    {mnt:>3} min  reloaded {got:.3f}  reported {rep}  "
                  f"{'' if d is None else f'{d:+.1f} %'}")
        ok = all(abs(v["diff_pct"]) <= 15 for v in verify.values() if v["diff_pct"] is not None)
        print(f"[verify] {'PASS' if ok else 'FAIL'} — the checkpoint "
              f"{'reproduces' if ok else 'does NOT reproduce'} its reported test error")
    rec = {"model": a.model, "dataset": a.dataset, "checkpoint": str(ck["path"].relative_to(REPO)),
           "window_index_in_test": a.window, "t0_absolute": int(t0), "input_len": L, "horizon_len": H,
           "scaler": {"mu": float(mu), "sd": float(sd_), "fitted_on": "train split only"},
           "window_mae_all_horizons_mph": round(mae_all, 3),
           "reported_test_metrics": reported, "verification": verify,
           "note": "single unseen window; the training metrics average the whole test set, so these "
                   "differ in magnitude — the check is that they are the same order, not identical",
           "rows": rows}
    (RESULTS / f"inference_{a.model}_{a.dataset}.json").write_text(json.dumps(rec, indent=1))
    print(f"\n[infer] window MAE over all horizons: {mae_all:.3f} mph")
    if reported:
        print(f"[infer] training-reported MAE @15min: {reported.get(15, {}).get('mae')} mph "
              f"(whole test set) — same order of magnitude expected")
    print(f"[infer] wrote {RESULTS / f'inference_{a.model}_{a.dataset}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
