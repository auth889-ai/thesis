"""Live simulations from the map: parameters checked, one at a time for the whole site, a per-visitor day limit when hosted."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform import ratelimit
from core.simulation.live_jobs import jobs, runner

client = TestClient(app)


def test_parameters_are_checked():
    assert jobs.validate("v2x", {}) == {"tech": "its_g5", "share": 1.0, "seed": 11, "level": "dhaka"}
    assert jobs.validate("mesh", {"phones": "8"})["phones"] == 8
    for kind, bad in (("v2x", {"tech": "wifi"}), ("v2x", {"share": 2}), ("mesh", {"phones": 40}), ("mesh", {"protocol": "x"}), ("signals", {"level": "x9"})):
        with pytest.raises(ValueError):
            jobs.validate(kind, bad)
    assert client.post("/api/live/teleport", json={}).status_code == 400


def test_one_simulation_at_a_time(monkeypatch):
    def slow(job):
        job.emit({"t": 0, "ambulance": [90.39, 23.75]})
        while not job.stop_event.is_set():
            time.sleep(0.05)
        raise runner.Stop
    monkeypatch.setattr(jobs, "mesh", slow)
    r = client.post("/api/live/mesh", json={})
    assert r.status_code == 200
    job = r.json()["job"]
    assert client.post("/api/live/v2x", json={}).status_code == 409
    v = client.get(f"/api/live/jobs/{job}").json()
    assert v["label"] == "SIMULATION" and v["frames"][0]["ambulance"] == [90.39, 23.75]
    client.post(f"/api/live/jobs/{job}/stop")
    for _ in range(50):
        if client.get(f"/api/live/jobs/{job}").json()["status"] == "stopped":
            break
        time.sleep(0.05)
    assert client.get(f"/api/live/jobs/{job}").json()["status"] == "stopped"
    assert not runner.busy()


def test_hosted_visitor_limit(monkeypatch):
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    lim = ratelimit.Limiter()
    monkeypatch.setattr(ratelimit, "LIMITER", lim)
    monkeypatch.setattr(runner.RUNNER, "start", lambda kind, p: {"started": True, "job": "x", "label": "SIMULATION"})
    codes = [client.post("/api/live/mesh", json={}).status_code for _ in range(ratelimit.LIVE_PER_DAY + 1)]
    assert codes[:-1] == [200] * ratelimit.LIVE_PER_DAY and codes[-1] == 429


def test_frames_are_dhaka_lon_lat():
    from core.common.paths import REPO
    n = runner.net(str(REPO / "data/cities/dhaka/sumo/corridor/dhaka_corridor.net.xml.gz"))
    x0, y0, x1, y1 = n.getBoundary()
    lon, lat = jobs.lonlat(n, (x0 + x1) / 2, (y0 + y1) / 2)
    assert 90.2 < lon < 90.6 and 23.6 < lat < 23.95
