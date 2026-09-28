"""TrafficTwin — application assembly only. Run from the repository root with `make app`."""
from __future__ import annotations

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, middleware
from app.router import api_router

app = FastAPI(title="TrafficTwin", version="1.0.0", docs_url=config.API_DOCS_URL,
              description="Traffic prediction (ML/DL), route optimization, SUMO simulation and V2X networking — for any city.")
app.include_router(api_router)
middleware.install(app)


@app.on_event("startup")
def _startup() -> None:
    """Re-attach training jobs; start the live corridor observatory and the forecast ledger unless disabled (tests)."""
    from app.forecasting.operations import training_jobs
    try:
        training_jobs.reattach_on_startup()
    except Exception as exc:                            # noqa: BLE001
        print(f"[train] could not re-attach jobs: {exc}")
    if not config.OBSERVATORY_ENABLED:
        return
    from app.data.live_providers import observatory
    from app.protocols.evidence import forecast_ledger
    try:
        forecast_ledger.start_scheduler("dhaka")
        observatory.observatory.start("dhaka")
    except Exception:                                   # noqa: BLE001 - never block startup
        pass


if config.FRONTEND.exists():
    if config.MEDIA.exists():
        app.mount("/media", StaticFiles(directory=config.MEDIA), name="media")
    app.mount("/static", StaticFiles(directory=config.FRONTEND), name="static")          # kept for older links

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.FRONTEND / "index.html")

    class SPAStaticFiles(StaticFiles):
        """The web app routes in the browser (/today, /mobility, ...): an unknown path without a file
        extension gets index.html so a deep link or a refresh lands on the page, never a 404."""
        async def get_response(self, path, scope):
            try:
                return await super().get_response(path, scope)
            except HTTPException as exc:
                if exc.status_code == 404 and "." not in path.rsplit("/", 1)[-1] and not path.startswith("api/"):
                    return await super().get_response("index.html", scope)
                raise

    app.mount("/", SPAStaticFiles(directory=config.FRONTEND), name="web")                 # the app's own relative assets (last: API routes win)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
