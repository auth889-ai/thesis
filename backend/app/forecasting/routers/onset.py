"""Protocol B, served: the regime-stratified comparison (congestion-regime error, onset detection,
lead time) for every model that ran on the same windows. Read from the committed run file, never
recomputed on request; the page says when it was generated and how to regenerate it."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.paths import REPO

router = APIRouter()
FILE = REPO / "results/forecasting/model_comparison.json"


@router.get("/api/protocol-b/onset", tags=["predict"])
def onset(dataset: str | None = None):
    """Every dataset's Protocol B table, or one dataset's. Rows carry the model name, aggregate and
    congested-regime error at 15 min, F1 of the congestion class, MAE at 60 min, onset detection rate and
    mean lead in minutes; the protocol block states the windows, context, threshold and seed."""
    if not FILE.exists():
        raise HTTPException(503, "no Protocol B run yet: python -m app.forecasting.evaluation.evaluate_models --all")
    runs = json.loads(FILE.read_text())
    if dataset:
        key = dataset.replace("_", "-").upper()                 # the app's dataset id is METR_LA; the run file says METR-LA
        runs = [r for r in runs if r["dataset"].upper() == key]
        if not runs:
            raise HTTPException(404, f"no Protocol B run for {dataset}")
    out = []
    for r in runs:
        rows = []
        for name, res in sorted(r["results"].items()):
            h15, h60, ol = res["horizons"].get("15", res["horizons"].get(15, {})), res["horizons"].get("60", res["horizons"].get(60, {})), res["onset_lead"]
            rows.append({"model": name, "mae_15": h15.get("mae"), "congestion_mae_15": h15.get("congestion_mae"),
                         "congestion_f1_15": h15.get("congestion_f1"), "mae_60": h60.get("mae"),
                         "onset_detection_rate": ol.get("detection_rate"), "mean_lead_min": ol.get("mean_lead_min")})
        out.append({"dataset": r["dataset"], "generated_utc": r["generated_utc"], "nodes": r["nodes"],
                    "protocol": r["protocol"], "rows": rows,
                    "source": "results/forecasting/model_comparison.json",
                    "regenerate": "python -m app.forecasting.evaluation.evaluate_models --dataset <name> --windows 120 --seed 11 --max-nodes 80"})
    return {"datasets": out}


CONFORMAL = REPO / "results/forecasting/conformal.json"


@router.get("/api/protocol-b/conformal", tags=["predict"])
def conformal(dataset: str | None = None):
    """Coverage and width of 90 % intervals per model and horizon under three calibrators (global,
    regime-aware, predicted-regime), on all test windows, in free flow, in congestion and at the
    transition. Read from the committed run file."""
    if not CONFORMAL.exists():
        raise HTTPException(503, "no conformal run yet: python -m app.forecasting.evaluation.conformal --dataset <name>")
    runs = json.loads(CONFORMAL.read_text())
    if dataset:
        key = dataset.replace("_", "-").upper()
        runs = [r for r in runs if r["dataset"].upper() == key]
        if not runs:
            raise HTTPException(404, f"no conformal run for {dataset}")
    return {"datasets": [{**r, "source": "results/forecasting/conformal.json",
                          "regenerate": "python -m app.forecasting.evaluation.conformal --dataset <name>"} for r in runs]}
