"""Protocol B, served: the regime-stratified comparison (congestion-regime error, onset detection,
lead time) for every model that ran on the same windows. Read from the committed run file, never
recomputed on request; the page says when it was generated and how to regenerate it."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from core.common.paths import REPO

router = APIRouter()
FILE = REPO / "results/forecasting/model_comparison.json"


@router.get("/api/protocol-b/onset", tags=["predict"])
def onset(dataset: str | None = None):
    """Every dataset's Protocol B table, or one dataset's. Rows carry the model name, aggregate and
    congested-regime error at 15 min, F1 of the congestion class, MAE at 60 min, onset detection rate and
    mean lead in minutes; the protocol block states the windows, context, threshold and seed."""
    if not FILE.exists():
        raise HTTPException(503, "no Protocol B run yet: python -m core.ml.forecasting.evaluation.evaluate_models --all")
    from core.ml.forecasting.evaluation.evaluate_models import summary
    runs = json.loads(FILE.read_text())
    names = sorted({r["dataset"] for r in runs})
    if dataset:
        key = dataset.replace("_", "-").upper()                 # the app's dataset id is METR_LA; the run file says METR-LA
        names = [n for n in names if n.upper() == key]
        if not names:
            raise HTTPException(404, f"no Protocol B run for {dataset}")
    out = []
    for name in names:
        s = summary(name)
        rows = []
        for model, agg in sorted(s["models"].items()):
            h15, h60, ol = agg["horizons"].get("15", {}), agg["horizons"].get("60", {}), agg["onset_lead"]
            g = lambda d, k: (d.get(k) or {}).get("mean")
            sd = lambda d, k: (d.get(k) or {}).get("std")
            rows.append({"model": model, "n_seeds": agg["n_seeds"], "mae_15": g(h15, "mae"), "mae_15_std": sd(h15, "mae"),
                         "congestion_mae_15": g(h15, "congestion_mae"), "congestion_mae_15_std": sd(h15, "congestion_mae"),
                         "congestion_f1_15": g(h15, "congestion_f1"), "mae_60": g(h60, "mae"),
                         "onset_detection_rate": g(ol, "detection_rate"), "onset_detection_rate_std": sd(ol, "detection_rate"),
                         "mean_lead_min": g(ol, "mean_lead_min")})
        latest = max((r for r in runs if r["dataset"] == name), key=lambda r: r["generated_utc"])
        out.append({"dataset": name, "generated_utc": latest["generated_utc"], "nodes": s["nodes"], "seeds": s["seeds"],
                    "protocol": {**s["protocol"], "seeds": s["seeds"]}, "rows": rows,
                    "source": "results/forecasting/model_comparison.json",
                    "regenerate": "python -m core.ml.forecasting.evaluation.evaluate_models --dataset <name> --windows 120 --seed <s> --max-nodes 0"})
    return {"datasets": out}


CONFORMAL = REPO / "results/forecasting/conformal.json"


@router.get("/api/protocol-b/conformal", tags=["predict"])
def conformal(dataset: str | None = None):
    """Coverage and width of 90 % intervals per model and horizon under three calibrators (global,
    regime-aware, predicted-regime), on all test windows, in free flow, in congestion and at the
    transition. Read from the committed run file."""
    if not CONFORMAL.exists():
        raise HTTPException(503, "no conformal run yet: python -m core.ml.forecasting.evaluation.conformal --dataset <name>")
    from core.ml.forecasting.evaluation.conformal import summary
    runs = json.loads(CONFORMAL.read_text())
    names = sorted({r["dataset"] for r in runs})
    if dataset:
        key = dataset.replace("_", "-").upper()
        names = [n for n in names if n.upper() == key]
        if not names:
            raise HTTPException(404, f"no conformal run for {dataset}")
    return {"datasets": [{**summary(n), "source": "results/forecasting/conformal.json",
                          "regenerate": "python -m core.ml.forecasting.evaluation.conformal --dataset <name> --nodes 207 --seed <s>"} for n in names]}


@router.get("/api/protocol-b/departure", tags=["predict"])
def departure(src: str, dst: str, as_of: int = 20000, model: str | None = None, deadline_min: int | None = None):
    """Leave when? Shortest sensor corridor from `src` to `dst`, the served model's forecast per leg at the horizon the
    traveller reaches it, the 90 % worst case from the calibrated half-widths, and the latest departure for a deadline."""
    from core.ml.forecasting.operations import departure as dep
    try:
        return dep.advise(src, dst, as_of, model, deadline_min)
    except (ValueError, KeyError) as ex:
        raise HTTPException(422, str(ex))
    except Exception as ex:                                             # noqa: BLE001 - no path, unknown sensor
        if "No path" in str(ex) or "not in G" in str(ex) or "NodeNotFound" in type(ex).__name__ or "NetworkXNoPath" in type(ex).__name__:
            raise HTTPException(404, f"no corridor between {src} and {dst}: {ex}")
        raise


@router.get("/api/protocol-b/sensors", tags=["predict"])
def sensors():
    """The METR-LA sensors with their release coordinates, for picking a corridor."""
    from core.ml.forecasting.operations import departure as dep
    _, _, locs = dep.sensor_graph()
    return {"dataset": "METR-LA", "sensors": locs}


IMPUTATION = REPO / "results/forecasting/imputation.json"


@router.get("/api/protocol-b/imputation", tags=["predict"])
def imputation():
    """Sparse sensing: the imputation run (25 % point missing, scored on hidden points) with its published counterparts."""
    if not IMPUTATION.exists():
        raise HTTPException(503, "no imputation run yet: USE_TF=0 python -m core.ml.forecasting.evaluation.imputation")
    return {**json.loads(IMPUTATION.read_text()), "source": "results/forecasting/imputation.json",
            "regenerate": "USE_TF=0 python -m core.ml.forecasting.evaluation.imputation --epochs <n>"}
