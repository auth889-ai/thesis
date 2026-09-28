"""TrafficTwin application assembly. Start with make app from the repository root."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from traffictwin.common import evidence_paths as config
from traffictwin.data.live_providers import observatory as observatory_mod
from traffictwin.protocols.evidence import forecast_ledger as forecast_log
from app.api import research, panels, live_reference, cities, predictions, model_prototypes, experiments, v2x, simulation, training, operations, system, stress, references


app = FastAPI(title="TrafficTwin", version="1.0.0", docs_url="/api/docs",
              description="Traffic prediction (ML/DL), route optimization, SUMO simulation and V2X networking — for any city.")


for router_module in (research, panels, live_reference, cities, predictions, model_prototypes, experiments, v2x, simulation, training, operations, system, stress, references):
    app.include_router(router_module.router)


@app.middleware("http")
async def _no_stale_frontend(request: Request, call_next):
    """The interface is ES modules; a browser that caches them shows yesterday's app after every
    change. Static files are always revalidated, so a plain reload shows the current code."""
    resp = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path in ("/", "/index.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.on_event("startup")
def _start_observatory() -> None:
    """Begin accumulating the rolling window as soon as the server is up.

    The buffer only means anything if it is filling, and the audit's finding was that it never
    could. Starting it here is what makes readiness a real countdown: leave the server running and
    the 288-step window fills in about a day. Sampling is off by default in tests, where a live
    API call per tick would be both slow and pointless.
    """
    from traffictwin.forecasting.operations import training_jobs as train_jobs
    try:
        train_jobs.reattach_on_startup()
    except Exception as exc:                            # noqa: BLE001
        print(f"[train] could not re-attach jobs: {exc}")
    import os
    if os.environ.get("DHAKAFLOW_NO_OBSERVATORY"):
        return
    try:
        forecast_log.start_scheduler("dhaka")
        observatory_mod.observatory.start("dhaka")
    except Exception:                              # noqa: BLE001 - never block startup
        pass


FRONTEND = config.FRONTEND


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
    if (config.REPO / "docs/media").exists():
        app.mount("/media", StaticFiles(directory=config.REPO / "docs/media"), name="media")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(FRONTEND / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("DhakaFlow -> http://127.0.0.1:8000    docs -> /api/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
