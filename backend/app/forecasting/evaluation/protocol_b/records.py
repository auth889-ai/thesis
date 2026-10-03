"""What Protocol B keeps: the persisted prediction blocks, the comparison record file and its Markdown view,
the cross-seed summary, and the merge of a later model family into an existing block."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .data import load
from .scoring import onset_lead, score
from .settings import OUT

RECORDS = OUT / "model_comparison.json"
MARKDOWN = OUT / "model_comparison.md"


def block_path(dataset: str, region: str, n_windows: int, nodes: int, seed: int) -> Path:
    return OUT / "protocol_b" / f"{dataset}_{region}_w{n_windows}_n{nodes}_s{seed}.npz"


def persist_block(dataset: str, region: str, n_windows: int, nodes: int, seed: int, truth, starts, thr, preds: dict) -> Path:
    """Every prediction is kept: the conformal layer calibrates on the validation block and is scored on the test
    block, and a reviewer can re-score any model without re-running it."""
    path = block_path(dataset, region, n_windows, nodes, seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, truth=truth, starts=starts, threshold=thr, **{f"pred_{k}": v for k, v in preds.items()})
    return path


def key(r: dict) -> str:
    """One record per (dataset, roads scored, seed): several seeds of one dataset live side by side."""
    p = r.get("protocol", {})
    return f"{r['dataset']}|n{r.get('nodes', p.get('nodes_scored'))}|s{p.get('seed', 11)}"


def read() -> list[dict]:
    return json.loads(RECORDS.read_text()) if RECORDS.exists() else []


def write(records: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    by = {key(r): r for r in read() if isinstance(r, dict)}
    for r in records:
        by[key(r)] = r
    allr = sorted(by.values(), key=key)
    RECORDS.write_text(json.dumps(allr, indent=1))
    MARKDOWN.write_text(markdown(allr))


def markdown(allr: list[dict]) -> str:
    L = ["# Model comparison — one protocol, models that can be compared\n",
         "Every model below sees the SAME test windows, the SAME context and the SAME horizons, on "
         "datasets where the future is known. This is what turns a forecast into evidence.\n",
         "OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' "
         "split, and mixing that with 5/15/30/60-minute horizons would be the incompatible "
         "comparison this project keeps refusing to make.\n"]
    for r in allr:
        p = r["protocol"]
        L += [f"\n## {r['dataset']} — {r['nodes']} nodes, {p['windows']} test windows, seed {p.get('seed', 11)}\n",
              f"Context {p['context_steps']} steps; {p['split']}. Congestion: {p['congestion_threshold']}. {p['missing']}.\n",
              "| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |",
              "|---|---|---|---|---|---|---|---|---|"]
        for name, res in sorted(r["results"].items()):
            h15 = res["horizons"].get(15, res["horizons"].get("15", {}))
            h60 = res["horizons"].get(60, res["horizons"].get("60", {}))
            ol = res["onset_lead"]
            L.append(f"| {name} | {h15.get('mae','–')} | {h15.get('rmse','–')} | {h15.get('mape_pct','–')} | **{h15.get('congestion_mae','–')}** | "
                     f"{h15.get('congestion_f1','–')} | {h60.get('mae','–')} | {ol.get('detection_rate','–')} | {ol.get('mean_lead_min','–')} min |")
    L.append("\nRegenerate: `python -m app.forecasting.evaluation.evaluate_models --all`. Machine-readable: `model_comparison.json`.\n")
    return "\n".join(L)


def summary(dataset: str, nodes: int | None = None) -> dict | None:
    """Mean and standard deviation of every metric across the seeds run for a dataset (and roads scored)."""
    runs = [r for r in read() if r["dataset"] == dataset and (nodes is None or r.get("nodes") == nodes)]
    if not runs:
        return None
    if nodes is None:                                              # the roads-scored count with the most seeds wins
        counts: dict = {}
        for r in runs:
            counts[r.get("nodes")] = counts.get(r.get("nodes"), 0) + 1
        nodes = max(counts, key=counts.get)
        runs = [r for r in runs if r.get("nodes") == nodes]
    models = sorted(set().union(*(r["results"].keys() for r in runs)))
    out = {}
    for m in models:
        rows = [r["results"][m] for r in runs if m in r["results"]]
        agg = {"n_seeds": len(rows), "horizons": {}, "onset_lead": {}}
        for h in ("5", "15", "30", "60"):
            vals: dict = {}
            for row in rows:
                hz = row["horizons"].get(h) or row["horizons"].get(int(h)) or {}
                for k, v in hz.items():
                    if isinstance(v, (int, float)):
                        vals.setdefault(k, []).append(float(v))
            if vals:
                agg["horizons"][h] = {k: {"mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v)), 4)} for k, v in vals.items()}
        vals = {}
        for row in rows:
            for k, v in row["onset_lead"].items():
                if isinstance(v, (int, float)):
                    vals.setdefault(k, []).append(float(v))
        agg["onset_lead"] = {k: {"mean": round(float(np.mean(v)), 4), "std": round(float(np.std(v)), 4)} for k, v in vals.items()}
        out[m] = agg
    seeds = sorted(r["protocol"].get("seed", 11) for r in runs)
    return {"dataset": dataset, "nodes": nodes, "seeds": seeds, "windows": runs[0]["protocol"].get("windows"), "protocol": runs[0]["protocol"], "models": out}


def merge(dataset: str, region: str, n_windows: int, max_nodes: int, seed: int, stage_files: list[Path]) -> dict | None:
    """Add one or more staged prediction files to the persisted block and re-score every model on it.

    A new model family (a foundation model that took an hour on the laptop's GPU) joins the comparison
    without re-running the families already there; the windows must match exactly or the merge refuses.
    """
    data = load(dataset)
    N = min(max_nodes, data.shape[1]) if max_nodes else data.shape[1]
    keep = block_path(dataset, region, n_windows, N, seed)
    base = dict(np.load(keep))
    for f in stage_files:
        z = np.load(f)
        if not np.array_equal(z["starts"], base["starts"]):
            raise SystemExit(f"{f}: windows differ from the persisted block; re-run the stage with the same seed/windows/nodes")
        base.update({k: z[k] for k in z.files if k.startswith("pred_")})
    np.savez_compressed(keep, **base)
    if region != "test":
        return None
    truth, thr = base["truth"], base["threshold"]
    preds = {k[5:]: v for k, v in base.items() if k.startswith("pred_")}
    prior = {key(r): r for r in read()}
    rec = prior.get(f"{dataset}|n{N}|s{seed}") or {"dataset": dataset, "protocol": {"seed": seed, "nodes_scored": int(N)}, "nodes": int(N), "timesteps": int(data.shape[0])}
    rec["results"] = {name: {"horizons": score(p, truth, thr), "onset_lead": onset_lead(p, truth, thr)} for name, p in preds.items()}
    rec["generated_utc"] = datetime.now(timezone.utc).isoformat()
    rec["protocol"]["merged_stages"] = sorted(set(rec["protocol"].get("merged_stages", [])) | {f.name for f in stage_files})
    return rec
