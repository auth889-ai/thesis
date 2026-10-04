"""PatchSTG (Fang et al., KDD 2025) on LargeST, through the authors' own code — test and train.

    python -m app.forecasting.training.patchstg_official --region SD                 # released weights, test only
    python -m app.forecasting.training.patchstg_official --region SD --mode train    # the authors' recipe, then test

The official repository (LMissher/PatchSTG, MIT, pinned in upstream/UPSTREAM_PINS.yaml) is cloned into the
external workspace and used UNCHANGED: `main.py` keeps its `train(); test()` entrypoint, whose README says to edit
line 262 to switch modes. This module is the switch instead. It imports the authors' `Solver`, hands it the same
keyword dictionary their argparse block builds from `config/<REGION>.conf`, and calls `test()` or `train()` on it.
Nothing about the model, the loader, the spatial patching or the metric is touched; the `metric` printed per step
is theirs, with MAPE as a fraction (their table multiplies by 100).

Data and weights come from the authors' Google Drive folders (`PatchSTG_data/{data,cpt}` in the workspace); the
region's `flow<region>.npz` and `adj.npy` are linked into the repo's `data/<REGION>/` beside the committed meta csv,
and `cpt/` is linked whole, so the config's relative paths resolve exactly as the authors wrote them.

On a rented machine training is resumable (`--resume <file>`, `--on-epoch <command>`): see patchstg_resume.py, which
calls the authors' `train()` one epoch at a time and writes a state file after each.

Each run writes one record to results/forecasting/patchstg_largest.json keyed `<region>|<mode>` with the per-step and
12-step-average MAE / RMSE / MAPE beside the published Table 3 average, and refreshes patchstg_largest.md.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path.home() / ".dhakaflow/upstream/PatchSTG"
DATA = Path.home() / ".dhakaflow/upstream/PatchSTG_data"
OUT = Path(__file__).resolve().parents[4] / "results/forecasting"
REGIONS = {"SD": 716, "GBA": 2352, "GLA": 3834, "CA": 8600}
PUBLISHED = {  # paper Table 3, 12-step average (MAE, RMSE, MAPE %)
    "SD": (16.90, 29.27, 11.23), "GBA": (19.50, 33.16, 14.64), "GLA": (18.96, 32.33, 11.44), "CA": (17.35, 29.79, 12.79)}

# the authors' argparse block, name for name: (section, key, type) -> Solver attribute
_ARGS = {"cuda": ("train", "cuda", str), "seed": ("train", "seed", int), "batch_size": ("train", "batch_size", int),
         "max_epoch": ("train", "max_epoch", int), "learning_rate": ("train", "learning_rate", float),
         "weight_decay": ("train", "weight_decay", float),
         "input_len": ("data", "input_len", int), "output_len": ("data", "output_len", int),
         "train_ratio": ("data", "train_ratio", float), "val_ratio": ("data", "val_ratio", float), "test_ratio": ("data", "test_ratio", float),
         "layers": ("param", "layers", int), "tem_patchsize": ("param", "tps", int), "tem_patchnum": ("param", "tpn", int),
         "factors": ("param", "factors", int), "recur_times": ("param", "recur", int), "spa_patchsize": ("param", "sps", int),
         "spa_patchnum": ("param", "spn", int), "node_num": ("param", "nodes", int), "tod": ("param", "tod", int),
         "dow": ("param", "dow", int), "input_dims": ("param", "id", int), "node_dims": ("param", "nd", int),
         "tod_dims": ("param", "td", int), "dow_dims": ("param", "dd", int),
         "traffic_file": ("file", "traffic", str), "meta_file": ("file", "meta", str), "adj_file": ("file", "adj", str),
         "model_file": ("file", "model", str), "log_file": ("file", "log", str)}


def official_args(conf_path: Path, num_workers: int = 0) -> dict:
    """The dictionary the authors' `vars(args)` would hold for this config file."""
    cfg = configparser.ConfigParser()
    cfg.read(conf_path)
    out = {name: typ(cfg[sec][key]) for name, (sec, key, typ) in _ARGS.items()}
    out["num_workers"] = num_workers
    return out


def link_release(region: str) -> list[str]:
    """Point the repo's relative paths at the downloaded release; returns what is still missing."""
    missing = []
    src = DATA / "data" / region
    dst = REPO / "data" / region
    dst.mkdir(parents=True, exist_ok=True)
    for fname in (f"flow{region.lower()}.npz", "adj.npy"):
        d = dst / fname
        flat = DATA / "data" / (f"adj{region.lower()}.npy" if fname == "adj.npy" else fname)   # the Drive folder is flat
        s = next((c for c in (src / fname, flat) if c.exists()), None)
        if s is not None and not d.exists():
            d.symlink_to(s)
        if not d.exists() and fname.endswith(".npz"):
            missing.append(str(flat))
    cpt = REPO / "cpt"
    if not cpt.exists() and (DATA / "cpt").exists():
        cpt.symlink_to(DATA / "cpt")
    if not (cpt / f"{region.lower()}_model").exists():
        missing.append(str(DATA / "cpt" / f"{region.lower()}_model"))
    (REPO / "log").mkdir(exist_ok=True)
    return missing


def run(region: str, mode: str = "test", device: str = "cpu", epochs: int | None = None, workers: int = 0,
        resume: str | None = None, on_epoch: str | None = None) -> dict:
    region = region.upper()
    if region not in REGIONS:
        raise SystemExit(f"region must be one of {sorted(REGIONS)}")
    missing = link_release(region)
    if missing and mode == "test":
        raise SystemExit("released files not present yet: " + ", ".join(missing))
    import torch
    os.chdir(REPO)                                   # the config's paths are relative to the repo, as the authors run it
    sys.path.insert(0, str(REPO))
    import main as official                          # the authors' module; its __main__ block does not run on import

    args = official_args(REPO / "config" / f"{region}.conf", workers)
    if epochs:
        args["max_epoch"] = epochs
    if torch.cuda.is_available() and int(args["cuda"]) >= torch.cuda.device_count():
        args["cuda"] = "0"                           # GBA/GLA/CA configs name GPU 7/4/6 of the authors' own machine
    (OUT / "patchstg_logs").mkdir(parents=True, exist_ok=True)
    args["log_file"] = str(OUT / "patchstg_logs" / f"{region}_{mode}.log")    # ours, so the authors' committed log/ stays untouched
    official.log = open(args["log_file"], "a")
    official.random.seed(args["seed"]); official.np.random.seed(args["seed"]); torch.manual_seed(args["seed"])
    t0 = time.time()
    solver = official.Solver(args)
    if device != "cpu" and not torch.cuda.is_available():          # their Solver only knows cuda-or-cpu; MPS is ours to ask for
        solver.device = torch.device(device)
        solver.model.to(solver.device)
    progress = None
    if mode == "train" and resume:
        sys.path.insert(0, str(Path(__file__).parent))            # on a rented machine the two files sit side by side, outside the package
        from patchstg_resume import resumable_epochs
        progress = resumable_epochs(solver, args["max_epoch"], resume, on_epoch, say=lambda m: official.log_string(official.log, m))
    elif mode == "train":
        solver.train()
    maes, rmses, mapes = solver.test()
    steps = [{"step": i + 1, "mae": round(float(maes[i]), 4), "rmse": round(float(rmses[i]), 4), "mape_pct": round(float(mapes[i]) * 100, 4)}
             for i in range(len(maes) - 1)]
    pub = PUBLISHED[region]
    rec = {"region": region, "mode": mode, "nodes": REGIONS[region], "device": device, "seconds": round(time.time() - t0, 1),
           "generated_utc": datetime.now(timezone.utc).isoformat(), "epochs": args["max_epoch"] if mode == "train" else 0,
           "weights": "authors' released checkpoint" if mode == "test" else "trained here with the authors' recipe",
           "average": {"mae": round(float(maes[-1]), 4), "rmse": round(float(rmses[-1]), 4), "mape_pct": round(float(mapes[-1]) * 100, 4)},
           "published": {"mae": pub[0], "rmse": pub[1], "mape_pct": pub[2]}, "steps": steps,
           "upstream": "LMissher/PatchSTG (MIT), main.py Solver used as released"}
    rec["mae_gap_pct"] = round((rec["average"]["mae"] - pub[0]) / pub[0] * 100, 2)
    if progress:
        rec["best_epoch"], rec["resumes"] = progress["best_epoch"], progress["resumes"]
    write(rec)
    return rec


def write(rec: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "patchstg_largest.json"
    prior = json.loads(path.read_text()) if path.exists() else []
    by = {f"{r['region']}|{r['mode']}": r for r in prior}
    by[f"{rec['region']}|{rec['mode']}"] = rec
    rows = sorted(by.values(), key=lambda r: (list(REGIONS).index(r["region"]), r["mode"]))
    path.write_text(json.dumps(rows, indent=1))
    L = ["# PatchSTG on LargeST — the authors' code, their split (6/2/2), their metric, 12-step average\n",
         "| region | sensors | weights | MAE | RMSE | MAPE % | published MAE / RMSE / MAPE % | MAE gap | device | time |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        a, p = r["average"], r["published"]
        L.append(f"| {r['region']} | {r['nodes']} | {r['weights']} | {a['mae']} | {a['rmse']} | {a['mape_pct']} | "
                 f"{p['mae']} / {p['rmse']} / {p['mape_pct']} | {r['mae_gap_pct']:+.2f} % | {r['device']} | {r['seconds']} s |")
    L.append("\nRegenerate: `python -m app.forecasting.training.patchstg_official --region <SD|GBA|GLA|CA> [--mode train]`.\n")
    (OUT / "patchstg_largest.md").write_text("\n".join(L))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--region", default="SD")
    p.add_argument("--mode", choices=("test", "train"), default="test")
    p.add_argument("--device", default="cpu", help="cpu or cuda (cuda is picked by the authors' code when present; MPS rejects their float64 stamps)")
    p.add_argument("--epochs", type=int, default=None, help="train mode only; default is the authors' config")
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--resume", default=None, help="train mode: state file written after every epoch and continued from when present")
    p.add_argument("--on-epoch", default=None, help="train mode with --resume: shell command run after each epoch's state file is written")
    a = p.parse_args()
    rec = run(a.region, a.mode, a.device, a.epochs, a.workers, a.resume, a.on_epoch)
    avg, pub = rec["average"], rec["published"]
    print(f"{rec['region']} {rec['mode']}: MAE {avg['mae']} RMSE {avg['rmse']} MAPE {avg['mape_pct']} %  "
          f"(published {pub['mae']} / {pub['rmse']} / {pub['mape_pct']} %, gap {rec['mae_gap_pct']:+.2f} %)  wrote {OUT / 'patchstg_largest.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
