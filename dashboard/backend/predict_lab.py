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

import config

sys.path.insert(0, str(config.REPO))
HORIZONS = [5, 15, 30, 60]
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
CHECKPOINT_MODELS = {"GWNet": ("GWNet", {"METR_LA": "METR-LA", "PEMS_BAY": "PEMS-BAY"}),
                     "STID": ("STID", {"METR_LA": "METR-LA", "PEMS_BAY": "PEMS-BAY"})}


def _live_datasets() -> list[dict]:
    import observatory as obs_mod
    out = []
    for cid in obs_mod.observatory.cities():
        r = obs_mod.observatory.readiness(cid)
        if r["steps_have"] < 1:
            continue
        rows, nodes = obs_mod.observatory.series(cid)
        names = list(nodes)
        if cid == "dhaka":
            import corridors as cz
            names = [cz.BY_ID.get(n, {}).get("name", n) for n in nodes]
        else:
            import city_corridors
            byid = {c["id"]: c for c in city_corridors.load(cid)}
            names = [byid.get(n, {}).get("name", n) for n in nodes]
        out.append({"id": f"live:{cid}", "name": f"{cid.replace('_', ' ').title()} — live corridors ({len(nodes)}), sampled every 5 min",
                    "node_names": names,
                    "nodes": len(nodes), "steps": r["steps_have"], "start_utc": rows[0]["utc"] if rows else None,
                    "interval_min": 5, "exposure": "HELD_OUT_ZERO_SHOT", "live": True,
                    "models": (["OpenCity-plus"] if r["steps_have"] >= 288 and len(nodes) >= 9 else [])
                              + (["Chronos-Bolt"] if r["steps_have"] >= 8 else []) + ["persistence"]})
    return out


def datasets() -> list[dict]:
    from pipeline.forecasting import opencity_predict as op
    out = op.local_datasets()
    live = _live_datasets()
    for d in out:
        d["models"] = ["OpenCity-plus", "Chronos-Bolt", "persistence"] + \
                      [m for m, (_, ds) in CHECKPOINT_MODELS.items() if d["id"] in ds]
        d["name"] = {"METR_LA": "Los Angeles — METR-LA (207 loop detectors)", "PEMS_BAY": "Bay Area — PEMS-BAY (325 detectors)",
                     "PEMS07M": "California D7 — PEMS07M (228 detectors)", "TrafficSH": "Shanghai — TrafficSH (896 regions)"}.get(d["id"], d["id"])
    import user_datasets
    return user_datasets.datasets() + live + out


def _series(dataset: str, region: int, n_nodes: int):
    if dataset.startswith("user:"):
        import user_datasets
        return user_datasets.series(dataset.split(":", 1)[1], region)
    if dataset.startswith("live:"):
        import numpy as np
        import observatory as obs_mod
        cid = dataset.split(":", 1)[1]
        cd = obs_mod.observatory.city_data(cid)
        vals = np.asarray(cd.values, dtype="float64")
        order = [region] + [i for i in range(vals.shape[1]) if i != region]
        rows, _ = obs_mod.observatory.series(cid)
        return vals[:, order], [cd.node_ids[i] for i in order], np.eye(len(order), dtype="float32"), {
            "quantity": "corridor mean speed, m/s (derived by us)", "reality": "REAL_LIVE",
            "first_utc": rows[0]["utc"] if rows else None, "region_index": region, "subgraph": order}
    from pipeline.forecasting import opencity_predict as op
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
            emit(stage="Running forward pass (OpenCity-plus, 26M parameters, CPU)", step=3)
            out = Path(tempfile.mkdtemp(prefix="oc_")) / "p.json"
            if dataset.startswith("user:"):               # their CSV contract, the whole uploaded graph
                import user_datasets
                pp = user_datasets.paths(dataset.split(":", 1)[1])
                cmd = [sys.executable, str(config.REPO / "pipeline/forecasting/opencity_predict.py"),
                       "--source", "csv", "--csv", str(pp["csv"]), "--adj", str(pp["adj"]),
                       "--as-of", str(end), "--horizons", "15,30,60", "--out", str(out)]
            else:
                cmd = [sys.executable, str(config.REPO / "pipeline/forecasting/opencity_predict.py"),
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
        elif model in CHECKPOINT_MODELS:
            cli, ds_map = CHECKPOINT_MODELS[model]
            if dataset not in ds_map:
                raise RuntimeError(f"{model} has a trained checkpoint only for {list(ds_map)}")
            emit(stage=f"Running forward pass ({model} checkpoint)", step=3)
            n_train = int(T * 0.7); test_lo = n_train + int(T * 0.1)
            window = max(0, end - 12 - test_lo)          # the script's window starts its 12 input steps at test_lo + window
            cmd = [sys.executable, str(config.REPO / "pipeline/forecasting/infer_from_checkpoint.py"),
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
            emit(stage=f"Running forward pass ({model})", step=3)
            from pipeline.forecasting.adapters.base import CityData
            from pipeline.forecasting.adapters.registry import forecast as run_forecast
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
                                  "stack": "the common forecast interface (pipeline/forecasting/adapters)",
                                  "claim": "univariate zero-shot" if model == "Chronos-Bolt" else "the floor"}
        emit(stage="Scoring", step=4)
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
