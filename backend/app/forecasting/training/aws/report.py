"""The benchmark table: our trained baselines next to the published numbers, so the reproduction
quality is visible in the same row."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .settings import RESULTS

# Published MAE / MAPE for the official configs.
PUB = {("GWNet", "METR-LA", 15): (2.69, 6.90), ("GWNet", "METR-LA", 30): (3.07, 8.37), ("GWNet", "METR-LA", 60): (3.53, 10.01),
       ("GWNet", "PEMS-BAY", 15): (1.30, 2.73), ("GWNet", "PEMS-BAY", 30): (1.63, 3.67), ("GWNet", "PEMS-BAY", 60): (1.95, 4.63),
       ("DCRNN", "METR-LA", 15): (2.77, 7.30), ("DCRNN", "METR-LA", 30): (3.15, 8.80), ("DCRNN", "METR-LA", 60): (3.60, 10.50)}
_LINE = re.compile(r"horizon\s+(\d+),\s*Test MAE:\s*([\d.]+),\s*Test MAPE:\s*([\d.]+),\s*Test RMSE:\s*([\d.]+)")


def parse_logs(dst: Path) -> list[dict]:
    """One row per (model, dataset, horizon) from the training logs the job uploaded."""
    rows = []
    for log in sorted(dst.glob("*.log")):
        if "_" not in log.stem:
            continue
        model, dataset = log.stem.split("_", 1)
        best = {}
        for h, mae, mape, rmse in _LINE.findall(log.read_text(errors="ignore")):
            best[int(h)] = {"mae": float(mae), "mape": float(mape), "rmse": float(rmse)}
        for h, v in sorted(best.items()):
            v["mape"] = v["mape"] * 100 if v["mape"] < 1.5 else v["mape"]   # BasicTS logs MAPE as a FRACTION; report percent, as the papers do
            rows.append({"model": model, "dataset": dataset, "horizon_min": h * 5, **v})
    return rows


def write_benchmark(rows: list[dict]) -> str:
    lines = ["# Trained baselines on real cities (AWS GPU, official BasicTS configs, unmodified)\n",
             "`ours` vs `published` is the reproduction check: the evaluation protocol was validated "
             "independently first (see benchmark_floors.md, our HA floor matches DCRNN's to 0.7 %), so a "
             "close match here means the training pipeline is correct too.\n",
             "| model | dataset | horizon | MAE | published MAE | diff | RMSE | MAPE % | published MAPE % |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        pub = PUB.get((r["model"], r["dataset"], r["horizon_min"]))
        pm = f"{pub[0]:.2f}" if pub else "–"
        diff = f"{100 * (r['mae'] / pub[0] - 1):+.1f} %" if pub else "–"
        pmape = f"{pub[1]:.2f}" if pub else "–"
        lines.append(f"| {r['model']} | {r['dataset']} | {r['horizon_min']} min | {r['mae']:.3f} | {pm} | {diff} | {r['rmse']:.3f} | {r['mape']:.2f} | {pmape} |")
    lines += ["", "Compare against `results/forecasting/benchmark_floors.md` (the floors these must beat) and the published numbers cited there.", "",
              "Regenerate: `python -m app.forecasting.training.aws_train --launch` then `--collect`."]
    text = "\n".join(lines) + "\n"
    (RESULTS / "benchmark.md").write_text(text)
    (RESULTS / "benchmark.json").write_text(json.dumps(rows, indent=1))
    return text
