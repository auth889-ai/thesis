"""TrafficTwin — application assembly only. Run from the repository root with `make app`."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.exceptions import HTTPException
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import config, middleware
from app.router import api_router

@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Startup work, then the MCP session manager for as long as the API runs."""
    from app.mcp import server as mcp_server
    _startup()
    async with mcp_server.lifespan():
        yield


app = FastAPI(title="TrafficTwin", version="1.0.0", docs_url=config.API_DOCS_URL, lifespan=_lifespan,
              description="Traffic prediction (ML/DL), route optimization, SUMO simulation and V2X networking — for any city.")
app.include_router(api_router)
middleware.install(app)
from app.platform.ratelimit import RateLimit  # noqa: E402 - the hosted app's limits (on only with TRAFFICTWIN_HOSTED=1)
app.add_middleware(RateLimit)


def _warm_model_lab() -> None:
    """Hosted app only (TRAFFICTWIN_HOSTED=1): one Model Lab forecast in the background when the service starts, so torch and the
    checkpoint are loaded before the first visitor (the first call pays for both; owner, 2026-10-10). Never blocks or fails startup."""
    import os
    import threading
    import time
    if os.environ.get("TRAFFICTWIN_HOSTED") != "1":
        return

    def warm():
        t0 = time.time()
        try:
            from core.ml.forecasting.layer import lab
            first = lab.sensors()["first"]
            r = lab.run(0, first, "D2STGNN")
            print(f"[model-lab] warm-up: {'ok' if r.get('ok') else r.get('error')} in {time.time() - t0:.1f} s", flush=True)
        except BaseException as exc:                    # noqa: BLE001 - SystemExit from a research loader included: logged, never raised
            print(f"[model-lab] warm-up skipped: {type(exc).__name__}: {exc}", flush=True)
    threading.Thread(target=warm, daemon=True, name="model-lab-warm-up").start()


def _startup() -> None:
    """Re-attach training jobs; start the live corridor observatory and the forecast ledger unless disabled (tests)."""
    from app.lifeos import db as lifeos_db
    try:
        lifeos_db.init()                                # the core store is always at the current migration
    except Exception as exc:                            # noqa: BLE001
        print(f"[lifeos] migration failed: {exc}")
    from core.ml.forecasting.operations import training_jobs
    try:
        training_jobs.reattach_on_startup()
    except Exception as exc:                            # noqa: BLE001
        print(f"[train] could not re-attach jobs: {exc}")
    _warm_model_lab()
    if not config.OBSERVATORY_ENABLED:
        return
    from app.plan import monitor
    monitor.start()                                     # the watch on every person's day
    from app.agent import router as agent_router, worker
    worker.start(agent_router._llm_or_503)              # recover goals a previous process left running, then reap every 30 s
    from core.common.data.live_providers import observatory
    from core.simulation.closed_loop.protocols.evidence import forecast_ledger
    try:
        forecast_ledger.start_scheduler("dhaka")
        observatory.observatory.start("dhaka")
    except Exception:                                   # noqa: BLE001 - never block startup
        pass


from starlette.routing import Route                                                    # noqa: E402
from app.mcp import server as _mcp                                                    # noqa: E402
app.router.routes.append(Route("/mcp", _mcp.endpoint, methods=["GET", "POST", "DELETE"], name="mcp"))   # MCP over Streamable HTTP (Alexa+ and other agents)

if config.FRONTEND.exists():
    if config.MEDIA.exists():
        app.mount("/media", StaticFiles(directory=config.MEDIA), name="media")
    app.mount("/static", StaticFiles(directory=config.FRONTEND), name="static")          # kept for older links

    NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}      # index.html names the hashed bundle: a cached copy shows yesterday's app

    ASSET_EXT = {"js", "mjs", "css", "map", "png", "jpg", "jpeg", "gif", "svg", "ico", "webp", "json", "pbf", "mvt", "wasm", "woff", "woff2", "ttf", "txt", "webmanifest", "xml", "pmtiles"}

    class SPAStaticFiles(StaticFiles):
        """A web app that routes in the browser: an unknown path without a file extension gets index.html so a deep link or a
        refresh lands on the page, never a 404."""
        async def get_response(self, path, scope):
            try:
                r = await super().get_response(path, scope)
                if path in ("", ".", "index.html", "sw.js"):
                    r.headers.update(NO_CACHE)
                return r
            except HTTPException as exc:
                last = path.rsplit("/", 1)[-1].lower()
                asset = last.rsplit(".", 1)[-1] in ASSET_EXT if "." in last else False   # a place id or "lat,lng" has dots; a file has a known extension
                if exc.status_code == 404 and not asset and not path.startswith("api/"):
                    r = await super().get_response("index.html", scope)
                    r.headers.update(NO_CACHE)
                    return r
                raise

    # The everyday pages, Research, 3D City and the simulations (React): under /app/; the map app's menus open them.
    app.mount("/app", SPAStaticFiles(directory=config.FRONTEND, html=True), name="web")
    OLD = ("trip", "3d", "add-city", "emergency", "offline", "settings", "today", "plan", "goals", "messages", "map", "city", "activity", "you-lifeos", "lab")

    def old_link(request: Request):
        """A link from before the map app (/emergency, /lab/evidence, ...) opens the same page under /app/."""
        q = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(f"/app{request.url.path}{q}", status_code=308)

    for p in OLD:
        app.add_api_route(f"/{p}", old_link, include_in_schema=False)
        app.add_api_route(f"/{p}/{{rest:path}}", old_link, include_in_schema=False)
    app.mount("/", SPAStaticFiles(directory=config.MAP_APP if (config.MAP_APP / "index.html").exists() else config.FRONTEND, html=True), name="map")   # last: API routes win

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
