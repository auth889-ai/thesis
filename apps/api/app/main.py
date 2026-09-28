"""TrafficTwin API — application assembly only. Start with `make app` from the repository root."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core import middleware, settings

app = FastAPI(title="TrafficTwin", version="1.0.0", docs_url=settings.API_DOCS_URL,
              description="Traffic prediction (ML/DL), route optimization, SUMO simulation and V2X networking — for any city.")
app.include_router(api_router)
middleware.install(app)


@app.on_event("startup")
def _startup() -> None:
    """Re-attach training jobs; start the live corridor observatory and the forecast ledger unless disabled (tests)."""
    from traffictwin.forecasting.operations import training_jobs
    try:
        training_jobs.reattach_on_startup()
    except Exception as exc:                            # noqa: BLE001
        print(f"[train] could not re-attach jobs: {exc}")
    if not settings.OBSERVATORY_ENABLED:
        return
    from traffictwin.data.live_providers import observatory
    from traffictwin.protocols.evidence import forecast_ledger
    try:
        forecast_ledger.start_scheduler("dhaka")
        observatory.observatory.start("dhaka")
    except Exception:                                   # noqa: BLE001 - never block startup
        pass


if settings.FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=settings.FRONTEND), name="static")
    if settings.MEDIA.exists():
        app.mount("/media", StaticFiles(directory=settings.MEDIA), name="media")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(settings.FRONTEND / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
