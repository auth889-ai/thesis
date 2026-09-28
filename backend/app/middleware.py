"""HTTP middleware: the interface is ES modules, so static files are never cached (a reload shows the current code)."""
from fastapi import FastAPI, Request


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def _no_stale_frontend(request: Request, call_next):
        resp = await call_next(request)
        if not request.url.path.startswith(("/api", "/media")):
            resp.headers["Cache-Control"] = "no-store"
        return resp
