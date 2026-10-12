"""Hosted-app rate limits: off on the laptop; on with TRAFFICTWIN_HOSTED=1, per visitor (X-Forwarded-For), 429 with Retry-After."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.platform import ratelimit


def test_window_counts_and_refuses():
    lim = ratelimit.Limiter()
    assert all(lim.allow("a", "r", 3, 60, now=100 + i) == 0 for i in range(3))
    assert lim.allow("a", "r", 3, 60, now=104) > 0
    assert lim.allow("b", "r", 3, 60, now=104) == 0                       # another visitor is not affected
    assert lim.allow("a", "r", 3, 60, now=161) == 0                       # the window moved on


def test_routing_limited_only_when_hosted(monkeypatch):
    monkeypatch.setattr(ratelimit, "LIMITER", ratelimit.Limiter())
    c = TestClient(app)
    url = "/api/route/nowhere?origin=1,2&destination=1,3"
    assert all(c.get(url).status_code != 429 for _ in range(ratelimit.ROUTING_PER_MIN + 5))   # laptop: no limit
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    codes = [c.get(url, headers={"X-Forwarded-For": "203.0.113.7"}).status_code for _ in range(ratelimit.ROUTING_PER_MIN + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]
    r = c.get(url, headers={"X-Forwarded-For": "203.0.113.7"})
    assert r.status_code == 429 and int(r.headers["retry-after"]) >= 1 and "route requests per minute" in r.json()["error"]
    assert c.get(url, headers={"X-Forwarded-For": "198.51.100.9"}).status_code != 429


def test_city_builds_per_visitor_per_day(monkeypatch):
    monkeypatch.setattr(ratelimit, "LIMITER", ratelimit.Limiter())
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    lim = ratelimit.LIMITER
    assert lim.allow("v", "build", ratelimit.BUILDS_PER_DAY, 86400) == 0 and lim.allow("v", "build", ratelimit.BUILDS_PER_DAY, 86400) == 0
    r = TestClient(app).post("/api/cities", json={}, headers={"X-Forwarded-For": "v"})
    assert r.status_code == 429 and "new cities per visitor per day" in r.json()["error"]


def test_simulation_starts_limited_and_capped_when_hosted(monkeypatch):
    from core.simulation.twin.live import runtime
    monkeypatch.setattr(ratelimit, "LIMITER", ratelimit.Limiter())
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    lim = ratelimit.LIMITER
    for _ in range(ratelimit.SIMS_PER_HOUR):
        assert lim.allow("v", "sim", ratelimit.SIMS_PER_HOUR, 3600) == 0
    r = TestClient(app).post("/api/sim/live/start", json={}, headers={"X-Forwarded-For": "v"})
    assert r.status_code == 429 and "simulations per visitor per hour" in r.json()["error"]
    assert runtime.HOSTED_MAX_SIM_S == 1800 and runtime.HOSTED_MAX_WALL_S == 600
