"""PREDICTION: pick a dataset, a region, a moment and a model — get a real forward pass.

Models, all through their own code:
    OpenCity-plus   authors' harness (HKUDS/OpenCity, pinned), released weights, 288 -> 288 steps
    GWNet / STID    checkpoints trained on the official BasicTS configs (METR-LA, PEMS-BAY)
    Chronos-Bolt    amazon/chronos-bolt-small, univariate, zero-shot
    persistence     the floor every model must beat

The window is cut at the chosen moment, the model sees only what came before, and the steps that
followed (when the dataset holds them) score the prediction. Nothing is read from a saved table.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app import evidence_paths as config

sys.path.insert(0, str(config.REPO))
HORIZONS = [5, 15, 30, 60]
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
CHECKPOINT_MODELS = {"GWNet": ("GWNet", {"METR_LA": "METR-LA", "PEMS_BAY": "PEMS-BAY"}),
                     "STID": ("STID", {"METR_LA": "METR-LA", "PEMS_BAY": "PEMS-BAY"})}


def _live_datasets() -> list[dict]:
    from app.data.live_providers import observatory as obs_mod
    out = []
    for cid in obs_mod.observatory.cities():
        r = obs_mod.observatory.readiness(cid)
        if r["steps_have"] < 1:
            continue
        rows, nodes = obs_mod.observatory.series(cid)
        own = obs_mod.observatory.own_history(cid)              # steps the city may be trained and tested on
        names = list(nodes)
        if cid == "dhaka":
            from app.data import reference_corridors as cz
            names = [cz.BY_ID.get(n, {}).get("name", n) for n in nodes]
        else:
            from app.data import city_corridors
            byid = {c["id"]: c for c in city_corridors.load(cid)}
            names = [byid.get(n, {}).get("name", n) for n in nodes]
        out.append({"id": f"live:{cid}", "name": f"{cid.replace('_', ' ').title()} — live corridors ({len(nodes)}), sampled every 5 min",
                    "node_names": names,
                    "nodes": len(nodes), "steps": own["steps_own"], "steps_total": r["steps_have"], "own_history": own,
                    "start_utc": own["first_own_utc"] or (rows[0]["utc"] if rows else None),
                    "interval_min": 5, "exposure": "HELD_OUT_ZERO_SHOT", "live": True,
                    "models": (["OpenCity-plus"] if r["steps_have"] >= 288 and len(nodes) >= 9 else [])
                              + (["Chronos-2", "Chronos-Bolt"] if r["steps_have"] >= 8 else []) + ["persistence"]})
    return out


TRAINED_SUFFIX = " · trained here"


def _with_trained(ds: list[dict]) -> list[dict]:
    """Models the pinned BasicTS harness has trained on THIS dataset (basicts_train.py cards)."""
    from app.forecasting.training import basicts_train as bt
    by = {}
    for c in bt.cards():
        by.setdefault(c["dataset"], []).append(c["arch"])
    for d in ds:
        d["trainable"] = d["id"].startswith(("user:", "live:")) and d["steps"] >= bt.MIN_STEPS
        d["models"] = [f"{a}{TRAINED_SUFFIX}" for a in by.get(d["id"], [])] + d["models"]
        if d["id"].startswith("user:") and "historical_average" not in d["models"]:
            d["models"].append("historical_average")     # the registry's own baseline adapter
    return ds


def datasets(include_uploads: bool = True) -> list[dict]:
    """Live cities first, then the benchmarks; a person's uploads only where they are managed (the Lab's Data tab)."""
    from app.forecasting.opencity import opencity_predict as op
    out = op.local_datasets()
    live = _live_datasets()
    for d in out:
        d["models"] = ["OpenCity-plus", "Chronos-Bolt", "persistence"] + \
                      [m for m, (_, ds) in CHECKPOINT_MODELS.items() if d["id"] in ds]
        d["name"] = {"METR_LA": "Los Angeles — METR-LA (207 loop detectors)", "PEMS_BAY": "Bay Area — PEMS-BAY (325 detectors)",
                     "PEMS07M": "California D7 — PEMS07M (228 detectors)", "TrafficSH": "Shanghai — TrafficSH (896 regions)"}.get(d["id"], d["id"])
    from app.data import uploads as user_datasets
    from app.forecasting.operations import scientific_prediction
    meta, values = scientific_prediction.series()
    from app.forecasting.operations import served_checkpoints
    served = sorted(served_checkpoints.available("METR-LA"))                  # every reproduced checkpoint serves the benchmark map
    canonical = {"id": "METR_LA", "name": "Los Angeles — METR-LA (207 loop detectors, 2012)", "nodes": values.shape[1],
                 "steps": len(values), "interval_min": 5, "quantity": "speed mph",
                 "models": ["GWNet"] + [m for m in served if m != "GWNet"] + ["persistence"], "trainable": False, "scientific": True,
                 "node_names": meta["nodes"], "start_utc": meta["first_utc"]}
    uploads = user_datasets.datasets() if include_uploads else []
    return _with_trained(live) + [canonical] + _with_trained([d for d in out if d["id"] != "METR_LA"] + uploads)


def _series(dataset: str, region: int, n_nodes: int):
    if dataset.startswith("user:"):
        from app.data import uploads as user_datasets
        return user_datasets.series(dataset.split(":", 1)[1], region)
    if dataset.startswith("live:"):
        import numpy as np
        from app.data.live_providers import observatory as obs_mod
        cid = dataset.split(":", 1)[1]
        cd = obs_mod.observatory.city_data(cid)
        vals = np.asarray(cd.values, dtype="float64")
        order = [region] + [i for i in range(vals.shape[1]) if i != region]
        rows, _ = obs_mod.observatory.series(cid)
        return vals[:, order], [cd.node_ids[i] for i in order], np.eye(len(order), dtype="float32"), {
            "quantity": "corridor mean speed, m/s (derived by us)", "reality": "REAL_LIVE",
            "first_utc": rows[0]["utc"] if rows else None, "region_index": region, "subgraph": order}
    from app.forecasting.opencity import opencity_predict as op
    return op.from_dataset(dataset, region, n_nodes)


def _clock(start_utc: str | None, index: int, interval_s: int = 300) -> str | None:
    if not start_utc:
        return None
    return (datetime.fromisoformat(start_utc) + timedelta(seconds=interval_s * index)).isoformat()


def _run(job: str, p: dict) -> None:
    import numpy as np

    def emit(**kw):
        with _LOCK:
            _JOBS[job].update(kw)
    try:
        dataset, model = p.get("dataset", "METR_LA"), p.get("model", "OpenCity-plus")
        from app.forecasting.operations import scientific_prediction
        if dataset in scientific_prediction.DATASETS:
            emit(stage="Fresh canonical inference", step=3)
            result = scientific_prediction.sensor_result(p, job)
            emit(status="done", stage="done", step=5, result=result)
            return
        region, n_nodes = int(p.get("region", 0)), int(p.get("nodes", 48))
        emit(stage="Loading dataset", step=1)
        vals, nodes, A, meta = _series(dataset, region, n_nodes)
        T = vals.shape[0]
        as_of = p.get("as_of")
        floor = 300 if not dataset.startswith(("live:", "user:")) else 1
        step_s = int(meta.get("interval_s", 300))
        hz = HORIZONS if step_s == 300 else [step_s // 60 * k for k in (1, 2, 4, 8)]   # steps 1,2,4,8 of a coarser clock
        end = T if as_of in (None, "", "latest") else max(floor, min(T, int(as_of)))
        hist = vals[:end]
        base = {"dataset": dataset, "model": model, "region": region, "nodes_in_subgraph": len(nodes),
                "series_length": T, "as_of_index": end, "as_of_utc": _clock(meta.get("first_utc"), end, step_s),
                "quantity": meta["quantity"], "reality": meta["reality"],
                "history": [None if x != x else round(float(x), 3) for x in hist[-72:, 0]],
                "history_from_utc": _clock(meta.get("first_utc"), end - 72, step_s), "interval_s": step_s,
                "graph_from": meta.get("graph_from"),
                "actual": [None if x != x else round(float(x), 3) for x in vals[end:end + 12, 0]] if end < T else None}
        emit(stage="Loading model", step=2)
        pred12 = None
        if model == "OpenCity-plus":
            emit(stage="Running the model (OpenCity, 26M parameters)", step=3)
            out = Path(tempfile.mkdtemp(prefix="oc_")) / "p.json"
            if dataset.startswith("user:"):               # their CSV contract, the whole uploaded graph
                from app.data import uploads as user_datasets
                pp = user_datasets.paths(dataset.split(":", 1)[1])
                cmd = [sys.executable, "-m", "app.forecasting.opencity.opencity_predict",
                       "--source", "csv", "--csv", str(pp["csv"]), "--adj", str(pp["adj"]),
                       "--as-of", str(end), "--horizons", "15,30,60", "--out", str(out)]
            else:
                cmd = [sys.executable, "-m", "app.forecasting.opencity.opencity_predict",
                       "--source", "dataset", "--dataset", dataset, "--region", str(region), "--nodes", str(n_nodes),
                       "--as-of", str(end), "--horizons", "15,30,60", "--out", str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1200, cwd=config.REPO)
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError((proc.stderr or proc.stdout or "")[-600:].strip().splitlines()[-1])
            r = json.loads(out.read_text())
            pred12 = r["prediction_region"]
            if pred12 is None:                            # csv source: per-node predictions at the horizons
                pred12 = [None] * 12
                for h, vs in r["predictions"].items():
                    pred12[int(h) // 5 - 1] = vs[region]
            base["model_card"] = {"upstream": "HKUDS/OpenCity @ eca64c9 (pinned)", "weights": r["weights"],
                                  "stack": r["stack"], "claim": r["claim"], "input_steps": 288, "output_steps": 288}
        elif model.endswith(TRAINED_SUFFIX):             # trained on this very dataset by their harness
            from app.forecasting.training import basicts_train as bt
            arch = model[: -len(TRAINED_SUFFIX)]
            card = bt.card_for(dataset, arch)
            if not card:
                raise RuntimeError(f"{arch} has not been trained on {dataset} yet — press Train")
            emit(stage=f"Running the model ({arch}, trained on this data)", step=3)
            pred = bt.predict(card, end)                  # (12, N) in the dataset's own node order
            pred12 = [round(float(x), 3) for x in pred[:, region]]
            tm, pf = card["test_metrics"], card["persistence_test"]
            hmin = {3: step_s * 3 // 60, 6: step_s * 6 // 60, 12: step_s * 12 // 60}
            base["model_card"] = {"checkpoint": Path(card["checkpoint"]).name, "trained_on": f"{dataset} ({card['steps']} steps, {card['nodes']} roads), {card.get('trained_on', 'this CPU')}",
                                  "epochs": card["epochs"], "trained_utc": card["trained_utc"], "stack": card["stack"], "claim": card["claim"],
                                  "reported_test_metrics": {str(hmin[k]): round(tm[f"horizon_{k}"]["MAE"], 3) for k in (3, 6, 12) if f"horizon_{k}" in tm},
                                  "persistence_test_metrics": {str(hmin[k]): round(pf[f"horizon_{k}"]["MAE"], 3) for k in (3, 6, 12) if pf.get(f"horizon_{k}", {}).get("MAE") is not None},
                                  "test_split": "the last 20 % of this dataset, never seen in training (their 70/10/20 split)"}
        elif model in CHECKPOINT_MODELS:
            cli, ds_map = CHECKPOINT_MODELS[model]
            if dataset not in ds_map:
                raise RuntimeError(f"{model} has a trained checkpoint only for {list(ds_map)}")
            emit(stage=f"Running the model ({model})", step=3)
            n_train = int(T * 0.7); test_lo = n_train + int(T * 0.1)
            window = max(0, end - 12 - test_lo)          # the script's window starts its 12 input steps at test_lo + window
            cmd = [sys.executable, "-m", "app.forecasting.infer_from_checkpoint",
                   "--model", cli, "--dataset", ds_map[dataset], "--window", str(window),
                   "--sensors", str(region + 1), "--verify-windows", "0"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=config.REPO)
            f = config.REPO / f"results/forecasting/inference_{cli}_{ds_map[dataset]}.json"
            if proc.returncode != 0 or not f.exists():
                raise RuntimeError((proc.stderr or proc.stdout or "")[-600:].strip().splitlines()[-1])
            r = json.loads(f.read_text())
            rows = [x for x in r["rows"] if x["sensor_index"] == region]
            byh = {x["horizon_min"]: x for x in rows}
            pred12 = [None] * 12
            for h, x in byh.items():
                pred12[h // 5 - 1] = x["predicted_mph"]
            t0 = int(r["t0_absolute"]); end = t0 + int(r["input_len"])
            base.update(as_of_index=end, as_of_utc=_clock(meta.get("first_utc"), end),
                        history=[None if x != x else round(float(x), 3) for x in vals[max(0, end - 72):end, 0]],
                        history_from_utc=_clock(meta.get("first_utc"), end - 72),
                        actual=[None if x != x else round(float(x), 3) for x in vals[end:end + 12, 0]] if end < T else None,
                        model_card={"checkpoint": r["checkpoint"], "trained_on": ds_map[dataset],
                                    "reported_test_metrics": r.get("reported_test_metrics"),
                                    "stack": "official BasicTS config, weights trained on GPU, reloaded here",
                                    "claim": "a city-specific model: it does not transfer to another graph"})
        else:                                             # Chronos-Bolt / persistence via the registry
            emit(stage=f"Running the model ({model})", step=3)
            from app.forecasting.adapters.base import CityData
            from app.forecasting.adapters.registry import forecast as run_forecast
            cd = CityData(city_id=dataset, node_ids=nodes, values=hist.astype("float32"), interval_s=step_s,
                          target=meta["quantity"], unit=meta["quantity"], reality=meta["reality"])
            r = run_forecast(cd, hz, model)
            f = r.get("forecast")
            if not f:
                raise RuntimeError(str((r.get("decision") or {}).get("reason")))
            pred12 = [None] * 12
            for h in hz:
                v = (f["values"].get(h) or f["values"].get(str(h)))[0]
                pred12[h * 60 // step_s - 1] = None if v is None or v != v else round(float(v), 3)
            base["model_card"] = {"model": f["model"], "checkpoint": f["checkpoint"], "is_baseline": f["is_baseline"],
                                  "stack": "the common forecast interface (src/pipeline/forecasting/adapters)",
                                  "claim": "univariate zero-shot" if model == "Chronos-Bolt" else "the floor"}
        emit(stage="Scoring", step=4)
        from app.data import provenance as pv
        card_ck = (base.get("model_card") or {}).get("checkpoint")
        rec = pv.Run(job, city=dataset, origin=None, destination=None, requested_model=model, resolved_model=model,
                     region=region, dataset_hash=pv.sha_array(vals[:end, :1]) if dataset.startswith(("user:", "live:")) else dataset,
                     graph_hash=pv.sha_array(A) if A is not None else None, checkpoint_path=card_ck,
                     checkpoint_sha256=pv.sha_file(next((c["checkpoint"] for c in __import__("app.forecasting.training.basicts_train", fromlist=["cards"]).cards()
                                                          if c["dataset"] == dataset and c["arch"] == model.replace(TRAINED_SUFFIX, "")), None)) if model.endswith(TRAINED_SUFFIX) else None,
                     input_window_hash=pv.sha_array(hist[-72:, 0]), raw_prediction_hash=pv.sha_array([x if x is not None else float("nan") for x in pred12]),
                     raw_prediction_first10=[None if x is None else round(float(x), 3) for x in pred12[:10]],
                     cache_hit_training=model.endswith(TRAINED_SUFFIX), inference_recomputed=True, result_source="LIVE_COMPUTATION")
        prov = rec.finish("done")
        base.update(run_id=job, result_source="LIVE_COMPUTATION", cache_hit_training=prov["cache_hit_training"], inference_recomputed=True,
                    provenance=rec.summary())
        actual = base.get("actual")
        metrics = {}
        for h in hz:
            k = h * 60 // step_s - 1
            pv = pred12[k] if pred12 and k < len(pred12) else None
            av = actual[k] if actual and k < len(actual) else None
            last = base["history"][-1] if base["history"] else None
            metrics[h] = {"predicted": pv, "actual": av,
                          "abs_error": round(abs(pv - av), 3) if pv is not None and av is not None else None,
                          "persistence_abs_error": round(abs(last - av), 3) if last is not None and av is not None else None}
        emit(status="done", stage="done", step=5, result={**base, "prediction": pred12, "metrics": metrics})
    except Exception as exc:                            # noqa: BLE001 - shown on the page
        emit(status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")


def start(payload: dict) -> str:
    job = "pl_" + uuid.uuid4().hex[:8]
    with _LOCK:
        _JOBS[job] = {"job": job, "status": "running", "stage": "Loading dataset", "step": 0, "request": payload}
    threading.Thread(target=_run, args=(job, payload), name=job, daemon=True).start()
    return job


def status(job: str) -> dict:
    with _LOCK:
        return dict(_JOBS.get(job) or {"job": job, "status": "unknown"})


# ---------------------------------------------------------------------------- training jobs
_TRAIN: dict[str, dict] = {}


def _train_run(job: str, p: dict) -> None:
    from app.forecasting.training import basicts_train as bt

    def emit(**kw):
        with _LOCK:
            _TRAIN[job].update(kw)
    try:
        card = bt.train(p.get("dataset", ""), p.get("arch", "STID"), int(p.get("epochs", 30)),
                        progress=lambda **k: emit(stage=f"Training — round {k['epoch']} / {k['epochs']}", **k))
        emit(status="done", stage="done", result={k: card[k] for k in ("dataset", "arch", "epochs", "test_metrics", "persistence_test",
                                                                       "curve", "trained_utc", "steps", "nodes", "quantity", "interval_s", "claim", "stack", "trained_on")})
    except BaseException as exc:                        # noqa: BLE001 - SystemExit from the pipeline is a reason, not a crash
        emit(status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")


def train_start(payload: dict) -> str:
    job = "tr_" + uuid.uuid4().hex[:8]
    where = payload.get("where", "cpu")
    with _LOCK:
        _TRAIN[job] = {"job": job, "status": "running", "stage": "Preparing the data", "epoch": 0,
                       "epochs": int(payload.get("epochs", 30)), "request": payload, "where": where}
    threading.Thread(target=_train_cloud_run if where == "aws" else _train_run, args=(job, payload), name=job, daemon=True).start()
    return job


def train_status(job: str) -> dict:
    with _LOCK:
        return dict(_TRAIN.get(job) or {"job": job, "status": "unknown"})


def trained() -> list[dict]:
    from app.forecasting.training import basicts_train as bt
    return [{k: c[k] for k in ("dataset", "arch", "epochs", "test_metrics", "persistence_test", "trained_utc", "steps", "nodes")} for c in bt.cards()]


# ---------------------------------------------------------------------------- the GPU path (AWS)
AWS_VARS = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "AWS_DEFAULT_REGION")


def _aws_env() -> dict | None:
    """The AWS credentials from .env, for the aws CLI the launcher shells out to.
    Server-side only: no endpoint ever returns a value from here."""
    import os
    from app.credentials import load
    env = dict(os.environ)
    for v in AWS_VARS:
        val = env.get(v) or load(v)
        if val:
            env[v] = val
    if not (env.get("AWS_ACCESS_KEY_ID") and env.get("AWS_SECRET_ACCESS_KEY")):
        return None
    env.setdefault("AWS_DEFAULT_REGION", env.get("AWS_REGION", "us-east-1"))
    return env


def cloud() -> dict:
    import shutil
    env = _aws_env()
    ok = bool(env) and shutil.which("aws") is not None
    return {"available": ok, "provider": "aws" if ok else None,
            "instance": "g5.xlarge (1× A10G, 24 GB) — spot first, on-demand if no spot capacity",
            "estimate": "about $0.10–0.50 per run: boot + install ≈ 4 min, then seconds per epoch; the instance terminates itself",
            "why_not": None if ok else ("aws CLI not installed" if env else "no AWS keys in .env")}


def _train_cloud_run(job: str, p: dict) -> None:
    import re
    import time
    from app.forecasting.training import aws_train as at
    from app.forecasting.training import basicts_train as bt

    def emit(**kw):
        with _LOCK:
            _TRAIN[job].update(kw)
    try:
        env = _aws_env()
        if not env:
            raise RuntimeError("no AWS credentials on the server")
        dataset, arch, epochs = p.get("dataset", ""), p.get("arch", "STID"), int(p.get("epochs", 100))
        name = at.city_job_name(dataset)
        emit(stage="Preparing the data and sending it to the cloud", cloud_job=name)
        cmd = [sys.executable, "-m", "app.forecasting.training.aws_train", "--launch", "--city-dataset", dataset,
               "--models", arch, "--epochs", str(epochs), "--allow-on-demand", "--max-hours", "1", "--job", name]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=config.REPO, env=env, timeout=900)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr)[-900:].strip())
        m = re.search(r"\[launch\] (i-[0-9a-f]+) \(([^)]+)\)", r.stdout)
        inst = m.group(1) if m else "?"
        emit(stage="Cloud GPU starting up (a few minutes)", instance=inst)
        import os
        os.environ.update({k: env[k] for k in AWS_VARS if k in env})
        quiet, t0 = 0, time.time()
        while True:
            time.sleep(20)
            st = at.city_poll(name)
            log = st["log"] or ""
            curve = bt.parse_curve(log)
            ep = max([c["epoch"] for c in curve], default=0)
            if st["done"]:
                break
            if "=== TRAIN" in log:
                emit(stage=f"Training on the cloud GPU — round {ep} / {epochs}", epoch=ep, epochs=epochs, curve=curve[-2 * epochs:],
                     line=(log.strip().splitlines() or [""])[-1][-160:])
            elif log:
                emit(stage=f"Cloud GPU up, installing ({int(time.time() - t0)} s)", line=(log.strip().splitlines() or [""])[-1][-160:])
            if not st["instances"]:
                quiet += 1
                if quiet >= 4 and not st["done"]:
                    raise RuntimeError("the instance is gone without a DONE marker (spot reclaimed or boot failure). Log tail:\n" + log[-800:])
            else:
                quiet = 0
            if time.time() - t0 > 3900:
                raise RuntimeError("gave up after 65 min; the watchdog terminates the instance")
        if st["done"].strip() != "DONE":
            raise RuntimeError(f"the job ended with marker {st['done'].strip()!r}. Log tail:\n" + (st["log"] or "")[-800:])
        emit(stage="Bringing the trained model back")
        cards = at.city_collect(name)
        card = next((c for c in cards if c["arch"] == arch), None)
        if not card:
            raise RuntimeError("the job finished but no checkpoint came back")
        emit(status="done", stage="done", result={k: card[k] for k in ("dataset", "arch", "epochs", "test_metrics", "persistence_test",
                                                                       "curve", "trained_utc", "steps", "nodes", "quantity", "interval_s", "claim", "stack", "trained_on")})
    except BaseException as exc:                        # noqa: BLE001
        emit(status="failed", stage="failed", error=f"{type(exc).__name__}: {exc}")
