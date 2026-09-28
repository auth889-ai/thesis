"""Model prototypes HTTP endpoints."""
from __future__ import annotations

import json
import sys
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from pathlib import Path
from backend.app import config
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/opencity/{city_id}", tags=["predict"])
def opencity_status(city_id: str):
    """Where the foundation model stands for this city, in the model's own terms.

    OpenCity runs through the authors' harness as a batch job. This reports how much of the
    history it needs has accumulated (the persisted observatory window), whether the CPU path has
    been verified, and the result once the run exists — never a fabricated number in between.
    """
    import sys
    sys.path.insert(0, str(config.REPO))
    from traffictwin.forecasting.opencity import opencity_city_eval as oce
    return oce.readiness(city_id)


def _opencity_predict(args: list[str]) -> dict:
    """Run the authors' stack in a subprocess (it chdirs and rewrites argv) and return its JSON."""
    import subprocess
    import sys as _sys
    import tempfile
    out = Path(tempfile.mkdtemp(prefix="opencity_")) / "prediction.json"
    cmd = [_sys.executable, str(config.REPO / "src/pipeline/forecasting/opencity_predict.py"), *args,
           "--out", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=config.REPO)
    if proc.returncode != 0 or not out.exists():
        tail = (proc.stderr or proc.stdout or "")[-1200:]
        return {"ok": False, "error": tail.strip().splitlines()[-1] if tail.strip() else "no output",
                "log_tail": tail}
    return {"ok": True, **json.loads(out.read_text())}


@router.post("/api/opencity/{city_id}/predict", tags=["predict"])
def opencity_predict_city(city_id: str, payload: dict | None = None):
    """OpenCity-plus forward pass on this city's own window (persisted observatory speeds by
    default, or the recorded classes), through the authors' unmodified stack. Refuses, with the
    model's own reason, when the window is too short or the graph too small."""
    p = payload or {}
    args = ["--source", str(p.get("source", "observatory")), "--city", city_id,
            "--horizons", str(p.get("horizons", "15,30,60"))]
    if p.get("as_of") is not None:
        args += ["--as-of", str(int(p["as_of"]))]
    return _opencity_predict(args)


@router.post("/api/opencity/upload", tags=["predict"])
async def opencity_predict_upload(csv: UploadFile = File(...), adj: UploadFile = File(...),
                                  horizons: str = Form("15,30,60"), as_of: str = Form("")):
    """Their demo's contract: a CSV (`time` + one column per region) and an `_rn_adj.npy`."""
    import tempfile
    d = Path(tempfile.mkdtemp(prefix="opencity_upload_"))
    csv_path, adj_path = d / "city.csv", d / "city_rn_adj.npy"
    csv_path.write_bytes(await csv.read()); adj_path.write_bytes(await adj.read())
    args = ["--source", "csv", "--csv", str(csv_path), "--adj", str(adj_path), "--horizons", horizons]
    if as_of.strip():
        args += ["--as-of", as_of.strip()]
    return _opencity_predict(args)
