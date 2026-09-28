#!/usr/bin/env python3
"""TRAIN ON THIS CITY'S OWN DATA — the pinned BasicTS harness, start to finish, on CPU.

    python src/pipeline/forecasting/basicts_train.py --dataset user:test_town --arch STID --epochs 30
    python src/pipeline/forecasting/basicts_train.py --list

The official baselines (STID, GraphWaveNet) are trained the way their authors train them —
THEIR data-preparation script, THEIR config, THEIR runner (`experiments/train.py`), THEIR
metrics (masked MAE / RMSE / MAPE at horizons 3, 6, 12) — on a dataset of OURS: an uploaded
CSV or a city the observatory has been watching. Nothing in the harness is edited; two files are
*added* under its tree per dataset, both derived from their own templates by substituting the
"hot parameters" at the top:

    scripts/data_preparation/DF_<name>/generate_training_data.py   (from METR-LA's script)
    baselines/<arch>/DF_<name>.py                                   (from METR-LA's config)

Their runner writes the checkpoint and the test metrics; we keep a small card next to them in
results/forecasting/trained/ so the app can list, load and score the model. The z-score scaler is
rebuilt from the training split exactly as their ZScoreScaler does, and the model is fed only its
FORWARD_FEATURES, as in infer_from_checkpoint.py.

Fairness: persistence is scored on the SAME test split with THEIR masked MAE, so "beats the
floor" means something.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
BTS = Path.home() / ".dhakaflow/upstream/BasicTS_legacy"
CARDS = REPO / "results/forecasting/trained"
ARCHS = {"STID": "STID", "GWNet": "GWNet", "STAEformer": "STAEformer", "DCRNN": "DCRNN"}   # app name -> baselines/<dir>
ARCH_CLASS = {"STID": "STID", "GWNet": "GraphWaveNet", "STAEformer": "STAEformer", "DCRNN": "DCRNN"}
ARCH_PAPER = {"STID": "Shao et al. 2022 (CIKM)", "GWNet": "Wu et al. 2019 (IJCAI)", "STAEformer": "Liu et al. 2023 (CIKM)",
              "DCRNN": "Li et al. 2018 (ICLR)"}
MIN_STEPS = 240                                             # 10 % validation split must hold one 12+12 window
IN_LEN = OUT_LEN = 12


def bts_name(dataset_id: str) -> str:
    return "DF_" + re.sub(r"[^A-Za-z0-9]+", "_", dataset_id).strip("_")


# ------------------------------------------------------------------ our data -> their raw layout
def load_series(dataset_id: str):
    """(values[T,N], node names, ISO times, adjacency[N,N], interval_s, quantity) for an app dataset."""
    sys.path.insert(0, str(REPO / "src/dashboard/backend"))
    if dataset_id.startswith("user:"):
        import user_datasets
        did = dataset_id.split(":", 1)[1]
        m = user_datasets.load_meta(did)
        if not m:
            raise SystemExit(f"no uploaded dataset {did}")
        p = user_datasets.paths(did)
        vals = np.load(p["npz"])["data"].astype("float64")
        import pandas as pd
        times = pd.read_csv(p["csv"], usecols=["time"])["time"].tolist()
        return vals, m["nodes"], times, np.load(p["adj"]), int(m["interval_s"]), m["quantity"]
    if dataset_id.startswith("live:"):
        raise SystemExit("live corridor history is derived from Google Routes responses and is not licensed as "
                         "training data — upload your own or a research dataset (user:<id>)")
    if False:                                              # kept for reference: how a live series would be read
        import observatory as obs_mod
        from pipeline.forecasting import opencity_city_eval as oce
        cid = dataset_id.split(":", 1)[1]
        cd = obs_mod.observatory.city_data(cid)
        rows, nodes = obs_mod.observatory.series(cid)
        vals = np.asarray(cd.values, dtype="float64")
        if cid == "dhaka":
            A = oce.geo_adjacency(list(cd.node_ids))
        else:
            import city_corridors
            byid = {c["id"]: c for c in city_corridors.load(cid)}
            pts = np.array([[(byid[n]["origin"]["lat"] + byid[n]["destination"]["lat"]) / 2,
                             (byid[n]["origin"]["lng"] + byid[n]["destination"]["lng"]) / 2] for n in cd.node_ids])
            dy = (pts[:, None, 0] - pts[None, :, 0]) * 111_000
            dx = (pts[:, None, 1] - pts[None, :, 1]) * 111_000 * np.cos(np.radians(pts[:, 0].mean()))
            dist = np.sqrt(dx ** 2 + dy ** 2); sigma = np.std(dist[dist > 0]) or 1.0
            A = np.exp(-(dist / sigma) ** 2); A[A < 0.1] = 0
        return vals, list(cd.node_ids), [r["utc"] for r in rows], A.astype("float32"), 300, cd.unit
    raise SystemExit("training here is for uploaded datasets (user:<id>); the benchmark cities carry GPU checkpoints")


def prepare(dataset_id: str) -> dict:
    """Run THEIR data-preparation script on our series (written first in their raw .h5 layout)."""
    import pandas as pd
    vals, nodes, times, A, interval_s, quantity = load_series(dataset_id)
    if vals.shape[0] < MIN_STEPS:
        raise SystemExit(f"{dataset_id} has {vals.shape[0]} steps; their 70/10/20 split needs at least {MIN_STEPS}")
    name = bts_name(dataset_id)
    raw = BTS / "datasets/raw_data" / name
    raw.mkdir(parents=True, exist_ok=True)
    idx = pd.to_datetime(pd.Series(times), utc=True).dt.tz_localize(None)
    df = pd.DataFrame(np.nan_to_num(vals, nan=0.0), index=pd.DatetimeIndex(idx), columns=[str(n) for n in nodes])
    df.to_hdf(raw / f"{name}.h5", key="df", mode="w")
    with open(raw / f"adj_{name}.pkl", "wb") as f:      # their METR-LA pickle layout: (ids, id->index, matrix)
        pickle.dump(([str(n) for n in nodes], {str(n): i for i, n in enumerate(nodes)}, np.asarray(A, dtype="float32")), f)
    tmpl = (BTS / "scripts/data_preparation/METR-LA/generate_training_data.py").read_text()
    steps_per_day = int(round(86400 / interval_s))
    src = (tmpl.replace("dataset_name = 'METR-LA'", f"dataset_name = '{name}'")
               .replace("steps_per_day = 288", f"steps_per_day = {steps_per_day}")
               .replace("domain = 'traffic speed'", f"domain = '{quantity}'"))
    assert src != tmpl, "their hot-parameter lines moved; adapt the substitutions"
    sd = BTS / "scripts/data_preparation" / name
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "generate_training_data.py").write_text(src)
    r = subprocess.run([sys.executable, str(sd / "generate_training_data.py")], cwd=BTS, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("their data preparation failed:\n" + (r.stderr or r.stdout)[-800:])
    desc = json.loads((BTS / "datasets" / name / "desc.json").read_text())
    from pipeline.forecasting import train_eval as te
    dd = BTS / "datasets" / name
    return {"name": name, "steps_per_day": steps_per_day, "nodes": len(nodes), "node_names": [str(n) for n in nodes],
            "desc": desc, "interval_s": interval_s, "quantity": quantity, "first_utc": times[0],
            "dataset_hash": te.sha256_file(dd / "data.dat"), "graph_hash": te.sha256_file(dd / "adj_mx.pkl", 8),
            "quality": te.to_jsonable(te.data_quality(vals, interval_s))}


def write_config(arch: str, name: str, n_nodes: int, epochs: int, steps_per_day: int, gpu: bool = False) -> Path:
    """Their METR-LA config for this architecture, with the dataset / size / epochs / device lines swapped."""
    d = ARCHS[arch]
    tmpl = (BTS / f"baselines/{d}/METR-LA.py").read_text()
    src = (tmpl.replace("DATA_NAME = 'METR-LA'", f"DATA_NAME = '{name}'")
               .replace('"num_nodes": 207', f'"num_nodes": {n_nodes}')
               .replace('"num_nodes" : 207', f'"num_nodes" : {n_nodes}')          # STAEformer's spacing
               .replace('"steps_per_day": 288', f'"steps_per_day": {steps_per_day}')
               .replace("NUM_EPOCHS = 100", f"NUM_EPOCHS = {epochs}")
               .replace("CFG.GPU_NUM = 1", "CFG.GPU_NUM = 0" if not gpu else "CFG.GPU_NUM = 1")
               .replace("CFG.EVAL.USE_GPU = True", "CFG.EVAL.USE_GPU = False" if not gpu else "CFG.EVAL.USE_GPU = True")
               .replace('"time_of_day_size": 288', f'"time_of_day_size": {steps_per_day}')
               .replace('"milestones": [1, 50, 80]', f'"milestones": [1, {max(2, epochs // 2)}, {max(3, epochs * 4 // 5)}]')
               .replace('"milestones": [1, 50]', f'"milestones": [1, {max(2, epochs // 2)}]')
               .replace('"milestones": [20, 30, 40, 50]', f'"milestones": [{max(1, epochs * 2 // 5)}, {max(2, epochs * 3 // 5)}, {max(3, epochs * 4 // 5)}, {max(4, epochs)}]')
               .replace('"milestones": [15, 30, 50]', f'"milestones": [{max(1, epochs * 3 // 10)}, {max(2, epochs * 3 // 5)}, {max(3, epochs)}]')
               # DCRNN's template calls random.randint with floats (-1e6, 1e6); Python >= 3.10 rejects
               # that — the same call with integer bounds, nothing else changes
               .replace("random.randint(-1e6, 1e6)", "random.randint(-1000000, 1000000)"))
    for must in (f"DATA_NAME = '{name}'", f"NUM_EPOCHS = {epochs}", "CFG.GPU_NUM = "):
        assert must in src, f"their config template changed around {must!r}"
    out = BTS / f"baselines/{d}/{name}{'_gpu' if gpu else ''}.py"
    out.write_text(src)
    return out


def parse_curve(log_text: str) -> list[dict]:
    """Per-epoch train loss / validation MAE from their log lines."""
    curve, epoch = [], 0
    for line in log_text.splitlines():
        m = LOG_EPOCH.search(line)
        if m:
            epoch = int(m.group(1))
        for kind, met, val in LOG_METRIC.findall(line):
            if met.lower() in ("loss", "mae") and kind.lower() in ("train", "val") and epoch:
                curve.append({"epoch": epoch, "kind": f"{kind.lower()}_{met.lower()}", "value": float(val)})
    return curve


def make_card(dataset_id: str, arch: str, epochs: int, prep: dict, cfg: Path, run: Path, log_text: str,
              where: str = "this CPU") -> dict:
    """The small record the app serves a trained model from: their checkpoint + their metrics."""
    best = next(iter(run.glob("*_best_val_MAE.pt")), None) or next(iter(run.glob("*.pt")), None)
    if best is None:
        raise RuntimeError(f"no .pt in {run}")
    name = prep["name"]
    from pipeline.forecasting import train_eval as te
    from pipeline.forecasting.aws_train import BASICTS_SHA
    cfg_cpu = BTS / f"baselines/{ARCHS[arch]}/{name}.py"
    dd = BTS / "datasets" / name
    if not prep.get("dataset_hash") and (dd / "data.dat").exists():       # a job prepared before hashing existed
        prep = {**prep, "dataset_hash": te.sha256_file(dd / "data.dat"), "graph_hash": te.sha256_file(dd / "adj_mx.pkl", 8)}
    if not prep.get("quality") and (dd / "data.dat").exists():
        raw0, _ = _prepared(name); v0 = np.asarray(raw0[:, :, 0], dtype="float64"); v0[v0 == 0] = np.nan
        prep = {**prep, "quality": te.to_jsonable(te.data_quality(v0, prep["interval_s"]))}
    key = te.cache_key(prep.get("dataset_hash", "?"), prep.get("graph_hash", "?"), arch,
                       hashlib.sha256(cfg_cpu.read_bytes()).hexdigest()[:8] if cfg_cpu.exists() else "?", BASICTS_SHA)
    card = {"dataset": dataset_id, "bts_name": name, "arch": arch, "arch_class": ARCH_CLASS[arch], "epochs": epochs, "cache_key": key,
            "dataset_hash": prep.get("dataset_hash"), "graph_hash": prep.get("graph_hash"), "upstream_sha": BASICTS_SHA,
            "quality": prep.get("quality"), "best_val_MAE": best_val_mae(log_text),
            "checkpoint": str(best), "config": str(cfg), "run_dir": str(run), "trained_utc": datetime.now(timezone.utc).isoformat(),
            "trained_on": where,
            "nodes": prep["nodes"], "node_names": prep["node_names"], "interval_s": prep["interval_s"], "quantity": prep["quantity"],
            "steps": prep["desc"]["num_time_steps"], "first_utc": prep["first_utc"], "curve": parse_curve(log_text),
            "test_metrics": parse_test_metrics(log_text, run), "persistence_test": persistence_floor(name),
            "stack": f"BasicTS-legacy (pinned): their data preparation, config, runner and masked metrics; {where}",
            "claim": "trained on this city's own data — a city-specific model"}
    CARDS.mkdir(parents=True, exist_ok=True)
    (CARDS / f"{name}__{arch}.json").write_text(json.dumps(te.to_jsonable(card), indent=1))
    return card


LOG_EPOCH = re.compile(r"Epoch (\d+) / (\d+)")
LOG_METRIC = re.compile(r"\b(train|val|test)[_/ ](MAE|RMSE|MAPE|loss):\s*([0-9]+\.[0-9]+)", re.I)


def train(dataset_id: str, arch: str = "STID", epochs: int = 30, progress=None) -> dict:
    """Prepare, configure, run THEIR trainer, then read back THEIR test metrics and checkpoint."""
    prep = prepare(dataset_id)
    name = prep["name"]
    cfg = write_config(arch, name, prep["nodes"], epochs, prep["steps_per_day"])
    ckpt_root = BTS / "checkpoints" / ARCH_CLASS[arch] / f"{name}_{epochs}_{IN_LEN}_{OUT_LEN}"
    if ckpt_root.exists():
        shutil.rmtree(ckpt_root)                        # a fresh run, not a resume of an old one
    cmd = [sys.executable, "experiments/train.py", "-c", str(cfg.relative_to(BTS)), "-g", ""]
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(cmd, cwd=BTS, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    lines, curve, epoch = [], [], 0
    for line in proc.stdout:
        lines.append(line.rstrip())
        m = LOG_EPOCH.search(line)
        if m:
            epoch = int(m.group(1))
        for kind, met, val in LOG_METRIC.findall(line):
            if met.lower() in ("loss", "mae") and kind.lower() in ("train", "val") and epoch:
                curve.append({"epoch": epoch, "kind": f"{kind.lower()}_{met.lower()}", "value": float(val)})
        if progress and (m or "test" in line.lower()):
            progress(epoch=epoch, epochs=epochs, line=line.strip()[-160:], curve=curve[-2 * epochs:])
    proc.wait()
    log_text = "\n".join(lines)
    if proc.returncode != 0:
        raise RuntimeError("their trainer failed:\n" + log_text[-1200:])
    runs = sorted(ckpt_root.glob("*/"), key=lambda p: p.stat().st_mtime)
    if not runs:
        raise RuntimeError("their trainer wrote no checkpoint directory:\n" + log_text[-800:])
    return make_card(dataset_id, arch, epochs, prep, cfg, runs[-1], log_text, where="this CPU")


def parse_test_metrics(log_text: str, run: Path) -> dict:
    """Their test table: per-horizon masked MAE / RMSE / MAPE, from test_metrics.json if the
    runner wrote one, else from the log lines it printed."""
    f = run / "test_metrics.json"
    if f.exists():
        return json.loads(f.read_text())
    out: dict = {}
    for m in re.finditer(r"Evaluate best model on test data for horizon (\d+), Test MAE: ([0-9.]+), Test MAPE: ([0-9.]+), Test RMSE: ([0-9.]+)", log_text):
        out[f"horizon_{m.group(1)}"] = {"MAE": float(m.group(2)), "MAPE": float(m.group(3)), "RMSE": float(m.group(4))}
    for m in re.finditer(r"Result <test>:.*?test/MAE: ([0-9.]+).*?test/MAPE: ([0-9.]+).*?test/RMSE: ([0-9.]+)", log_text):
        out["overall"] = {"MAE": float(m.group(1)), "MAPE": float(m.group(2)), "RMSE": float(m.group(3))}
    return out


def best_val_mae(log_text: str) -> float | None:
    """The validation MAE their runner reached at its best epoch (the checkpoint it kept)."""
    vals = [float(m.group(1)) for m in re.finditer(r"val/MAE: ([0-9.]+)", log_text)]
    return min(vals) if vals else None


def estimate_seconds(arch: str, steps: int, nodes: int, epochs: int) -> float:
    """CPU wall-clock, from measured runs on this machine (STID 30 ep x 4032 x 20 = 73 s;
    GWNet 10 ep x 864 x 12 = 28 s) — used only to decide local vs GPU, never to change a result."""
    per = {"STID": 3.0e-5, "GWNet": 2.7e-4, "STAEformer": 4.0e-4, "DCRNN": 9.0e-4}.get(arch, 3e-4)
    return 8 + per * steps * nodes * epochs


def _prepared(name: str):
    d = BTS / "datasets" / name
    desc = json.loads((d / "desc.json").read_text())
    shape = desc["shape"] if "shape" in desc else [desc["num_time_steps"], desc["num_nodes"], desc["num_features"]]
    return np.memmap(d / "data.dat", dtype="float32", mode="r", shape=tuple(shape)), desc


def persistence_floor(name: str) -> dict:
    """Persistence on THEIR test split with THEIR masking (0 = missing), per horizon 3 / 6 / 12."""
    raw, _ = _prepared(name)
    T = raw.shape[0]
    n_train = int(T * 0.7); test_lo = n_train + int(T * 0.1)
    y = np.asarray(raw[:, :, 0])
    out = {}
    for h in (3, 6, 12):
        t = np.arange(test_lo + IN_LEN, T - h)
        if len(t) == 0:
            continue
        last, fut = y[t - 1], y[t + h - 1]
        m = (fut != 0) & (last != 0)
        out[f"horizon_{h}"] = {"MAE": float(np.abs(last[m] - fut[m]).mean()) if m.any() else None}
    return out


def load_model(card: dict):
    from pipeline.forecasting.infer_from_checkpoint import load_official_cfg
    import torch
    cfg, _ = load_official_cfg(ARCHS[card["arch"]], card["bts_name"])
    model = cfg.MODEL.ARCH(**cfg.MODEL.PARAM)
    fwd = list(cfg.MODEL.get("FORWARD_FEATURES", [0]))
    model.eval()                                          # inference mode BEFORE any forward (DCRNN's decoder reads labels only when training)
    if cfg.MODEL.get("SETUP_GRAPH"):                      # DCRNN creates its parameters on the first forward
        raw, _ = _prepared(card["bts_name"])
        x = torch.zeros(1, IN_LEN, raw.shape[1], len(fwd))
        with torch.no_grad():
            model(history_data=x, future_data=None, batch_seen=0, epoch=1, train=False)
    state = torch.load(card["checkpoint"], map_location="cpu", weights_only=False)
    missing, unexpected = model.load_state_dict(state.get("model_state_dict", state), strict=False)
    if unexpected or (missing and len(missing) > 2):
        raise RuntimeError(f"checkpoint does not fit {card['arch']}: missing {list(missing)[:3]}, unexpected {list(unexpected)[:3]}")
    model.eval()
    return model, fwd


def predict(card: dict, as_of: int, *, return_input_hash=False):
    """The trained model's next 12 steps for every node, from the 12 steps before `as_of`."""
    import torch
    raw, _ = _prepared(card["bts_name"])
    T = raw.shape[0]
    n_train = int(T * 0.7)
    mu, sd = float(raw[:n_train, :, 0].mean()), float(raw[:n_train, :, 0].std())
    as_of = max(IN_LEN, min(T, as_of))
    x = np.array(raw[as_of - IN_LEN:as_of], dtype="float32")[None]
    x[..., 0] = (x[..., 0] - mu) / sd
    model, fwd = load_model(card)
    with torch.no_grad():
        tensor = torch.tensor(x)[..., fwd]
        out = model(history_data=tensor, future_data=None, batch_seen=0, epoch=1, train=False)
        pred = (out if isinstance(out, torch.Tensor) else out["prediction"]).numpy()
    prediction = pred[0, ..., 0] * sd + mu
    if return_input_hash:
        import hashlib
        return prediction, hashlib.sha256(tensor.contiguous().numpy().tobytes()).hexdigest()
    return prediction                                  # (12, N)


def cards() -> list[dict]:
    out = []
    for f in sorted(CARDS.glob("*.json")) if CARDS.exists() else []:
        c = json.loads(f.read_text())
        if Path(c["checkpoint"]).exists():
            out.append(c)
    return out


def card_for(dataset_id: str, arch: str) -> dict | None:
    return next((c for c in cards() if c["dataset"] == dataset_id and c["arch"] == arch), None)


def cached(key: str) -> dict | None:
    """An identical, VALIDATED checkpoint (same data, graph, model, config, upstream) — reuse it."""
    for c in cards():
        if c.get("cache_key") == key and (c.get("verification") or {}).get("passed") and c.get("evaluation"):
            return c
    return None


def save_card(card: dict) -> None:
    from pipeline.forecasting import train_eval as te
    (CARDS / f"{card['bts_name']}__{card['arch']}.json").write_text(json.dumps(te.to_jsonable(card), indent=1))


def official_cpu_evaluation(card: dict) -> dict:
    """THEIR `experiments/evaluate.py` on this machine (CPU) for this checkpoint — the reference
    the reload must reproduce. A GPU worker's logged numbers can differ from a CPU evaluation of
    the same weights (TF32 / fused attention kernels), so the numbers the app serves are the ones
    reproducible on the device that serves them; the GPU-logged ones stay on the card."""
    cfg = BTS / f"baselines/{ARCHS[card['arch']]}/{card['bts_name']}.py"
    r = subprocess.run([sys.executable, "experiments/evaluate.py", "-cfg", str(cfg.relative_to(BTS)), "-ckpt", card["checkpoint"], "-g", "", "-d", "cpu"],
                       cwd=BTS, capture_output=True, text=True, timeout=1800)
    out = {}
    for m in re.finditer(r"Evaluate best model on test data for horizon (\d+), Test MAE: ([0-9.]+), Test MAPE: ([0-9.]+), Test RMSE: ([0-9.]+)", r.stdout + r.stderr):
        out[f"horizon_{m.group(1)}"] = {"MAE": float(m.group(2)), "MAPE": float(m.group(3)), "RMSE": float(m.group(4))}
    for m in re.finditer(r"Result <test>:.*?test/MAE: ([0-9.]+).*?test/MAPE: ([0-9.]+).*?test/RMSE: ([0-9.]+)", r.stdout + r.stderr):
        out["overall"] = {"MAE": float(m.group(1)), "MAPE": float(m.group(2)), "RMSE": float(m.group(3))}
    if not out:
        raise RuntimeError("their evaluate.py produced no test metrics:\n" + (r.stderr or r.stdout)[-600:])
    return out


def verify_checkpoint(card: dict) -> dict:
    """Reload the checkpoint and recompute the test MAE on every test window; it must reproduce
    THEIR evaluation of the same checkpoint on this device (evaluate.py, CPU) within VERIFY_TOL,
    or the checkpoint is not the model that was scored. The training run's logged numbers are
    compared too and any device gap is recorded."""
    import torch
    from pipeline.forecasting import train_eval as te
    raw, _ = _prepared(card["bts_name"])
    T = raw.shape[0]
    sp = te.splits(T)
    n_train = sp["train"][1]
    mu, sd = float(raw[:n_train, :, 0].mean()), float(raw[:n_train, :, 0].std())
    model, fwd = load_model(card)
    t = te.windows(*sp["test"])
    y = np.asarray(raw[:, :, 0])
    errs = {h: [] for h in te.HORIZONS}
    with torch.no_grad():
        for lo in range(0, len(t), 64):
            tt = t[lo:lo + 64]
            x = np.stack([np.array(raw[i - te.IN_LEN:i], dtype="float32") for i in tt])
            x[..., 0] = (x[..., 0] - mu) / sd
            out = model(history_data=torch.tensor(x)[..., fwd], future_data=None, batch_seen=0, epoch=1, train=False)
            pred = (out if isinstance(out, torch.Tensor) else out["prediction"]).numpy()[..., 0] * sd + mu
            for h in te.HORIZONS:
                fut = np.stack([y[i + h - 1] for i in tt]); p = pred[:, h - 1]
                m = fut != 0
                errs[h].append(np.abs(p[m] - fut[m]))
    rec = {f"horizon_{h}": float(np.concatenate(errs[h]).mean()) for h in te.HORIZONS}
    logged = {k: (v or {}).get("MAE") for k, v in (card.get("test_metrics_logged") or card.get("test_metrics") or {}).items() if k.startswith("horizon_")}
    official = official_cpu_evaluation(card)
    ref = {k: official[k]["MAE"] for k in rec if k in official}
    diffs = {k: (abs(rec[k] - ref[k]) / ref[k] if ref.get(k) else None) for k in rec}
    ok = all(d is not None and d <= te.VERIFY_TOL for d in diffs.values())
    device_gap = {k: (abs(logged[k] - ref[k]) / ref[k] if logged.get(k) and ref.get(k) else None) for k in rec}
    if any(d is not None and d > te.VERIFY_TOL for d in device_gap.values()):
        # the app serves what is reproducible here: their CPU evaluation becomes the card's test table
        card.setdefault("test_metrics_logged", card.get("test_metrics"))
        card["test_metrics"] = official
        card["test_metrics_note"] = "re-evaluated on CPU by their evaluate.py; the GPU worker's logged numbers (test_metrics_logged) differ by device numerics"
    return {"passed": ok, "tolerance": te.VERIFY_TOL, "recomputed_MAE": rec, "reported_MAE": ref, "logged_MAE": logged,
            "relative_difference": {k: (None if d is None else round(d, 4)) for k, d in diffs.items()},
            "device_gap_logged_vs_cpu": {k: (None if d is None else round(d, 4)) for k, d in device_gap.items()},
            "reference": "their experiments/evaluate.py on CPU", "windows": int(len(t)), "checkpoint": Path(card["checkpoint"]).name}


def evaluate(card: dict, chronos: bool = True) -> dict:
    """Validation- and test-split metrics for the trained model and the untrained baselines, on
    the prepared data; selection by VALIDATION only; the test table reported once."""
    from pipeline.forecasting import train_eval as te
    raw, desc = _prepared(card["bts_name"])
    vals = np.asarray(raw[:, :, 0], dtype="float64")
    T, N = vals.shape
    sp = te.splits(T)
    spd = int(round(86400 / card["interval_s"]))
    speed_like = any(k in (card.get("quantity") or "").lower() for k in ("speed", "km/h", "mph"))
    ff = te.freeflow_from_train(vals, sp["train"][1]) if speed_like else None
    ha = te.historical_average(vals, sp["train"][1], spd)
    tables = {}
    for split in ("val", "test"):
        t = te.windows(*sp[split])
        per = te.score(te.predict_persistence(vals, t), vals, t, ff)
        tab = {"persistence": per, "historical_average": te.score(te.predict_ha(ha, t, spd), vals, t, ff)}
        if chronos:
            try:
                cp, ts = te.predict_chronos(vals, t, card["interval_s"], card.get("quantity") or "", card["node_names"])
                finite = float(np.isfinite(cp).mean())
                if finite < 0.5:                        # the model did not answer: say so, never score zeros
                    tab["Chronos-Bolt"] = {"error": f"Chronos returned no forecast for {1 - finite:.0%} of the sampled windows: "
                                                    f"{te.predict_chronos.last_reason or 'unknown reason'}"}
                else:
                    tab["Chronos-Bolt"] = te.score(cp, vals, ts, ff)          # non-finite entries are masked out
                    tab["Chronos-Bolt"]["sampled_windows"] = int(len(ts)); tab["Chronos-Bolt"]["finite_fraction"] = round(finite, 3)
            except Exception as exc:                    # noqa: BLE001 — a missing model is reported, not fatal
                tab["Chronos-Bolt"] = {"error": str(exc)[:200]}
        # the trained model: on test their runner's numbers (+ our F1 / RMSE via the reload), on val its best epoch
        if split == "test":
            mine = model_test_table(card, vals, sp, ff)
        else:
            mine = {"overall": {"MAE": card.get("best_val_MAE")}}
        tab[card["arch"]] = mine
        for name, tb in tab.items():
            if "error" not in tb:
                te.with_skill(tb, per)
        tables[split] = tab
    # SELECTION on validation only, by overall MAE
    cands = {k: (v.get("overall") or {}).get("MAE") for k, v in tables["val"].items() if "error" not in v}
    cands = {k: v for k, v in cands.items() if v is not None}
    selected = min(cands, key=cands.get) if cands else card["arch"]
    return te.to_jsonable({"split_rule": "chronological 70/10/20, never shuffled", "validation": tables["val"], "test": tables["test"],
                           "selected_by_validation": selected, "validation_MAE": cands,
                           "congestion_rule": "congested = below 60 % of the road's free-flow (95th percentile of its training split)" if speed_like else None,
                           "chronos_windows": te.CHRONOS_WINDOWS})


def model_test_table(card: dict, vals: np.ndarray, sp: dict, ff) -> dict:
    """The trained model on every test window through the reloaded checkpoint (RMSE / MAPE / F1
    included), beside the runner's own reported MAE."""
    import torch
    from pipeline.forecasting import train_eval as te
    raw, _ = _prepared(card["bts_name"])
    n_train = sp["train"][1]
    mu, sd = float(raw[:n_train, :, 0].mean()), float(raw[:n_train, :, 0].std())
    model, fwd = load_model(card)
    t = te.windows(*sp["test"])
    preds = []
    with torch.no_grad():
        for lo in range(0, len(t), 64):
            tt = t[lo:lo + 64]
            x = np.stack([np.array(raw[i - te.IN_LEN:i], dtype="float32") for i in tt])
            x[..., 0] = (x[..., 0] - mu) / sd
            out = model(history_data=torch.tensor(x)[..., fwd], future_data=None, batch_seen=0, epoch=1, train=False)
            preds.append((out if isinstance(out, torch.Tensor) else out["prediction"]).numpy()[..., 0] * sd + mu)
    tab = te.score(np.concatenate(preds), vals, t, ff)
    for k, v in (card.get("test_metrics") or {}).items():
        if k in tab and v.get("MAE") is not None:
            tab[k]["reported_MAE"] = v["MAE"]
    return tab


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="user:test_town")
    p.add_argument("--arch", choices=list(ARCHS), default="STID")
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--list", action="store_true")
    a = p.parse_args()
    if a.list:
        for c in cards():
            print(f"{c['dataset']:<28} {c['arch']:<6} epochs {c['epochs']:<4} test {json.dumps(c['test_metrics'].get('overall'))}")
        return 0
    card = train(a.dataset, a.arch, a.epochs, progress=lambda **k: print(f"  epoch {k['epoch']}/{k['epochs']}  {k['line']}"))
    print(json.dumps({k: card[k] for k in ("dataset", "arch", "epochs", "test_metrics", "persistence_test", "checkpoint")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
