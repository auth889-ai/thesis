"""Rate limits for the hosted app (Q5): on only when TRAFFICTWIN_HOSTED=1, so the laptop and the tests are unchanged.

Per visitor (the client address Caddy passes in X-Forwarded-For; the direct peer otherwise):
  - the routing calls that reach the city's Valhalla server (navigation proxy, whole-city routes, signal prediction, nearest
    hospital, isochrones): ROUTING_PER_MIN per minute;
  - simulation starts (3D City live run, ambulance run): SIMS_PER_HOUR per hour; the runtime itself runs one for the whole site,
    caps a hosted run at 30 simulated minutes and stops it after 10 minutes of real time (core.simulation.twin.live.runtime);
  - live twin starts: TWINS_PER_DAY per day; one twin per visitor, stopped when idle (core.simulation.live_twin.manager);
  - "Add your city" builds (POST /api/cities, each one Overpass request to the public OpenStreetMap server): BUILDS_PER_DAY per day,
    on top of the app-wide DAILY_BUILDS limit in core.common.data.city_builds.
A refused request gets 429 with Retry-After and a sentence saying which limit it hit. Counts are kept in memory (one process)."""
from __future__ import annotations

import os
import re
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

ROUTING_PER_MIN = 30
BUILDS_PER_DAY = 2
ROUTING = re.compile(r"^/api/(navigate/[^/]+/route|route/[^/]+(/signal)?|emergency/reach/[^/]+/(nearest|isochrone|live))$")
BUILD = ("POST", "/api/cities")
SIM_STARTS = {("POST", "/api/sim/live/start"), ("POST", "/api/emergency/runs")}
SIMS_PER_HOUR = 6
LIVE_JOB = re.compile(r"^/api/live/(v2x|sos|mesh|signals)$")
LIVE_PER_DAY = 6                     # live simulations from the map (core/simulation/live_jobs), per visitor per day
LIVE_TWIN = re.compile(r"^/api/live-twin/[^/]+/start$")
TWINS_PER_DAY = 10                   # live twin starts per visitor per day (each visitor has at most one running; core/simulation/live_twin)


def hosted() -> bool:
    return os.environ.get("TRAFFICTWIN_HOSTED") == "1"


class Limiter:
    """Sliding windows of request times per (visitor, rule)."""
    def __init__(self):
        self.hits: dict[tuple[str, str], list[float]] = {}
        self.lock = threading.Lock()

    def allow(self, who: str, rule: str, limit: int, window_s: float, now: float | None = None) -> float:
        """0 when allowed (and counted), else the seconds until the oldest hit leaves the window."""
        now = time.time() if now is None else now
        with self.lock:
            q = [t for t in self.hits.get((who, rule), []) if now - t < window_s]
            if len(q) >= limit:
                self.hits[(who, rule)] = q
                return max(1.0, window_s - (now - q[0]))
            q.append(now)
            self.hits[(who, rule)] = q
            return 0.0


LIMITER = Limiter()


def visitor(request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


class RateLimit(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if not hosted():
            return await call_next(request)
        path, who = request.url.path, visitor(request)
        if (request.method, path) == BUILD:
            wait = LIMITER.allow(who, "build", BUILDS_PER_DAY, 86400)
            if wait:
                return JSONResponse(status_code=429, headers={"Retry-After": str(int(wait))},
                                    content={"error": f"rate_limited: at most {BUILDS_PER_DAY} new cities per visitor per day on the hosted app", "retry_after_s": int(wait)})
        elif (request.method, path) in SIM_STARTS:
            wait = LIMITER.allow(who, "sim", SIMS_PER_HOUR, 3600)
            if wait:
                return JSONResponse(status_code=429, headers={"Retry-After": str(int(wait))},
                                    content={"error": f"rate_limited: at most {SIMS_PER_HOUR} simulations per visitor per hour on the hosted app (one runs at a time for the whole site)", "retry_after_s": int(wait)})
        elif request.method == "POST" and LIVE_JOB.match(path):
            wait = LIMITER.allow(who, "live", LIVE_PER_DAY, 86400)
            if wait:
                return JSONResponse(status_code=429, headers={"Retry-After": str(int(wait))},
                                    content={"error": f"rate_limited: at most {LIVE_PER_DAY} live simulations per visitor per day on the hosted app (one runs at a time for the whole site)", "retry_after_s": int(wait)})
        elif request.method == "POST" and LIVE_TWIN.match(path):
            wait = LIMITER.allow(who, "twin", TWINS_PER_DAY, 86400)
            if wait:
                return JSONResponse(status_code=429, headers={"Retry-After": str(int(wait))},
                                    content={"error": f"rate_limited: at most {TWINS_PER_DAY} live twin starts per visitor per day on the hosted app (one twin per visitor)", "retry_after_s": int(wait)})
        elif ROUTING.match(path):
            wait = LIMITER.allow(who, "routing", ROUTING_PER_MIN, 60)
            if wait:
                return JSONResponse(status_code=429, headers={"Retry-After": str(int(wait))},
                                    content={"error": f"rate_limited: at most {ROUTING_PER_MIN} route requests per minute on the hosted app", "retry_after_s": int(wait)})
        return await call_next(request)
