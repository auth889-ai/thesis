"""The live twin: a real SUMO run streams real positions, the agent drives the same functions."""
from __future__ import annotations

import json

import time

import pytest
from pathlib import Path

needs_recorded = pytest.mark.skipif(not (Path(__file__).resolve().parents[2] / "results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl").exists(), reason="recorded live series is git-ignored; absent on CI")


@pytest.fixture(autouse=True)
def outputs_go_to_a_temporary_folder(tmp_path, monkeypatch):
    """A test run must not add folders to results/live/sim or rewrite the run history."""
    from core.simulation.twin.live import runtime, settings
    for module in (runtime, settings):
        monkeypatch.setattr(module, "OUT_ROOT", tmp_path / "sim")
        monkeypatch.setattr(module, "HISTORY", tmp_path / "sim_history.json")


def test_agent_rules_parse_the_reference_phrases():
    from core.simulation.twin.live import command_handler as sa
    tool, p = sa.parse("Run another simulation with a higher volume, say 60 % demand for 20 minutes")
    assert tool == "start_simulation" and p["scale"] == 0.6 and p["duration_s"] == 1200
    assert sa.parse("stop the simulation")[0] == "stop_simulation"
    assert sa.parse("pause")[0] == "pause_simulation"
    assert sa.parse("continue")[0] == "resume_simulation"
    assert sa.parse("what is the status?")[0] == "get_status"
    assert sa.parse("start a continuous run at 25 % demand")[1].get("continuous") is True
    tool, p = sa.parse("start a prediction-aware run, seed 7, compliance 40 %")
    assert p["arm"] == "prediction_aware" and p["seed"] == 7 and p["compliance"] == 0.4


def test_agent_clamps_parameters_into_the_twins_range():
    from core.simulation.twin.live import command_handler as sa
    q = sa._clamp({"scale": 9, "duration_s": 5, "compliance": 3, "arm": "nope", "step_delay_ms": -4})
    assert q == {"scale": 1.0, "duration_s": 60, "compliance": 1.0, "step_delay_ms": 0}


def test_map_config_never_leaks_a_secret(client):
    c = client.get("/api/config/map").json()
    assert c["provider"] in ("openfreemap", "mapbox") and ("{z}" in c["tiles"] if c["provider"] == "mapbox" else c["style"].startswith("https://"))
    assert "sk." not in json.dumps(c)


def test_map_config_names_a_base_map_we_may_use_and_a_satellite_picture_that_says_what_it_is(client, monkeypatch):
    from core.common import credentials
    monkeypatch.setattr(credentials, "mapbox_token", lambda: None)
    c = client.get("/api/config/map").json()
    assert c["provider"] == "openfreemap" and "OpenStreetMap" in c["attribution"] and "OpenFreeMap" in c["attribution"]
    sat = c["satellite"]
    assert sat["licence"] == "CC BY 4.0" and sat["captured"] == "2016" and sat["composite"] is True and sat["resolution_m"] == 10
    assert "{z}" in sat["tiles"] and "EOX" in sat["attribution"] and "Copernicus Sentinel data 2016" in sat["attribution"]


def test_no_esri_address_is_left_in_the_app():
    """Esri's street tiles need Esri software or a subscription (third_party/SOURCES.md); nothing may load them."""
    import pathlib
    repo = pathlib.Path(__file__).resolve().parents[2]
    files = [f for root, pats in (("backend/app", ("*.py",)), ("frontend/src", ("*.ts", "*.tsx"))) for pat in pats for f in (repo / root).rglob(pat)]
    assert len(files) > 100
    assert not [str(f.relative_to(repo)) for f in files if "arcgisonline" in f.read_text(errors="ignore").lower()]


@pytest.mark.slow
def test_live_run_streams_positions_and_scores_like_the_chain(client):
    r = client.post("/api/sim/live/start", json={"duration_s": 90, "scale": 0.1, "arm": "reactive",
                                                 "step_delay_ms": 40}).json()   # ~4 s of playback
    assert r["started"], r
    seen = False
    for _ in range(600):
        s = client.get("/api/sim/live/state").json()
        if s.get("vehicles"):
            lon, lat, v, eq, vid, angle, vclass = s["vehicles"][0]
            assert 90.2 < lon < 90.6 and 23.6 < lat < 23.95      # Dhaka
            assert v >= 0 and eq in (0, 1) and isinstance(vid, str) and 0 <= angle <= 360 and vclass
            assert isinstance(s.get("signals"), dict)             # traffic-light phase strings, by signal id
            seen = True
        if s["status"] in ("done", "failed", "stopped"):
            break
        time.sleep(0.2)
    assert seen and s["status"] == "done", s.get("message")
    assert "total_vehicle_hours" in s["result"]["metrics"]
    assert client.get("/api/sim/live/history").json()["runs"][0]["run_id"] == r["run_id"]


def test_agent_endpoint_answers_without_a_key(client, monkeypatch):
    from core.common import credentials
    monkeypatch.setattr(credentials, "anthropic_key", lambda: "")
    d = client.post("/api/sim/agent", json={"message": "status"}).json()
    assert d["backend"] == "rules" and d["actions"][0]["tool"] == "get_status"


@pytest.mark.slow
def test_continuous_mode_replays_demand_and_couples_to_the_live_road(client):
    r = client.post("/api/sim/live/start", json={"continuous": True, "scale": 0.1, "arm": "baseline",
                                                 "step_delay_ms": 0}).json()
    assert r["started"] and r["params"]["continuous"] and r["params"]["duration_s"] > 3600
    hour2 = False
    for _ in range(600):
        s = client.get("/api/sim/live/state?vehicles=false").json()
        k = s.get("kpis") or {}
        if (k.get("hour") or 0) >= 2 and k.get("vehicles_on_road", 0) > 0:
            hour2 = True; break
        if s["status"] == "failed":
            pytest.fail(s.get("message"))
        time.sleep(0.2)
    st = client.post("/api/sim/live/stop").json()
    assert hour2, "demand was not replayed into the second hour"
    assert st["status"] in ("stopped", "done") and st["result"]["metrics"]["arrived"] > 0
    assert "live_applied_utc" in k


@needs_recorded
def test_opencity_predict_endpoint_refuses_honestly_when_the_window_is_short(client):
    d = client.post("/api/opencity/dhaka/predict", json={"source": "recorded"}).json()
    assert d["ok"] is False and "9 nodes" in d["error"]          # 6 recorded corridors


def test_networks_list_starts_with_the_calibrated_twin(client):
    d = client.get("/api/twin/networks").json()
    assert d["networks"][0]["id"] == "dhaka_r1" and d["networks"][0]["demand"] .startswith("SYNTHETIC_WHAT_IF_UNCALIBRATED")
    assert d["networks"][0]["validation"]["status"] in {"VALIDATED", "NOT_VALIDATED", "UNAVAILABLE"}
    for n in d["networks"][1:]:
        assert n["demand"] in ("SYNTHETIC_WHAT_IF", "SYNTHETIC_PARTLY_CALIBRATED") and n["edges"] > 0     # the second: fitted to counts on a few sections (twin/calibration.py)


def test_start_refuses_an_unknown_network(client):
    r = client.post("/api/sim/live/start", json={"network": "atlantis"}).json()
    assert r["started"] is False and "generate" in r["reason"]


@pytest.mark.slow
def test_generated_city_runs_in_the_twin(client):
    from core.simulation.twin.live import runtime as live_sim
    gen = sorted([n for n in live_sim.networks() if n["id"] != "dhaka_r1" and n.get("edges", 0) >= 100],
                 key=lambda n: -n["edges"])
    if not gen:
        pytest.skip("no generated city with a usable network in this checkout")
    r = client.post("/api/sim/live/start", json={"network": gen[0]["id"], "duration_s": 300,
                                                 "scale": 2.0, "arm": "reactive", "step_delay_ms": 5}).json()
    assert r["started"] and r["params"]["demand_reality"] == "SYNTHETIC_WHAT_IF"
    for _ in range(600):
        s = client.get("/api/sim/live/state").json()
        if s["status"] in ("done", "failed"): break
        time.sleep(0.2)
    assert s["status"] == "done", s.get("message")
    assert s["result"]["metrics"]["arrived"] > 0


def test_map_config_offers_worldwide_buildings_and_survives_an_unreachable_catalogue(client, monkeypatch):
    from core.simulation.twin import buildings_source as bs
    from core.simulation.twin import scene
    b = client.get("/api/config/map").json()["buildings"]              # tests make no outside request
    assert b["provider"] == "overture" and b["url"].endswith(f"{b['release']}/buildings.pmtiles") and "OpenStreetMap" in b["attribution"] and "Overture" in b["attribution"]
    assert b["heights"]["assumed_storey_m"] == scene.LEVEL_M and b["heights"]["assumed_default_m"] == scene.DEFAULT_M        # one rule in the project
    monkeypatch.delenv(bs.OFFLINE_ENV, raising=False)
    monkeypatch.setattr(bs, "_cache", {})
    monkeypatch.setattr(bs, "latest_release", lambda: (_ for _ in ()).throw(OSError("unreachable")))
    fallback = bs.source()
    assert fallback["release"] == bs.KNOWN_RELEASE and "could not be read" in fallback["found"]
    monkeypatch.setattr(bs, "_cache", {})
    monkeypatch.setattr(bs, "latest_release", lambda: "2099-01-01.0")
    assert bs.source()["release"] == "2099-01-01.0" and "Google" not in client.get("/api/config/map").json()["attribution"]
