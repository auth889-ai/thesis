"""The live twin (core/simulation/live_twin) and its forecasters (core/ml/forecasting/live): the stream, the forecasters, the click
actions and the hosted limits."""
from __future__ import annotations

import math
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.platform import ratelimit
from core.common.paths import REPO
from core.ml.forecasting.live import online
from core.simulation.live_twin import demand, detectors, manager, session

client = TestClient(app)
DHAKA_BOX = (90.30, 23.65, 90.50, 23.85)


def in_dhaka(lon: float, lat: float) -> bool:
    return DHAKA_BOX[0] < lon < DHAKA_BOX[2] and DHAKA_BOX[1] < lat < DHAKA_BOX[3]


# ---------------------------------------------------------------------------------------------------------------- forecasters
def series(m: int, i: int) -> float:
    return 35 + 15 * math.sin((m + 3 * i) / 12)


def test_no_change_is_the_last_value_and_nothing_is_learned_early():
    f = online.Forecasters({"a": 60.0, "b": 50.0}, use_chronos=False)
    for m in range(online.HORIZON + max(online.LAGS)):
        last = online.HORIZON + max(online.LAGS) - 1
        f.observe({"a": series(m, 0), "b": None if m == last else series(m, 1)}, 1.0)
        assert f.learned == 0                          # the first prediction is made at minute 14; its truth arrives at minute 29
    assert f.predictions("no_change")["a"] == round(series(m, 0), 1)
    assert f.predictions("no_change")["b"] == round(series(m - 1, 1), 1)         # a missing minute is carried forward as an input only
    f.observe({"a": series(m + 1, 0), "b": series(m + 1, 1)}, 1.0)
    assert f.learned == 2


def test_online_model_learns_on_a_fixed_series():
    f = online.Forecasters({f"r{i}": 60.0 for i in range(30)}, use_chronos=False)
    for m in range(240):
        f.observe({f"r{i}": series(m, i) for i in range(30)}, 1.0)
    h = f.history
    assert h[0]["online_10"] == h[0]["no_change_10"]   # untrained, it is "no change"
    assert h[-1]["online_10"] < 0.5 * h[-1]["no_change_10"]
    assert h[0]["chronos_10"] is None                  # Chronos off: compared without it, never invented


def test_chronos_gives_fifteen_steps():
    ok, why = online.Chronos.available()
    if not ok:
        pytest.skip(why)
    out = online.Chronos.predict([[series(m, 0) for m in range(60)], [None] * 10 + [series(m, 1) for m in range(50)]], online.HORIZON)
    assert len(out) == 2 and all(len(o) == online.HORIZON for o in out)
    assert all(0 < v < 100 for o in out for v in o)


# ---------------------------------------------------------------------------------------------------------------- detectors, demand
def test_detectors_from_the_network(tmp_path: Path):
    from core.common.data import city_config
    from core.simulation.live_jobs.runner import net
    lt = city_config.load("dhaka").live_twin
    n = net(str(REPO / lt.net))
    roads = detectors.roads(n, lt.detector_road_types, lt.detector_min_edge_m)
    assert len(roads) > 50 and all(r.getLength() >= lt.detector_min_edge_m and r.getFunction() == "" for r in roads)
    by_road, sha = detectors.write_additional(tmp_path / "a.xml", roads)
    assert sum(len(v) for v in by_road.values()) == sum(r.getLaneNumber() for r in roads)
    assert sha == detectors.write_additional(tmp_path / "b.xml", roads)[1]
    assert city_config.load("los_angeles").live_twin is None           # no config entry: "no data for this city"

    class Loops:
        @staticmethod
        def getLastIntervalMeanSpeed(lid):
            return {"x0": 10.0, "x1": -1.0}.get(lid, -1.0)
    conn = type("C", (), {"inductionloop": Loops})()
    assert detectors.read_minute(conn, {"r": ["x0", "x1"], "empty": ["y"]}) == {"r": 36.0, "empty": None}


def test_demand_repeats_hour_after_hour(tmp_path: Path):
    src = tmp_path / "r.xml"
    src.write_text('<routes>\n<vType id="c"/>\n<vehicle id="v0" depart="1.00"><route edges="a"/></vehicle>\n'
                   '<vehicle id="v1" depart="3500.00"><route edges="b"/></vehicle>\n</routes>\n')
    text = demand.repeated(src, tmp_path / "o.xml", 3).read_text()
    ids = re.findall(r'<vehicle id="([^"]+)"', text)
    departs = [float(x) for x in re.findall(r'depart="([\d.]+)"', text)]
    assert ids == ["v0_h0", "v1_h0", "v0_h1", "v1_h1", "v0_h2", "v1_h2"]
    assert departs == [1.0, 3500.0, 3601.0, 7100.0, 7201.0, 10700.0]
    assert text.count('<vType id="c"/>') == 1


# ---------------------------------------------------------------------------------------------------------------- a real twin
@pytest.fixture(scope="module")
def twin():
    s = session.Session("dhaka", "test-visitor", speed=1e9, sync_forecasts=True)
    s.start()
    end = time.time() + 240
    while s.status in ("starting", "warming") and time.time() < end:
        time.sleep(0.5)
    yield s
    s.stop()
    s.thread.join(30)


def run_for(s, seconds: float) -> None:
    t = s.t
    end = time.time() + 120
    while s.t < t + seconds and s.status == "running" and time.time() < end:
        time.sleep(0.2)


def test_twin_streams_vehicles_in_lon_lat_with_a_clock_seed(twin):
    assert twin.status == "running", twin.message
    assert abs(twin.seed - int(time.time()) % 2**31) < 600
    index, msgs = twin.since(None)
    assert msgs[0]["type"] == "full" and len(msgs[0]["vehicles"]) > 50
    assert all(in_dhaka(v["lon"], v["lat"]) for v in msgs[0]["vehicles"].values())
    run_for(twin, 5)
    _, more = twin.since(index)
    steps = [m for m in more if m["type"] == "step"]
    assert steps and set(steps[0]["vehicles"]) == {"creations", "updates", "removals"}
    assert twin.hello()["label"] == "SIMULATION" and twin.hello()["roads"]
    f = twin.forecast
    assert f["roads"] == len(twin.loops) and set(f["predicted"]) == set(online.NAMES)


def test_crash_blocks_its_lane(twin):
    # only the twin's published state is read here: its TraCI connection belongs to the simulation thread
    for vid, v in sorted(twin.vehicles.items(), key=lambda p: -p[1]["speed"])[:20]:
        twin.command({"cmd": "crash", "lon": v["lon"], "lat": v["lat"]})
        run_for(twin, 2)
        if twin.crashed:
            break
    assert len(twin.crashed) == 1, twin.events[-3:]
    crashed = next(iter(twin.crashed))
    run_for(twin, 20)
    assert twin.vehicles[crashed]["speed"] == 0
    assert twin.vehicles[crashed]["s"] == session.CRASHED
    assert twin.events[-1]["key"] == "crash"


def test_live_twin_ambulance_has_no_bluelight_device_and_the_thesis_keeps_it(twin):
    from core.simulation.ambulance import service
    assert twin.amb_cfg["ambulance"]["vtype"]["bluelight"] is False and twin.hello()["bluelight"] is False
    assert 'key="has.bluelight.device" value="false"' in (twin.dir / "ambulance_type.rou.xml").read_text()
    assert service.settings()["ambulance"]["vtype"]["bluelight"] is True        # the thesis runs are unchanged
    assert twin.amb_cfg["alert"]["makeway"]["version"] == 2


def test_ambulance_alerts_and_demand_slider(twin):
    o = twin.cfg.emergency.origin
    twin.command({"cmd": "ambulance", "lon": o.lon, "lat": o.lat})
    twin.command({"cmd": "demand", "value": 1.5})
    run_for(twin, 60)
    assert twin.status == "running", twin.message
    a = twin._counts()["ambulance"]
    assert a is not None and a["messages"]["sent"] > 0 and a["technology"] == "its_g5" and a["range_m"] == 425.0
    assert twin.factor == 1.5 and any(e["key"] == "demand" and e["params"]["x"] == 1.5 for e in twin.events)
    twin.command({"cmd": "ambulance", "lon": o.lon, "lat": o.lat})
    run_for(twin, 2)
    if a["state"] != "arrived":
        assert any(e["key"] == "ambBusy" for e in twin.events)                 # one ambulance at a time
    twin.command({"cmd": "demand", "value": 9})
    run_for(twin, 2)
    assert twin.events[-1]["key"] == "demandRange"


# ---------------------------------------------------------------------------------------------------------------- limits
class Stub:
    def __init__(self, city_id, visitor, **kw):
        self.visitor, self.status, self.last_seen, self.id, self.said = visitor, "running", time.time(), f"stub-{visitor}", None

    def start(self):
        pass

    def stop(self):
        self.status = "stopped"

    def say(self, *a, **k):
        self.said = a


def test_one_twin_per_visitor_a_server_cap_and_the_idle_stop(monkeypatch):
    monkeypatch.setattr(manager, "Session", Stub)
    monkeypatch.setattr(manager, "others_running", lambda: 1)
    m = manager.Manager()
    monkeypatch.setattr(m, "_ensure_reaper", lambda: None)
    a, created = m.start("dhaka", "v1")
    again, created2 = m.start("dhaka", "v1")
    assert created and not created2 and again is a
    m.start("dhaka", "v2")
    with pytest.raises(session.Refused) as e:
        m.start("dhaka", "v3")                          # 2 twins + 1 other simulation = MAX_RUNNING
    assert e.value.key == "full"
    assert m.reap_once(time.time() + manager.IDLE_S + 1) is False
    assert a.status == "stopped" and a.said[1] == "idle"


def test_hosted_twin_starts_per_day(monkeypatch):
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    monkeypatch.setattr(ratelimit, "LIMITER", ratelimit.Limiter())
    monkeypatch.setattr(manager.MANAGER, "start", lambda city, who, **kw: (Stub(city, who), True))
    monkeypatch.setattr(Stub, "hello", lambda self: {"id": self.id}, raising=False)
    codes = [client.post("/api/live-twin/dhaka/start", json={}).status_code for _ in range(ratelimit.TWINS_PER_DAY + 1)]
    assert codes[:-1] == [200] * ratelimit.TWINS_PER_DAY and codes[-1] == 429


def test_a_visitor_is_the_browser_id_not_the_address(monkeypatch):
    seen = []
    monkeypatch.setattr(manager.MANAGER, "start", lambda city, who, **kw: (seen.append(who), (Stub(city, who), True))[1])
    monkeypatch.setattr(Stub, "hello", lambda self: {"id": self.id}, raising=False)
    for ip in ("103.80.1.178", "103.80.1.179"):
        client.post("/api/live-twin/dhaka/start", json={}, headers={"X-TT-Visitor": "abcd-1234-efgh", "X-Forwarded-For": ip})
    client.post("/api/live-twin/dhaka/start", json={}, headers={"X-TT-Visitor": "bad id!", "X-Forwarded-For": "10.0.0.9"})
    assert seen == ["v:abcd-1234-efgh", "v:abcd-1234-efgh", "10.0.0.9"]


def test_websocket_sends_hello_then_the_state(monkeypatch):
    s = Stub("dhaka", "testclient")
    s.hello = lambda: {"type": "hello", "id": s.id, "label": "SIMULATION"}
    s.since = lambda index: (1, [{"type": "full", "vehicles": {"x": {"lon": 90.4, "lat": 23.75}}}]) if index is None else (1, [])
    s.command = lambda cmd: None
    s.status = "running"
    monkeypatch.setattr(manager.MANAGER, "sessions", {s.id: s})
    with client.websocket_connect(f"/api/live-twin/twins/{s.id}/ws") as ws:
        assert ws.receive_json()["label"] == "SIMULATION"
        assert ws.receive_json()["type"] == "full"
    with client.websocket_connect("/api/live-twin/twins/nope/ws") as ws:
        assert ws.receive_json()["type"] == "error"


# ---------------------------------------------------------------------------------------------------------------- steering (off by default)
def test_steering_is_off_by_default(twin):
    assert twin.steer is None and twin.steer_stats["minutes"] == 0 and not twin.steered
    assert twin._status_full()["steer"] is None
    assert all(v["s"] != session.STEERED for v in twin.vehicles.values())


def test_steering_sets_predicted_times_and_reroutes_the_informed_share():
    s = session.Session("dhaka", "steer-test", speed=1e9, sync_forecasts=True, chronos=False, steer={"forecaster": "online", "share": 0.3})
    s.start()
    end = time.time() + 240
    while s.t < 18 * 60 and s.status in ("starting", "warming", "running") and time.time() < end:
        time.sleep(0.5)
    s.stop(); s.thread.join(30)
    st = s.steer_stats
    assert st["minutes"] >= 2 and st["edges_set"] > 50 and st["reroutes"] > 0, st
    assert st["route_changed"] >= len(s.steered) > 0          # a car may change route in more than one minute
    other = session.Session("dhaka", "steer-test-2", steer={"forecaster": "current", "share": 0.3})
    other.seed = s.seed
    assert [v for v in ("a1", "b2", "c3", "d4", "e5") if s.informed(v)] == [v for v in ("a1", "b2", "c3", "d4", "e5") if other.informed(v)]
    with pytest.raises(session.Refused):
        session.Session._check_steer({"forecaster": "oracle"})
