"""RQ1 end to end, one stage at a time (each writes its own JSON under results/forecasting/rq1/):

    python -m core.ml.forecasting.transfer_dhaka.run rescore      # Protocol B blocks (METR-LA, PEMS-BAY x seeds) + weekday HA -> BasicTS metrics
    python -m core.ml.forecasting.transfer_dhaka.run dhaka        # DhaTraX site-days: persistence, Chronos-Bolt, Chronos-2, TimesFM, transferred trees
    python -m core.ml.forecasting.transfer_dhaka.run transfer     # trees trained on METR-LA -> PEMS-BAY, against PEMS-BAY's own
    python -m core.ml.forecasting.transfer_dhaka.run character    # why Dhaka differs: stop-and-go, congestion, CV, autocorrelation
    python -m core.ml.forecasting.transfer_dhaka.run summary      # summary.json / .md, figures, evidence hashes

The Protocol B blocks come first from `python -m core.ml.forecasting.evaluation.evaluate_models` (research/forecasting_rq1/scripts/01_protocol_b.sh).
Every number names its city and dataset."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.common.paths import REPO
from core.ml.forecasting.transfer_dhaka import baselines, character, metrics, transfer

OUT = REPO / "results/forecasting/rq1"
EVIDENCE = REPO / "evidence/forecasting/rq1"
BLOCKS = REPO / "results/forecasting/protocol_b"
DATASETS = ("METR-LA", "PEMS-BAY")
SEEDS = (11, 23, 37)
WINDOWS = 120
CITY = {"METR-LA": "Los Angeles", "PEMS-BAY": "San Francisco Bay Area", "DhaTraX": "Dhaka"}


def _write(name: str, body: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps({"generated_utc": datetime.now(timezone.utc).isoformat(), **body}, indent=1, ensure_ascii=False))
    return p


def _block(dataset: str, seed: int, nodes: int) -> Path:
    return BLOCKS / f"{dataset}_test_w{WINDOWS}_n{nodes}_s{seed}.npz"


def rescore() -> Path:
    """Every saved prediction re-scored with BasicTS's masked metrics at 15/30/60 min, plus the weekday historical average."""
    from core.ml.forecasting.evaluation.protocol_b.data import load, splits
    from core.ml.forecasting.evaluation.protocol_b.settings import CONTEXT, STEPS
    rows = []
    for ds in DATASETS:
        data = load(ds)
        ts = baselines.timestamps(ds)
        tr_end, _ = splits(len(data))
        table = baselines.weekday_table(data[:tr_end], ts[:tr_end])
        for seed in SEEDS:
            path = _block(ds, seed, data.shape[1])
            if not path.exists():
                rows.append({"dataset": ds, "seed": seed, "missing": f"{path.name} not run yet"})
                continue
            z = np.load(path)
            truth, starts = z["truth"], z["starts"]
            preds = {k[5:]: z[k] for k in z.files if k.startswith("pred_")}
            preds["historical_average_weekday"] = baselines.predict_weekday(table, ts, starts, CONTEXT, STEPS, preds["historical_average"])
            rows.append({"dataset": ds, "city": CITY[ds], "seed": seed, "nodes": int(data.shape[1]), "windows": int(len(starts)),
                         "block": str(path.relative_to(REPO)), "block_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                         "scored_from": str(ts[starts[0] + CONTEXT]), "scored_to": str(ts[starts[-1] + CONTEXT + STEPS - 1]),
                         "results": {m: metrics.score(p, truth) for m, p in preds.items()}})
    return _write("lab_scores.json", {"metrics": "BasicTS masked_mae / masked_rmse / masked_mape, null 0.0 (third_party/SOURCES.md)",
                                      "protocol": "Protocol B: chronological 70/10/20 split, a contiguous block of 120 test windows chosen by the seed, context 96 steps",
                                      "rows": rows})


def _foundation_here(ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """The three zero-shot models through Protocol B's own functions, on (W, C, N) contexts (0 = no reading)."""
    from core.ml.forecasting.evaluation.foundation_stage import predict_chronos2, predict_timesfm
    from core.ml.forecasting.evaluation.protocol_b.baselines import predict_chronos
    out = {"chronos": predict_chronos(ctx, steps, "amazon/chronos-bolt-small")}
    out.update({k: v for k, v in predict_chronos2(ctx, steps).items() if k == "chronos2"})
    out.update(predict_timesfm(ctx, steps))
    return out


def _foundation(ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """The same, in a child process: torch and the tree libraries crash when they share an interpreter (as Protocol B found)."""
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "ctx.npy", Path(td) / "out.npz"
        np.save(src, ctx)
        subprocess.run([sys.executable, "-c", f"import numpy as np; from core.ml.forecasting.transfer_dhaka.run import _foundation_here; "
                        f"np.savez({str(dst)!r}, **_foundation_here(np.load({str(src)!r}), {steps}))"], check=True)
        z = np.load(dst)
        return {k: z[k] for k in z.files}


def _trees_here(train_dataset: str, seed: int, ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """Protocol B's trees on the train split of `train_dataset`, scaled per window (rq1/transfer.py), predicting `ctx`."""
    from core.ml.forecasting.evaluation.protocol_b.data import load, splits
    data = load(train_dataset)
    return transfer.predict(transfer.fit(data[:splits(len(data))[0]], seed), ctx, steps)


def _trees(train_dataset: str, seed: int, ctx: np.ndarray, steps: int) -> dict[str, np.ndarray]:
    """The same, in a child process, so this process (which scores with torch) never loads the tree libraries."""
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src, dst = Path(td) / "ctx.npy", Path(td) / "out.npz"
        np.save(src, ctx)
        subprocess.run([sys.executable, "-c", f"import numpy as np; from core.ml.forecasting.transfer_dhaka.run import _trees_here; "
                        f"np.savez({str(dst)!r}, **_trees_here({train_dataset!r}, {seed}, np.load({str(src)!r}), {steps}))"], check=True)
        z = np.load(dst)
        return {k: z[k] for k in z.files}


def dhaka() -> Path:
    from core.common.data.recorded import dhatrax
    from core.ml.forecasting.transfer_dhaka import dhaka as dk
    sites = []
    for site in dhatrax.sites():
        values, _, meta = dk.dhatrax_site(site)
        ctx, truth, origins = dk.windows(values)
        preds = {"persistence": dk.persistence(ctx)} | _foundation(ctx, dk.STEPS)
        per_seed = {s: _trees("METR-LA", s, ctx, dk.STEPS) for s in SEEDS}
        res = {m: metrics.score(p, truth) for m, p in preds.items()}
        for name in ("random_forest", "xgboost"):
            scores = [metrics.score(per_seed[s][name], truth) for s in SEEDS]
            res[f"{name}_from_metr_la"] = {h: {k: round(float(np.mean([sc[h][k] for sc in scores])), 4) for k in scores[0][h]}
                                           | {f"{k}_sd": round(float(np.std([sc[h][k] for sc in scores], ddof=1)), 4) for k in scores[0][h]} for h in scores[0]}
        sites.append({"site": site["site"], "day": site.get("day"), "windows": int(len(origins)), "context_steps": dk.CONTEXT, "unit": "km/h", "results": res,
                      "no_historical_average": "one recorded day per site: there is no other day to average", "meta": {k: meta[k] for k in ("dataset", "series", "limits")}})
    return _write("dhaka_scores.json", {"city": "Dhaka", "dataset": "DhaTraX v1.0 (CC BY 4.0), 5-minute median speed at three camera sites, one day each",
                                        "metrics": "BasicTS masked metrics; trees: mean and sd over training seeds 11, 23, 37", "sites": sites})


def transfer_test() -> Path:
    """Trees trained on METR-LA scored on PEMS-BAY's Protocol B windows (each seed's block), against the same recipe trained on PEMS-BAY."""
    from core.ml.forecasting.evaluation.protocol_b.data import load, windows
    from core.ml.forecasting.evaluation.protocol_b.settings import STEPS
    bay = load("PEMS-BAY")
    rows = []
    for seed in SEEDS:
        _, ctx, truth = windows(bay, WINDOWS, seed, STEPS, "test")
        moved, home = _trees("METR-LA", seed, ctx, STEPS), _trees("PEMS-BAY", seed, ctx, STEPS)
        rows.append({"seed": seed, "results": {f"{m}_trained_on_metr_la": metrics.score(p, truth) for m, p in moved.items()}
                     | {f"{m}_trained_on_pems_bay": metrics.score(p, truth) for m, p in home.items()}})
    return _write("transfer_scores.json", {"target": "PEMS-BAY (San Francisco Bay Area), Protocol B test blocks of seeds 11, 23, 37",
                                           "source": "METR-LA (Los Angeles) train split only", "cannot_transfer": transfer.CANNOT_TRANSFER,
                                           "scaling": "each window scaled by its own context mean; no target data used for training", "rows": rows})


def character_stage() -> Path:
    from core.common.data.recorded import dhatrax
    from core.ml.forecasting.evaluation.protocol_b.data import load, splits
    from core.ml.forecasting.evaluation.recorded_backtest import dhatrax_site
    out = {}
    for ds in DATASETS:
        data = load(ds)
        out[ds] = {"city": CITY[ds], "unit": "mph", **character.summary(character.la_sensor_days(data, baselines.timestamps(ds), splits(len(data))[1]))}
    out["DhaTraX"] = {"city": "Dhaka", "unit": "km/h", "sites": {}}
    for site in dhatrax.sites():
        values, _, _ = dhatrax_site(site)
        out["DhaTraX"]["sites"][site["site"]] = {"day": site.get("day"), **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in character.measures(values[:, 0]).items()}}
    return _write("character.json", {"window": "weekdays 06:00-19:00, 5-minute speeds, outages removed", "definitions": character.__doc__, "measures": out})


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stage", choices=["rescore", "dhaka", "transfer", "character", "summary"])
    a = ap.parse_args()
    if a.stage == "summary":
        from core.ml.forecasting.transfer_dhaka.summary import build
        print(build())
    else:
        print({"rescore": rescore, "dhaka": dhaka, "transfer": transfer_test, "character": character_stage}[a.stage]())
