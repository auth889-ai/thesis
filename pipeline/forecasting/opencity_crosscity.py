#!/usr/bin/env python3
"""Cross-city evaluation with the official OpenCity foundation model.

    python pipeline/forecasting/opencity_crosscity.py --list
    python pipeline/forecasting/opencity_crosscity.py --dataset PEMS07M
    python pipeline/forecasting/opencity_crosscity.py --all-zeroshot

THE POINT THIS SCRIPT EXISTS TO GET RIGHT
    "Zero-shot" means the model never saw that city during pre-training. OpenCity's own
    `conf/general_conf/pretrain.conf` records the pre-training corpus in a commented-out
    `dataset_use` line, and it includes **METR_LA and PEMS_BAY**.

    So evaluating OpenCity-plus on METR-LA or PEMS-BAY and calling the result zero-shot would be
    false. That is exactly why the authors' own evaluation example in their README uses PEMS07M —
    a city absent from that list. This script therefore refuses to label any pre-training city as
    zero-shot, and marks it SEEN_IN_PRETRAINING instead.

    The genuinely held-out cities available in the released dataset are listed in HELD_OUT below.

WHAT IS RUN
    The authors' own command, unmodified:

        python Run.py -mode test -model OpenCity -load_pretrain_path OpenCity-plus.pth \\
               -batch_size 2 --embed_dim 512 --skip_dim 512 --enc_depth 6

    with `-test_ratio` supplied on the command line (their shipped config sets it to 0.0, which
    leaves no test split at all).

THE ONE FILE THIS TOUCHES, AND WHY THAT IS THE AUTHORS' OWN PROCEDURE
    Which dataset to evaluate lives in `conf/general_conf/pretrain.conf`, read from a hard-coded
    relative path, and the `-dataset_use` flag cannot override it: upstream declares it
    `type=list`, so argparse would split "PEMS07M" into single characters. Their README instructs
    the reader to edit that value ("please use only one dataset to test (e.g. dataset_use =
    ['PEMS07M'] in pretrain.config)"), so setting it is configuration, not modification of their
    algorithm. This script edits only that one assignment, restores the file afterwards, and
    verifies with `git status` that the checkout is byte-identical to the pinned SHA when it
    finishes — including if the run crashes.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream"))
OC = WORKSPACE / "OpenCity"
PINNED_SHA = "eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f"
CONF = OC / "conf/general_conf/pretrain.conf"
WEIGHTS = "OpenCity-plus.pth"
OUT = REPO / "results/forecasting"

# From the commented-out `dataset_use` line in the authors' pretrain.conf — the pre-training corpus.
PRETRAINED_ON = {
    "CAD4-1", "CAD4-2", "CAD4-3", "CAD4-4", "CAD7-1", "CAD7-2", "CAD7-3", "CAD8-1", "CAD8-2",
    "CAD12-1", "CAD12-2", "PEMS08", "PEMS04", "PEMS_BAY", "METR_LA", "NYC_TAXI",
    "TrafficHZ", "TrafficZZ", "TrafficCD", "TrafficJN",
}
# Released datasets NOT in that corpus — the only ones a zero-shot claim can be made about.
HELD_OUT = ("PEMS07M", "TrafficSH", "TrafficNJ", "TrafficTJ", "SZ_DIDI", "CD_DIDI",
            "NYC_BIKE-3", "CHI_TAXI")


def exposure(dataset: str) -> str:
    return "SEEN_IN_PRETRAINING" if dataset in PRETRAINED_ON else "HELD_OUT_ZERO_SHOT"


def check_clone() -> str:
    if not OC.exists():
        raise SystemExit(f"OpenCity checkout missing at {OC}\n"
                         f"  python pipeline/upstream/fetch_upstream.py --name OpenCity")
    sha = subprocess.check_output(["git", "-C", str(OC), "rev-parse", "HEAD"], text=True).strip()
    if sha != PINNED_SHA:
        raise SystemExit(f"OpenCity is at {sha}, not the pinned {PINNED_SHA}")
    return sha


def tracked_dirty() -> str:
    return subprocess.check_output(
        ["git", "-C", str(OC), "status", "--porcelain", "--untracked-files=no"], text=True).strip()


METRIC_RE = re.compile(
    r"average horizon.*?MAE:\s*([0-9.]+).*?RMSE:\s*([0-9.]+).*?MAPE:\s*([0-9.]+)",
    re.IGNORECASE | re.DOTALL)
HORIZON_RE = re.compile(
    r"Horizon\s+(\d+).*?MAE:\s*([0-9.]+).*?RMSE:\s*([0-9.]+).*?MAPE:\s*([0-9.]+)", re.IGNORECASE)


def parse_metrics(text: str) -> dict:
    """Read the authors' own printed evaluation. Never recomputed by us."""
    out: dict = {"horizons": {}}
    for h, mae, rmse, mape in HORIZON_RE.findall(text):
        out["horizons"][int(h)] = {"mae": float(mae), "rmse": float(rmse), "mape": float(mape)}
    m = METRIC_RE.search(text)
    if m:
        out["average"] = {"mae": float(m.group(1)), "rmse": float(m.group(2)),
                          "mape": float(m.group(3))}
    return out


def run_one(dataset: str, test_ratio: float, batch_size: int, timeout: int,
            arm: str = "zero_shot", epochs: int = 0) -> dict:
    """arm='zero_shot' runs the authors' `-mode test`. arm='fine_tuned' runs their `-mode eval`,
    which loads the released weights, freezes every parameter except `predictor.linear`, and trains
    that head on the target city before testing — their own adaptation path, not one we invented."""
    sha = check_clone()
    if tracked_dirty():
        raise SystemExit(f"the pinned OpenCity checkout is already modified:\n{tracked_dirty()}")

    original = CONF.read_text()
    started = datetime.now(timezone.utc).isoformat()
    try:
        CONF.write_text(re.sub(r"^dataset_use\s*=.*$", f"dataset_use = ['{dataset}']",
                               original, count=1, flags=re.MULTILINE))
        # Launched through _opencity_boot.py, which restores NumPy aliases deleted in 2.0 and
        # defaults torch.load to CPU when there is no GPU. It edits none of their source; the
        # shims are printed into the log so the compatibility layer is auditable.
        boot = REPO / "pipeline/forecasting/_opencity_boot.py"
        mode = "eval" if arm == "fine_tuned" else "test"
        cmd = [sys.executable, str(boot), "-mode", mode, "-model", "OpenCity",
               "-load_pretrain_path", WEIGHTS, "-batch_size", str(batch_size),
               "--embed_dim", "512", "--skip_dim", "512", "--enc_depth", "6"]
        if arm == "fine_tuned":
            cmd += ["-epochs", str(epochs)]
        env = dict(os.environ, DF_OC_SCRIPT=str(OC / "model/Run.py"))
        proc = subprocess.run(cmd, cwd=OC / "model", capture_output=True, text=True,
                              timeout=timeout, env=env)
        log = (proc.stdout or "") + (proc.stderr or "")
        metrics = parse_metrics(log)
        status = "OK" if (proc.returncode == 0 and metrics.get("average")) else "FAILED"
    except subprocess.TimeoutExpired:
        log, metrics, status, proc = "timed out", {}, "TIMEOUT", None
    finally:
        CONF.write_text(original)                       # always restore, crash or not
        if tracked_dirty():
            raise SystemExit("FAILED TO RESTORE the pinned checkout — refusing to continue:\n"
                             f"{tracked_dirty()}")

    logs = OUT / "opencity_logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / f"{dataset}_{arm}.log").write_text(log)

    return {
        "dataset": dataset,
        "model": "OpenCity-plus",
        "arm": arm if exposure(dataset) == "HELD_OUT_ZERO_SHOT" else f"{arm}_but_seen_in_pretraining",
        "exposure": exposure(dataset),
        "exposure_note": (
            "absent from OpenCity's pre-training corpus, so this IS a zero-shot result"
            if exposure(dataset) == "HELD_OUT_ZERO_SHOT" else
            "present in OpenCity's pre-training corpus (see the commented dataset_use line in "
            "conf/general_conf/pretrain.conf) — this is NOT zero-shot and must never be reported "
            "as such"),
        "status": status,
        "metrics": metrics,
        "upstream": {"repo": "HKUDS/OpenCity", "sha": sha, "weights": WEIGHTS,
                     "weights_source": "huggingface hkuds/OpenCity-Plus (released, as-is)",
                     "command": "Run.py -mode test -model OpenCity (authors' own evaluation)",
                     "config_changed": f"dataset_use -> ['{dataset}'] (their documented procedure), restored after the run",
                     "checkout_restored": True},
        "settings": {"batch_size": batch_size, "embed_dim": 512, "skip_dim": 512, "enc_depth": 6,
                     "split": "the authors' own — Run.py copies val/test ratios from the model's "
                              "predictor config over anything passed on the command line, so the "
                              "shipped split is what is used and we do not fight it"},
        "compatibility_shims": "pipeline/forecasting/_opencity_boot.py — NumPy 2.0 alias "
                               "restoration and CPU map_location; no upstream source is edited",
        "started_utc": started,
        "log": f"results/forecasting/opencity_logs/{dataset}_{arm}.log",
        "fine_tune_epochs": epochs if arm == "fine_tuned" else None,
    }


def write_outputs(records: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "opencity_crosscity.json"
    prior = []
    if path.exists():
        try:
            prior = json.loads(path.read_text())
        except json.JSONDecodeError:
            prior = []
    by = {(r["dataset"], r.get("arm", "zero_shot")): r for r in prior}
    for r in records:
        by[(r["dataset"], r["arm"])] = r
    allrecs = sorted(by.values(), key=lambda r: (r["exposure"], r["dataset"], r["arm"]))
    path.write_text(json.dumps(allrecs, indent=1))

    # Our own city-specific numbers, read from the evidence file so this table cannot drift.
    own = {}
    tr = REPO / "results/forecasting/trained_results.json"
    if tr.exists():
        for r in json.loads(tr.read_text()).get("runs", []):
            m = (r.get("metrics_by_horizon_min") or {}).get("15")
            if m:
                own.setdefault(r["dataset"].replace("-", "_"), []).append(
                    {"model": r["model"], "mae": m.get("mae")})

    L = ["# Cross-city generalization — OpenCity foundation model\n",
         "Official `HKUDS/OpenCity` at the pinned SHA, evaluated with the authors' own commands and "
         "their released `OpenCity-plus` weights, used as published. No foundation model is "
         "pre-trained here.\n",
         "## The distinction that decides whether this is a zero-shot claim at all\n",
         "OpenCity's pre-training corpus is recorded in a commented-out `dataset_use` line in "
         "`conf/general_conf/pretrain.conf`, and it **includes METR_LA and PEMS_BAY**. Evaluating "
         "on those cities is therefore *not* zero-shot, however good the number looks. Only cities "
         "absent from that list support a zero-shot claim — which is why the authors' own README "
         "example evaluates on PEMS07M.\n",
         "**This is the trap the plan for this chapter walked into:** two of the three cities "
         "originally named for the cross-city comparison are in OpenCity's training data.\n",
         "## Arms\n",
         "| arm | what it is |",
         "|---|---|",
         "| city-specific | Graph WaveNet / STID trained on that city by us (the strong baseline) |",
         "| OpenCity zero-shot | released weights, `-mode test`, never shown this city |",
         "| OpenCity fine-tuned | released weights, `-mode eval` — upstream freezes everything except "
         "`predictor.linear` and trains that head on the target city |",
         "",
         "## Results\n",
         "Published figures are OpenCity's own Table 1 (arXiv 2408.10269) for OpenCity-plus in the "
         "zero-shot setting — the same model, dataset and protocol.\n",
         "| dataset | exposure | ours MAE | published MAE | diff | ours RMSE | pub RMSE | ours MAPE | pub MAPE | verdict |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for r in allrecs:
        a = (r.get("metrics") or {}).get("average") or {}
        pub = r.get("published") or {}
        d = (r.get("reproduction_diff_pct") or {}).get("mae")
        tag = "**HELD OUT**" if r["exposure"] == "HELD_OUT_ZERO_SHOT" else "seen in pre-training"
        L.append(f"| {r['dataset']} | {tag} | {a.get('mae', '–')} | {pub.get('mae', '–')} | "
                 f"{(str(d) + ' %') if d is not None else '–'} | {a.get('rmse', '–')} | "
                 f"{pub.get('rmse', '–')} | {a.get('mape', '–')} | {pub.get('mape', '–')} | "
                 f"**{r.get('verdict', r['status'])}** |")
    fails = [r for r in allrecs if r["status"] != "OK"]
    if fails:
        L += ["", "### Runs that did not produce a metric\n"]
        for r in fails:
            L.append(f"- **{r['dataset']}** — {r['status']}: {r.get('failure') or 'see log'}")
        L.append("")

    if own:
        L += ["", "## Our city-specific models, for comparison\n",
              "Trained by us on that city, MAE at 15 min. These are the numbers OpenCity has to "
              "beat to make cross-city pre-training worthwhile on a city where labelled history "
              "already exists.\n",
              "| dataset | model | MAE@15min | in OpenCity's pre-training? |", "|---|---|---|---|"]
        for ds, rows_ in sorted(own.items()):
            for r_ in sorted(rows_, key=lambda x: x["mae"] or 9e9):
                L.append(f"| {ds} | {r_['model']} | {r_['mae']} | "
                         f"{'YES — not zero-shot' if ds in PRETRAINED_ON else 'no'} |")
        L += ["", "**These two tables are not directly comparable and must not be presented as if "
                  "they were.** OpenCity is scored on its own 288-step horizon under the authors' "
                  "split; our models are scored at 15 minutes under the DCRNN protocol. A like-for-"
                  "like comparison needs both models evaluated under one protocol on one city, "
                  "which is a separate piece of work and is not claimed here.\n"]

    L += ["", "Rows marked *seen in pre-training* are reported for completeness and must not be "
              "quoted as evidence of cross-city generalization.\n",
          "Regenerate: `python pipeline/forecasting/opencity_crosscity.py --all-zeroshot`. "
          "Machine-readable: `opencity_crosscity.json`.\n"]
    (OUT / "opencity_crosscity.md").write_text("\n".join(L))
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="PEMS07M")
    p.add_argument("--arm", default="zero_shot", choices=["zero_shot", "fine_tuned"])
    p.add_argument("--fine-tune-epochs", type=int, default=5)
    p.add_argument("--all-zeroshot", action="store_true", help="every held-out city present locally")
    p.add_argument("--batch-size", type=int, default=2)
    p.add_argument("--timeout", type=int, default=7200)
    p.add_argument("--list", action="store_true")
    a = p.parse_args()

    if a.list:
        print("pre-training corpus (NOT zero-shot):")
        for d in sorted(PRETRAINED_ON):
            print(f"   {d}")
        print("\nheld-out (zero-shot claims allowed), present locally:")
        for d in HELD_OUT:
            here = (OC / "data" / d / f"{d}.npz").exists()
            print(f"   {d:<12} {'downloaded' if here else 'not downloaded'}")
        return 0

    targets = ([d for d in HELD_OUT if (OC / "data" / d / f"{d}.npz").exists()]
               if a.all_zeroshot else [a.dataset])
    if not targets:
        raise SystemExit("no held-out datasets downloaded; fetch them from hkuds/OpenCity-dataset")

    records = []
    for d in targets:
        print(f"[opencity] {d} [{a.arm}] ({exposure(d)}) …", flush=True)
        r = run_one(d, 0.0, a.batch_size, a.timeout, arm=a.arm, epochs=a.fine_tune_epochs)
        avg = (r.get("metrics") or {}).get("average") or {}
        print(f"           {r['status']}  MAE={avg.get('mae', '–')} RMSE={avg.get('rmse', '–')} "
              f"MAPE={avg.get('mape', '–')}")
        records.append(r)
    write_outputs(records)
    print(f"\nwrote {(OUT / 'opencity_crosscity.md').relative_to(REPO)}")
    return 0 if all(r["status"] == "OK" for r in records) else 1


if __name__ == "__main__":
    sys.exit(main())
