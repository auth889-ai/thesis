#!/usr/bin/env python3
"""RETIRED — violates the project policy that all model training runs on Colab/GPU, never this machine.

Kept only for history. Use notebooks/Predict_Twin_Colab.ipynb instead.

Original docstring follows.

Train official BasicTS(-legacy) baselines on the Dhaka twin dataset — locally, on CPU.

    python predict/train_twin_local.py --models STID,GWNet
    python predict/train_twin_local.py --models AGCRN,DCRNN,STAEformer,STGCN --epochs 100

The twin dataset (predict/data/dhaka_twin, 288 x 250 x 4, label DHAKA_SIMULATED_SENSOR_GRAPH) is
small enough that the official configs train in minutes on CPU, so the Dhaka forecasting table
does not have to wait for Colab.  Nothing upstream is modified: the pinned BasicTS-legacy checkout
(~/.dhakaflow/upstream/BasicTS_legacy @4c3e2d3) is used as-is; research/forecasting/make_legacy_config.py
derives each model's DhakaR1 config from its own official PEMS04 config (dataset name + node count only),
and this script additionally sets CFG.GPU_NUM = 0 (CPU) and, if --epochs is given, the epoch count.

Per model: log -> predict/results/twin_models/<model>.log, best-model test metrics at horizons
3/6/12 (= 15/30/60 min) -> twin_models.json / twin_models.md next to the persistence / historical-
average floors, and the harness's test_results.npz (predictions + targets) -> <model>_test_results.npz
for predict/forecast_to_weights.py --source model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from research.forecasting.make_legacy_config import make, DATASET  # noqa: E402

BTS = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream")) / "BasicTS_legacy"
DATA = REPO / "predict/data/dhaka_twin/basicts_legacy"
OUT = REPO / "predict/results/twin_models"
H2MIN = {1: 5, 3: 15, 6: 30, 12: 60}
RE_EVAL = re.compile(r"horizon\s+(\d+),\s*Test MAE:\s*([\d.]+),\s*Test MAPE:\s*([\d.]+),\s*Test RMSE:\s*([\d.]+)")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def stage_dataset() -> str:
    dst = BTS / "datasets" / DATASET
    dst.mkdir(parents=True, exist_ok=True)
    for f in ("data.dat", "desc.json", "adj_mx.pkl"):
        shutil.copy2(DATA / f, dst / f)
    return sha(DATA / "data.dat")


def train(model: str, epochs: int | None) -> dict:
    cfg = make(BTS, model)
    txt = cfg.read_text()
    txt = re.sub(r"CFG\.GPU_NUM\s*=\s*\d+", "CFG.GPU_NUM = 0", txt)
    if epochs:
        txt = re.sub(r"^NUM_EPOCHS\s*=\s*\d+", f"NUM_EPOCHS = {epochs}", txt, flags=re.M)
    cfg.write_text(txt)
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / f"{model}.log"
    t0 = time.time()
    with open(log, "w") as fh:
        rc = subprocess.call([sys.executable, "experiments/train.py", "-c", str(cfg.relative_to(BTS)), "-g", "0"],
                             cwd=BTS, stdout=fh, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    text = log.read_text(errors="ignore")
    best = {}
    for h, mae, mape, rmse in RE_EVAL.findall(text):          # last occurrence per horizon = best-model evaluation
        best[int(h)] = {"mae": float(mae), "mape": float(mape), "rmse": float(rmse)}
    saved = re.findall(r"Test results saved to (\S+)", text)
    npz = None
    if saved:
        src = BTS / saved[-1].rstrip(".")
        src = src if src.exists() else (src.parent / "test_results.npz")
        if src.exists():
            npz = OUT / f"{model}_test_results.npz"
            shutil.copy2(src, npz)
    rec = {"model": model, "rc": rc, "wall_s": round(wall, 1), "config": str(cfg.relative_to(BTS)), "log": str(log.relative_to(REPO)),
           "test_results_npz": str(npz.relative_to(REPO)) if npz else None, "best_test": best, "epochs": epochs or "official"}
    print(f"[{model}] rc={rc} wall={wall:.0f}s " + " ".join(f"h{h}:MAE={m['mae']:.3f}" for h, m in sorted(best.items())), flush=True)
    return rec


def write_tables(recs: dict, data_sha: str):
    floors = json.loads((REPO / "predict/results/twin_floors.json").read_text()) if (REPO / "predict/results/twin_floors.json").exists() else {}
    lines = [f"# Dhaka twin forecasting — official BasicTS baselines trained locally on CPU\n",
             f"Dataset `predict/data/dhaka_twin` (DHAKA_SIMULATED_SENSOR_GRAPH, data.dat sha `{data_sha}`), target speed m/s, chronological 70/10/20 split, "
             f"official configs (PEMS04 template → DhakaR1, CPU), harness BasicTS-legacy @4c3e2d3, NULL_VAL=0 masking.\n",
             "| model | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 | epochs | wall s |", "|---|---|---|---|---|---|---|---|---|"]
    fl = floors.get("floors", floors) if isinstance(floors, dict) else {}
    for name in ("persistence", "historical_average"):
        row = fl.get(name) if isinstance(fl, dict) else None
        if isinstance(row, dict):
            cells = []
            for mn in (15, 30, 60):
                r = row.get(str(mn)) or row.get(f"{mn}min") or row.get(mn) or {}
                cells += [f"{r.get('mae', float('nan')):.3f}", f"{r.get('rmse', float('nan')):.3f}"]
            lines.append(f"| {name} (floor) | " + " | ".join(cells) + " | – | – |")
    for m, r in recs.items():
        b = r["best_test"]
        cells = [f"{b[h]['mae']:.3f} | {b[h]['rmse']:.3f}" if h in b else "– | –" for h in (3, 6, 12)]
        lines.append(f"| {m} | " + " | ".join(cells) + f" | {r['epochs']} | {r['wall_s']} |")
    lines += ["", "Floors from `predict/results/twin_floors.md` (same split). Predictions for every test window are in `<model>_test_results.npz`.",
              "Regenerate: `python predict/train_twin_local.py --models " + ",".join(recs) + "`."]
    (OUT / "twin_models.md").write_text("\n".join(lines) + "\n")
    (REPO / "predict/results/twin_models.md").write_text("\n".join(lines) + "\n")
    (OUT / "twin_models.json").write_text(json.dumps({"data_sha": data_sha, "models": recs}, indent=1))
    print("\n".join(lines))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="STID,GWNet")
    ap.add_argument("--epochs", type=int, default=None, help="override the official epoch count (default: official)")
    a = ap.parse_args()
    data_sha = stage_dataset()
    prev = json.loads((OUT / "twin_models.json").read_text())["models"] if (OUT / "twin_models.json").exists() else {}
    for m in a.models.split(","):
        prev[m] = train(m, a.epochs)
        write_tables(prev, data_sha)
    return 0


if __name__ == "__main__":
    sys.exit(main())
