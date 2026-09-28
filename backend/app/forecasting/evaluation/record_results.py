#!/usr/bin/env python3
"""Turn training logs into a machine-readable, fully-provenanced result record.

    python -m app.forecasting.evaluation.record_results --logs results/forecasting/aws_logs
    python -m app.forecasting.evaluation.record_results --logs results/forecasting/aws_logs --csv

Markdown is for reading; this file is for checking. Every trained number is written to JSON and CSV
together with everything needed to re-run it and to judge it:

    dataset, upstream repository + exact SHA, BasicTS SHA, config path, epochs, hardware,
    MAE / RMSE / MAPE at 5 / 15 / 30 / 60 min, the published value, and the percentage difference.

MAPE unit: the BasicTS-legacy harness logs MAPE as a FRACTION (`Test MAPE: 0.0702` = 7.02 %). It is
converted here once, explicitly, rather than by guessing from magnitude — a heuristic would break on
PEMS-BAY, where a true MAPE of 2.73 % and a fraction of 0.0273 are both plausible-looking numbers.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.paths import REPO
RESULTS = REPO / "results/forecasting"

# The harness logs MAPE as a fraction of 1. Documented, not inferred.
MAPE_IS_FRACTION = True

UPSTREAM = {
    "harness": {"name": "BasicTS (legacy fair-comparison branch)",
                "repo": "https://github.com/GestaltCogTeam/BasicTS",
                "sha": "4c3e2d373c647667c2123e1591f2d79c229dfcc6",
                "paper": "Shao et al., Exploring Progress in Multivariate Time Series Forecasting, TKDE 2024"},
    "models": {
        "GWNet": {"name": "Graph WaveNet", "paper": "Wu et al., IJCAI 2019",
                  "repo": "https://github.com/nnzhan/Graph-WaveNet",
                  "config": "baselines/GWNet/{dataset}.py (official, unmodified except epochs/horizons)"},
        "STID": {"name": "STID", "paper": "Shao et al., CIKM 2022",
                 "repo": "https://github.com/GestaltCogTeam/STID",
                 "config": "baselines/STID/{dataset}.py (official, unmodified except epochs/horizons)"},
        "DCRNN": {"name": "DCRNN", "paper": "Li et al., ICLR 2018",
                  "repo": "https://github.com/liyaguang/DCRNN",
                  "config": "baselines/DCRNN/{dataset}.py"},
        "STAEformer": {"name": "STAEformer", "paper": "Liu et al., CIKM 2023",
                       "repo": "https://github.com/XDZhelheim/STAEformer",
                       "config": "baselines/STAEformer/{dataset}.py"},
    },
    "datasets": {
        "METR-LA": {"sensors": 207, "bin_minutes": 5, "source": "DCRNN release (Li et al., ICLR 2018)",
                    "note": "real loop detectors, Los Angeles"},
        "PEMS-BAY": {"sensors": 325, "bin_minutes": 5, "source": "DCRNN release (Li et al., ICLR 2018)",
                     "note": "real loop detectors, Bay Area"},
    },
}

# Published MAE / RMSE / MAPE% at 15 / 30 / 60 min.
PUBLISHED = {
    ("GWNet", "METR-LA"): {15: (2.69, 5.15, 6.90), 30: (3.07, 6.22, 8.37), 60: (3.53, 7.37, 10.01)},
    ("DCRNN", "METR-LA"): {15: (2.77, 5.38, 7.30), 30: (3.15, 6.45, 8.80), 60: (3.60, 7.60, 10.50)},
    ("GWNet", "PEMS-BAY"): {15: (1.30, 2.74, 2.73), 30: (1.63, 3.70, 3.67), 60: (1.95, 4.52, 4.63)},
    ("DCRNN", "PEMS-BAY"): {15: (1.38, 2.95, 2.90), 30: (1.74, 3.97, 3.90), 60: (2.07, 4.74, 4.90)},
}

def rel(p: Path) -> str:
    """Repo-relative when inside the repo, absolute otherwise (logs may live anywhere)."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


RE_EVAL = re.compile(r"horizon\s+(\d+),\s*Test MAE:\s*([\d.]+),\s*Test MAPE:\s*([\d.]+),\s*Test RMSE:\s*([\d.]+)")
RE_EPOCHS = re.compile(r"NUM_EPOCHS[:=]\s*(\d+)")          # the harness logs "NUM_EPOCHS: 50"
RE_EPOCH_RUN = re.compile(r"Epoch\s+(\d+)\s*/\s*(\d+)")   # and progress as "Epoch 50 / 50"
RE_GPU = re.compile(r"(NVIDIA [A-Za-z0-9 ]+|Tesla [A-Z0-9]+|A10G|T4|A100)")
RE_CKPT = re.compile(r"Loading Checkpoint from '([^']+)'")


def parse_log(path: Path, hardware: dict) -> dict | None:
    stem = path.stem
    if "_" not in stem:
        return None
    model, dataset = stem.split("_", 1)
    txt = path.read_text(errors="ignore")
    if not RE_EVAL.search(txt):
        return None
    bins = UPSTREAM["datasets"].get(dataset, {}).get("bin_minutes", 5)
    per_h = {}
    for h, mae, mape, rmse in RE_EVAL.findall(txt):          # last block = best-model evaluation
        per_h[int(h)] = {"mae": float(mae), "rmse": float(rmse),
                         "mape_pct": float(mape) * (100.0 if MAPE_IS_FRACTION else 1.0)}
    ep = RE_EPOCHS.findall(txt)
    runs = RE_EPOCH_RUN.findall(txt)
    epochs_configured = int(ep[-1]) if ep else (int(runs[-1][1]) if runs else None)
    epochs_completed = int(runs[-1][0]) if runs else None
    ck = RE_CKPT.findall(txt)
    rows = {}
    for h, v in sorted(per_h.items()):
        minutes = h * bins
        pub = PUBLISHED.get((model, dataset), {}).get(minutes)
        row = dict(v)
        row["horizon_steps"] = h
        row["horizon_minutes"] = minutes
        if pub:
            row |= {"published_mae": pub[0], "published_rmse": pub[1], "published_mape_pct": pub[2],
                    "mae_diff_pct": round(100 * (v["mae"] / pub[0] - 1), 2),
                    "rmse_diff_pct": round(100 * (v["rmse"] / pub[1] - 1), 2),
                    "mape_diff_pct": round(100 * (v["mape_pct"] / pub[2] - 1), 2)}
        rows[minutes] = row
    return {
        "model": model, "model_info": UPSTREAM["models"].get(model, {}),
        "dataset": dataset, "dataset_info": UPSTREAM["datasets"].get(dataset, {}),
        "harness": UPSTREAM["harness"],
        "config": UPSTREAM["models"].get(model, {}).get("config", "").format(dataset=dataset),
        "epochs": epochs_configured, "epochs_completed": epochs_completed,
        "checkpoint": ck[-1] if ck else None,
        "hardware": hardware,
        "mape_unit_note": "harness logs MAPE as a fraction; converted to percent here",
        "log": rel(path),
        "metrics_by_horizon_min": rows,
    }


def hardware_from(logs: Path, dataset: str) -> dict:
    hw = {"provider": "AWS EC2", "instance_type": None, "gpu": None, "region": None}
    # match the run that actually trained THIS dataset, not merely the most recent launch
    hist = RESULTS / "aws_jobs.jsonl"
    jobs = [json.loads(l) for l in hist.read_text().splitlines() if l.strip()] if hist.exists() else []
    j = next((x for x in reversed(jobs) if dataset in str(x.get("datasets", ""))), None)
    if j is None and (RESULTS / "aws_job.json").exists():
        j = json.loads((RESULTS / "aws_job.json").read_text())
    if j:
        hw |= {"instance_type": j.get("type"), "region": j.get("region"), "ami": j.get("ami"),
               "instance_id": j.get("instance"), "launched_utc": j.get("launched_utc"),
               "matched_by": "dataset"}
    main = logs / "dhakaflow.log"
    if main.exists():
        m = RE_GPU.search(main.read_text(errors="ignore")[:400000])
        if m:
            hw["gpu"] = m.group(1).strip()
    return hw


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--logs", type=Path, default=RESULTS / "aws_logs")
    p.add_argument("--out", type=Path, default=RESULTS / "trained_results")
    a = p.parse_args()
    if not a.logs.exists():
        print(f"no logs at {a.logs} — run src/pipeline/forecasting/aws_train.py --collect first")
        return 1
    recs = []
    for f in sorted(a.logs.glob("*.log")):
        ds = f.stem.split("_", 1)[1] if "_" in f.stem else ""
        r = parse_log(f, hardware_from(a.logs, ds))
        if r:
            recs.append(r)
    if not recs:
        print(f"no parseable training logs in {a.logs}")
        return 1
    git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                         cwd=REPO).stdout.strip()
    doc = {"generated_utc": datetime.now(timezone.utc).isoformat(), "repo_git_sha": git,
           "reality": "REAL public benchmark datasets; official upstream configs; GPU-trained",
           "runs": recs}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.with_suffix(".json").write_text(json.dumps(doc, indent=1))

    fields = ["model", "dataset", "horizon_minutes", "mae", "rmse", "mape_pct",
              "published_mae", "published_rmse", "published_mape_pct",
              "mae_diff_pct", "rmse_diff_pct", "mape_diff_pct",
              "epochs", "instance_type", "gpu", "harness_sha", "config", "log"]
    with open(a.out.with_suffix(".csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in recs:
            for _, row in sorted(r["metrics_by_horizon_min"].items()):
                w.writerow({"model": r["model"], "dataset": r["dataset"],
                            "epochs": r["epochs"], "instance_type": r["hardware"].get("instance_type"),
                            "gpu": r["hardware"].get("gpu"), "harness_sha": r["harness"]["sha"],
                            "config": r["config"], "log": r["log"],
                            **{k: row.get(k) for k in fields if k in row}})
    print(f"wrote {a.out.with_suffix('.json')}\nwrote {a.out.with_suffix('.csv')}")
    for r in recs:
        hs = sorted(r["metrics_by_horizon_min"])
        print(f"  {r['model']:<6} {r['dataset']:<9} epochs={r['epochs_completed']}/{r['epochs']} horizons={hs} "
              f"ckpt={'yes' if r['checkpoint'] else 'NO'}")
        for mnt in hs:
            row = r["metrics_by_horizon_min"][mnt]
            pub = f" vs published {row['published_mae']} ({row['mae_diff_pct']:+.1f} %)" if "published_mae" in row else ""
            print(f"      {mnt:>3} min  MAE {row['mae']:.3f}  RMSE {row['rmse']:.3f}  "
                  f"MAPE {row['mape_pct']:.2f} %{pub}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
