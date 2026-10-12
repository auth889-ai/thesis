"""RQ1 forecasting results for the Research page: the summary built by `python -m core.ml.forecasting.transfer_dhaka.run summary` and its figures.
Nothing is computed on request; a missing file is said plainly."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from core.common.paths import REPO

OUT = REPO / "results/forecasting/rq1"          # the same folder as core.ml.forecasting.transfer_dhaka.run.OUT; importing that module would load pandas,
router = APIRouter()                             # which the hosted app does not install (it crashed the hosted app on 2026-10-08)


@router.get("/api/forecasting/rq1", tags=["forecasting"])
def rq1_summary():
    p = OUT / "summary.json"
    if not p.exists():
        return {"available": False, "note": "RQ1 has not been run yet: research/forecasting_rq1/scripts/01_protocol_b.sh"}
    return {"available": True, **json.loads(p.read_text())}


@router.get("/api/forecasting/rq1/figures/{name}", tags=["forecasting"])
def rq1_figure(name: str):
    p = (OUT / "figures" / name).resolve()
    if p.parent != (OUT / "figures").resolve() or p.suffix != ".png" or not p.exists():
        raise HTTPException(404, "no such figure")
    return FileResponse(p, media_type="image/png")
