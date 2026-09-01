#!/usr/bin/env python3
"""P1 winner triage from the official evaluator's own saved state.

The official RT-DETR `DetSolver.val()` saves `eval.pth` — the raw pycocotools
COCOeval accumulate() state — into output_dir (det_solver.py:102), which the
arm syncs to S3. Per-class AP therefore comes from the OFFICIAL evaluation,
computed offline here; no re-inference, no homemade eval loop.

precision array convention (pycocotools): [T=10 IoU thrs, R=101 recall pts,
K=categories, A=areas(all,s,m,l), M=maxDets(1,10,100)]. AP is the mean over
valid (>-1) entries; AP50 uses T=0 only.

Winner rule (predeclared in the P1 gate spec): highest mean AP50:95 over the
decisive Dhaka classes {rickshaw, cng, easy-bike}; every class is reported.

Usage:
    python scripts/p1_triage.py [--arms p1-rtdetr-r18 p1-rtdetr-r50]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from research.perception.voc_to_yolo import PORIBOHON_CLASSES  # noqa: E402

BUCKET = "dhakaflow-train-915644996102"
DECISIVE = ("rickshaw", "cng", "easy-bike")


def _env():
    import os, re
    env = dict(os.environ)
    for line in (REPO / "dhakaflow" / ".env").read_text().splitlines():
        m = re.match(r"\s*(AWS_[A-Z_]+)\s*=\s*(\S+)", line)
        if m and m.group(1) not in env:
            env[m.group(1)] = m.group(2)
    return env


def fetch_eval(arm: str, dest: Path) -> Path | None:
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"{arm}_eval.pth"
    r = subprocess.run(["aws", "s3", "cp",
                        f"s3://{BUCKET}/ckpt/{arm}/out/eval.pth", str(out)],
                       env=_env(), capture_output=True, text=True)
    return out if r.returncode == 0 else None


def per_class_ap(eval_pth: Path) -> dict:
    import numpy as np
    import torch
    state = torch.load(eval_pth, map_location="cpu", weights_only=False)
    prec = state["precision"]          # [T, R, K, A, M]
    k_count = prec.shape[2]
    rows = {}
    for k in range(k_count):
        name = (PORIBOHON_CLASSES[k] if k < len(PORIBOHON_CLASSES)
                else f"cat_{k}")
        p_all = prec[:, :, k, 0, -1]
        p50 = prec[0, :, k, 0, -1]
        rows[name] = {
            "ap50_95": float(np.mean(p_all[p_all > -1])) if (p_all > -1).any() else None,
            "ap50": float(np.mean(p50[p50 > -1])) if (p50 > -1).any() else None,
        }
    valid = [v["ap50_95"] for v in rows.values() if v["ap50_95"] is not None]
    return {"per_class": rows,
            "map50_95": sum(valid) / len(valid) if valid else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+",
                    default=["p1-rtdetr-r18", "p1-rtdetr-r50"])
    ap.add_argument("--out", type=Path,
                    default=REPO / "artifacts" / "p1_triage")
    args = ap.parse_args()

    report = {}
    for arm in args.arms:
        f = fetch_eval(arm, args.out)
        if f is None:
            report[arm] = {"status": "NO_EVAL_YET"}
            continue
        m = per_class_ap(f)
        decisive = [m["per_class"].get(c, {}).get("ap50_95") for c in DECISIVE]
        decisive = [d for d in decisive if d is not None]
        m["decisive_mean_ap50_95"] = (sum(decisive) / len(decisive)
                                      if decisive else None)
        m["status"] = "OK"
        report[arm] = m

    ranked = sorted((a for a in report if report[a].get("status") == "OK"),
                    key=lambda a: report[a]["decisive_mean_ap50_95"] or -1,
                    reverse=True)
    result = {
        "winner_rule": "highest mean AP50:95 over " + "/".join(DECISIVE),
        "winner": ranked[0] if ranked else None,
        "arms": report,
        "dataset": "Poribohon-BD official (CC BY 4.0), frozen split 300aabc8",
        "eval_provenance": "official DetSolver.val() eval.pth (det_solver.py:102)",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "triage.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
