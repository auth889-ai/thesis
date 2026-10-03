"""Training HTTP endpoints."""
from __future__ import annotations

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from app.forecasting.operations import prediction_jobs as predict_lab
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/predict-lab/datasets", tags=["predict"])
def predict_lab_datasets(uploads: bool = True):
    """Real datasets present locally and the models that can serve each: live cities, then benchmarks; `uploads=false`
    leaves out a person's own uploads (the City page), which the Lab's Data tab lists."""
    return {"datasets": predict_lab.datasets(include_uploads=uploads)}


@router.post("/api/predict-lab/upload", tags=["predict"])
async def predict_lab_upload(csv: UploadFile = File(...), name: str = Form("my city"), quantity: str = Form("speed_kmh"),
                             adj: UploadFile | None = File(None), coords: UploadFile | None = File(None)):
    """Any city, your data: a CSV (wide `time,<road>...` or long `time,road,value`), optionally a
    coordinates CSV or an adjacency `.npy`, becomes a dataset every model on the page can serve."""
    from app.data import uploads as user_datasets
    try:
        meta = user_datasets.save(name, await csv.read(), quantity,
                                  adj_bytes=(await adj.read()) if adj and adj.filename else None,
                                  coords_bytes=(await coords.read()) if coords and coords.filename else None)
    except Exception as exc:                            # noqa: BLE001 - the page shows the reason
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "dataset": f"user:{meta['id']}", "meta": meta, "models": user_datasets.models_for(meta)}


@router.post("/api/predict-lab/run", tags=["predict"])
def predict_lab_run(payload: dict):
    """A real forward pass: dataset, region, moment, model -> prediction, scored where possible."""
    return {"job": predict_lab.start(payload or {}), "poll": "/api/predict-lab/{job}"}


@router.post("/api/predict-lab/train", tags=["predict"])
def predict_lab_train(payload: dict):
    """Train an official BasicTS baseline (STID / GWNet) on THIS dataset — their data preparation,
    config, runner and metrics, on CPU. Returns a job to poll; the model then appears in the menu."""
    return {"job": predict_lab.train_start(payload or {}), "poll": "/api/predict-lab/train/{job}"}


@router.get("/api/predict-lab/train/{job}", tags=["predict"])
def predict_lab_train_status(job: str):
    return predict_lab.train_status(job)


@router.post("/api/train", tags=["train"])
def train_create(payload: dict):
    """Create a training job. Policy: small jobs run here, larger ones on an AWS single-GPU worker
    (unless `where` pins it). Returns the job id to poll."""
    from app.forecasting.operations import training_jobs as train_jobs
    try:
        return train_jobs.start(payload or {})
    except ValueError as exc:
        return {"error": str(exc)}


@router.get("/api/train", tags=["train"])
def train_list():
    from app.forecasting.operations import training_jobs as train_jobs
    return {"jobs": train_jobs.list_jobs()}


@router.get("/api/train/{job_id}", tags=["train"])
def train_status(job_id: str):
    """Stage (QUEUED … COMPLETE | FAILED), epoch and validation metrics while training, then the
    validation / test tables, checkpoint verification and the trust gate."""
    from app.forecasting.operations import training_jobs as train_jobs
    j = train_jobs.get(job_id)
    if j.get("status") == "done" and not j.get("identity"):
        j["identity"] = train_jobs.identity_for(job_id)          # the causal-chain record of a finished job
    return j


@router.post("/api/train/{job_id}/cancel", tags=["train"])
def train_cancel(job_id: str):
    """Stop a job; a cloud worker is terminated immediately."""
    from app.forecasting.operations import training_jobs as train_jobs
    return train_jobs.cancel(job_id)


@router.get("/api/predict-lab/cloud", tags=["predict"])
def predict_lab_cloud():
    """Whether the GPU path is configured (AWS keys on the server, aws CLI present). Never a key value."""
    return predict_lab.cloud()


@router.get("/api/predict-lab/trained", tags=["predict"])
def predict_lab_trained():
    """Models trained here, with their test metrics beside persistence on the same split."""
    return {"trained": predict_lab.trained()}


@router.get("/api/predict-lab/{job}", tags=["predict"])
def predict_lab_status(job: str):
    return predict_lab.status(job)
