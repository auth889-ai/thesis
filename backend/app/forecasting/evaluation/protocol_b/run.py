"""Evaluate one dataset under Protocol B end to end, and the command line.

    python -m app.forecasting.evaluation.evaluate_models --dataset METR-LA --windows 120 --seed 11 --max-nodes 0
    python -m app.forecasting.evaluation.evaluate_models --all
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import records
from .data import free_flow, load, splits, subsample
from .scoring import onset_lead, score
from .settings import BIN_MIN, CONGESTION_RATIO, CONTEXT, HORIZONS_MIN, OUT, STEPS
from app.paths import REPO
from .stages import stage

STAGE_MODULE = "app.forecasting.evaluation.protocol_b.run"


def evaluate(dataset: str, n_windows: int, seed: int, chronos_model: str, skip_chronos: bool = False,
             max_nodes: int = 0, region: str = "test", zero_shot: str = "chronos,chronos2,timesfm") -> dict:
    data = subsample(load(dataset), max_nodes)
    T, N = data.shape
    tr_end, _ = splits(T)
    thr = CONGESTION_RATIO * free_flow(data[:tr_end])

    from app.forecasting.evaluation.checkpoint_stage import checkpoints_for
    zs = [] if skip_chronos else [k.strip() for k in zero_shot.split(",") if k.strip()]
    kinds = ["baselines", "trees"] + zs + (["checkpoints"] if checkpoints_for(dataset) else [])
    preds, truth, starts, timings = {}, None, None, {}
    with tempfile.TemporaryDirectory() as td:
        for kind in kinds:
            f = Path(td) / f"{kind}.npz"
            t0 = time.time()
            print(f"  [{kind}] …", flush=True)
            subprocess.run([sys.executable, "-m", STAGE_MODULE, "--stage", kind, "--dataset", dataset, "--windows", str(n_windows),
                            "--seed", str(seed), "--chronos-model", chronos_model, "--max-nodes", str(max_nodes),
                            "--region", region, "--stage-out", str(f)], check=True)
            timings[kind] = round(time.time() - t0, 1)
            z = np.load(f)
            truth = z["truth"] if truth is None else truth
            starts = z["starts"]
            preds.update({k[5:]: z[k] for k in z.files if k.startswith("pred_")})

    records.persist_block(dataset, region, n_windows, N, seed, truth, starts, thr, preds)
    results = {name: {"horizons": score(p, truth, thr), "onset_lead": onset_lead(p, truth, thr)} for name, p in preds.items()}
    return {
        "dataset": dataset, "generated_utc": datetime.now(timezone.utc).isoformat(),
        "protocol": {
            "windows": int(len(starts)), "context_steps": CONTEXT, "nodes_scored": int(N),
            "horizons_min": list(HORIZONS_MIN), "bin_min": BIN_MIN,
            "split": "chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real",
            "congestion_threshold": f"{CONGESTION_RATIO} x per-node free-flow (85th percentile of that node's TRAIN-split observed values)",
            "missing": "values of 0.0 are sensor outages and are excluded from every metric",
            "trees_trained_on": "TRAIN split only", "seed": seed, "stage_seconds": timings,
            "isolation": "each model family runs in its own process: torch and the tree libraries deadlock when they share an interpreter",
            "not_compared_with": "OpenCity — it is scored on a 288-step horizon under its authors' split; mixing protocols would be meaningless",
        },
        "nodes": int(N), "timesteps": int(T), "results": results,
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="METR-LA")
    p.add_argument("--all", action="store_true")
    p.add_argument("--windows", type=int, default=200)
    p.add_argument("--seed", type=int, default=11, help="which contiguous block of the real test region is scored")
    p.add_argument("--chronos-model", default="amazon/chronos-bolt-small")
    p.add_argument("--skip-chronos", action="store_true")
    p.add_argument("--stage", default="", help="internal: run one model family")
    p.add_argument("--stage-out", type=Path, default=None)
    p.add_argument("--max-nodes", type=int, default=0, help="deterministic road subsample; 0 uses every road")
    p.add_argument("--region", default="test", choices=["test", "val"], help="score the test block (the comparison) or the validation block (conformal calibration)")
    p.add_argument("--zero-shot", default="chronos,chronos2,timesfm", help="which zero-shot families to run (comma list of chronos, chronos2, timesfm)")
    p.add_argument("--merge", type=Path, nargs="*", default=None, help="staged prediction files (--stage ... --stage-out) to add to the persisted block, then re-score")
    return p


def _print_rows(results: dict) -> None:
    for name, res in sorted(results.items()):
        h = res["horizons"].get(15, {})
        print(f"   {name:<20} MAE@15={h.get('mae'):<8} congMAE={h.get('congestion_mae')} F1={h.get('congestion_f1')} onset={res['onset_lead'].get('detection_rate')}")


def main(argv: list[str] | None = None) -> int:
    a = parser().parse_args(argv)
    if a.merge:
        rec = records.merge(a.dataset, a.region, a.windows, a.max_nodes, a.seed, a.merge)
        if rec:
            _print_rows(rec["results"]); records.write([rec])
        print(f"merged into the {a.region} block of {a.dataset}")
        return 0
    if a.stage:
        stage(a.stage, a.dataset, a.windows, a.seed, a.chronos_model, a.max_nodes, a.stage_out, a.region)
        return 0
    out = []
    for ds in (["METR-LA", "PEMS-BAY", "PEMS07M"] if a.all else [a.dataset]):
        print(f"[eval] {ds} …", flush=True)
        r = evaluate(ds, a.windows, a.seed, a.chronos_model, a.skip_chronos, a.max_nodes, a.region, a.zero_shot)
        _print_rows(r["results"])
        if a.region == "test":
            out.append(r)
    records.write(out)
    print(f"\nwrote {records.MARKDOWN.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
