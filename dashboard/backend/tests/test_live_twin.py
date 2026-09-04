"""The live twin: a real SUMO run streams real positions, the agent drives the same functions."""
from __future__ import annotations

import time

import pytest


def test_agent_rules_parse_the_reference_phrases():
    import sim_agent as sa
    tool, p = sa.parse("Run another simulation with a higher volume, say 60 % demand for 20 minutes")
    assert tool == "start_simulation" and p["scale"] == 0.6 and p["duration_s"] == 1200
    assert sa.parse("stop the simulation")[0] == "stop_simulation"
    assert sa.parse("pause")[0] == "pause_simulation"
    assert sa.parse("continue")[0] == "resume_simulation"
    assert sa.parse("what is the status?")[0] == "get_status"
    tool, p = sa.parse("start a prediction-aware run, seed 7, compliance 40 %")
    assert p["arm"] == "prediction_aware" and p["seed"] == 7 and p["compliance"] == 0.4


def test_agent_clamps_parameters_into_the_twins_range():
    import sim_agent as sa
    q = sa._clamp({"scale": 9, "duration_s": 5, "compliance": 3, "arm": "nope", "step_delay_ms": -4})
    assert q == {"scale": 1.0, "duration_s": 60, "compliance": 1.0, "step_delay_ms": 0}


def test_map_config_never_leaks_a_secret(client):
    c = client.get("/api/config/map").json()
    assert c["provider"] in ("esri", "mapbox") and "{z}" in c["tiles"]
    assert "sk." not in c["tiles"]


@pytest.mark.slow
def test_live_run_streams_positions_and_scores_like_the_chain(client):
    r = client.post("/api/sim/live/start", json={"duration_s": 90, "scale": 0.1, "arm": "reactive",
                                                 "step_delay_ms": 40}).json()   # ~4 s of playback
    assert r["started"], r
    seen = False
    for _ in range(600):
        s = client.get("/api/sim/live/state").json()
        if s.get("vehicles"):
            lon, lat, v, eq = s["vehicles"][0]
            assert 90.2 < lon < 90.6 and 23.6 < lat < 23.95      # Dhaka
            assert v >= 0 and eq in (0, 1)
            seen = True
        if s["status"] in ("done", "failed", "stopped"):
            break
        if _ % 25 == 0:
            print(f"[live-test] {time.strftime('%H:%M:%S')} status={s['status']} t={s.get('sim_time_s')} "
                  f"msg={s.get('message')!r} kpis={bool(s.get('kpis'))}", flush=True)
        time.sleep(0.2)
    assert seen and s["status"] == "done", s.get("message")
    assert "total_vehicle_hours" in s["result"]["metrics"]
    assert client.get("/api/sim/live/history").json()["runs"][0]["run_id"] == r["run_id"]


def test_agent_endpoint_answers_without_a_key(client, monkeypatch):
    import credentials
    monkeypatch.setattr(credentials, "anthropic_key", lambda: "")
    d = client.post("/api/sim/agent", json={"message": "status"}).json()
    assert d["backend"] == "rules" and d["actions"][0]["tool"] == "get_status"
