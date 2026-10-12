"""Crash SOS, TEST mode: the WreckWatch rule on the synthetic traces, deterministic traces, the plain line from the table, the alert
path for online and offline, and the TEST alert that never sends anything."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.safety import sos
from app.main import app


def test_the_rule_on_the_three_synthetic_traces():
    ride, brake, jolt = (sos.detect(sos.synthetic(k)["samples"]) for k in ("normal_ride", "hard_brake", "crash_jolt"))
    assert not ride["detected"] and ride["peak_g"] < 2
    assert not brake["detected"] and 1.5 <= brake["peak_g"] < 4                    # a hard brake stays under the 4 g that filters "a drop or sudden stop"
    assert jolt["detected"] and jolt["peak_g"] >= 4 and 12.0 <= jolt["at_s"] <= 12.12
    assert not jolt["speed_checked"]                                                # no speed in the trace: the speed floor is reported as not applied


def test_the_speed_floor_applies_only_when_a_speed_is_known():
    spike = [{"t": 0, "ax": 0, "ay": 0, "az": 9.81}, {"t": 0.1, "ax": 50, "ay": 0, "az": 9.81, "speed_kmh": 10}, {"t": 0.2, "ax": 50, "ay": 0, "az": 9.81, "speed_kmh": 40}]
    d = sos.detect(spike)
    assert d["detected"] and d["at_s"] == 0.2 and d["speed_checked"] and d["speed_kmh"] == 40


def test_synthetic_traces_are_deterministic():
    a, b = (hashlib.sha256(json.dumps(sos.synthetic("crash_jolt"), indent=0).encode()).hexdigest() for _ in range(2))
    assert a == b


def test_plain_numbers_come_from_the_rows(tmp_path):
    out = sos.build(traces=tmp_path / "t", evidence=tmp_path / "e")
    assert out["plain"] == sos.plain_numbers(out["rows"]) == {"traces": 3, "detected": 1, "peak_g": {r["kind"]: r["peak_g"] for r in out["rows"]}, "threshold_g": 4.0}
    assert (tmp_path / "t/SHA256SUMS").read_text().count("\n") == 3 and (tmp_path / "e/results.sha256").exists()


def test_the_checked_in_results_match_their_rows():
    f = Path(sos.EVIDENCE) / "results.json"
    if not f.exists():
        pytest.skip("not built here")
    d = json.loads(f.read_text())
    assert d["plain"] == sos.plain_numbers(d["rows"]) and d["label"] == "SYNTHETIC"


def test_the_path_online_shows_the_number_and_offline_uses_the_saved_mesh_result(monkeypatch):
    on = sos.path_steps("dhaka", True, 5.9)
    assert [s["key"] for s in on["steps"]] == ["detected", "countdown", "network", "never_sent"]
    assert on["steps"][2]["values"]["number"] == "999" and on["steps"][1]["values"]["seconds"] == 15
    off = sos.path_steps("dhaka", False, 5.9)
    third = off["steps"][2]
    assert third["key"] in ("mesh", "mesh_none")
    if third["key"] == "mesh":
        from core.networking.mesh import results as mesh
        t = mesh.read("dhaka")
        assert third["stamp"] == "SIMULATED" and third["values"]["pct"] == t["plain"]["reached_pct"] and third["values"]["vehicles"] == t["plain"]["vehicles"]   # the Offline page's own numbers
    assert sos.path_steps("nowhere", True)["available"] is False


def test_a_test_sos_reaches_the_feed_and_never_sends(monkeypatch):
    from app.plan import notifications
    monkeypatch.setattr(notifications, "publish", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a TEST SOS must never notify")))
    sos._TEST_ALERTS.clear()
    c = TestClient(app)
    r = c.post("/api/emergency/sos/test", json={"city_id": "dhaka", "peak_g": 5.87, "online": True, "source": "synthetic:crash_jolt"})
    assert r.status_code == 200 and r.json()["stamp"] == "TEST" and r.json()["tag"]["kind"] == "simulated"
    feed = c.get("/api/alerts/feed?city_id=dhaka").json()
    assert any(i["kind"] == "sos" and i["stamp"] == "TEST" for i in feed["items"])
    assert not any(i["kind"] == "sos" for i in c.get("/api/alerts/feed?city_id=berlin").json()["items"])       # never another city's
    assert c.get("/api/emergency/sos/trace/crash_jolt").status_code in (200, 404) and c.get("/api/emergency/sos/trace/nope").status_code == 404
    sos._TEST_ALERTS.clear()                                                                     # in-memory: leave nothing for the other tests


def test_button_press_is_labelled_button_not_sensor():
    """The map app's SOS button sends source "button": tagged as the button (real, a person's action) with no peak, never as the motion
    sensor or a replayed trace (audit 2026-10-10)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from core.safety import sos
    sos._TEST_ALERTS.clear()
    c = TestClient(app)
    r = c.post("/api/emergency/sos/test", json={"city_id": "dhaka", "peak_g": 0, "online": True, "source": "button"}).json()
    assert r["tag"]["kind"] == "real" and "button" in r["tag"]["source"] and "motion sensor" not in r["tag"]["source"]
    assert r["value"] is None and r["values"]["peak_g"] is None
    r = c.post("/api/emergency/sos/test", json={"city_id": "dhaka", "peak_g": 5.0, "online": True, "source": "sensor"}).json()
    assert r["tag"]["kind"] == "real" and "motion sensor" in r["tag"]["source"] and r["value"] == 5.0
    sos._TEST_ALERTS.clear()


def test_phone_sensor_detection_is_never_put_in_the_feed():
    """Step D (2026-10-11): a TEST detection from the phone's real sensor is answered but never stored in the alerts feed."""
    from fastapi.testclient import TestClient
    from app.main import app
    from core.safety import sos
    sos._TEST_ALERTS.clear()
    c = TestClient(app)
    r = c.post("/api/emergency/sos/test", json={"city_id": "dhaka", "peak_g": 6.1, "online": True, "source": "phone-sensor"}).json()
    assert r["stamp"] == "TEST" and r["stored"] is False and r["tag"]["kind"] == "real" and "phone" in r["tag"]["source"]
    assert not any(i["kind"] == "sos" for i in c.get("/api/alerts/feed?city_id=dhaka").json()["items"])
    assert sos._TEST_ALERTS == []


def test_a_trace_from_sumos_collision_record_carries_the_closing_speed_and_applies_the_speed_floor(tmp_path, monkeypatch):
    """R1 (2026-10-11): the pulse's integral equals |collider - victim|, every sample carries the collider's speed, and the rule fires only
    when both the 4 g and the 15 mph floor hold; the trace is served by the same API as the synthetic kinds and read back as a row."""
    src = {"run": "test", "record": {"colliderSpeed": "12.26", "victimSpeed": "20.00", "colliderType": "CNG", "victimType": "Motor_Cycle"}}
    tr = sos.from_collision(12.26, 20.0, src)
    assert tr["label"] == "SIMULATION" and tr["kind"] == "sumo_collision" and tr["collision"]["closing_speed_mps"] == 7.74
    import math
    assert tr["collision"]["pulse_peak_g"] == round(math.pi * 7.74 / (2 * sos.PULSE_S) / sos.G, 2)
    pulse = [s for s in tr["samples"] if sos.AT_S <= s["t"] < sos.AT_S + sos.PULSE_S]
    assert len(pulse) == 6 and all(s["speed_kmh"] == 44.1 for s in tr["samples"])
    assert sos.from_collision(12.26, 20.0, src, phone_speed_mps=20.0)["samples"][0]["speed_kmh"] == 72.0     # the phone in the other car
    d = tr["detection"]
    assert d["detected"] and d["speed_checked"] and d["speed_kmh"] == 44.1 and sos.AT_S <= d["at_s"] < sos.AT_S + sos.PULSE_S and d["peak_g"] > 4
    slow = sos.from_collision(2.0, 0.0, src)                                        # a 2 m/s nudge: 0.8 g, and under the speed floor
    assert not slow["detection"]["detected"] and slow["detection"]["peak_g"] < 4
    fast_but_soft = sos.from_collision(20.0, 19.0, src)                             # 72 km/h but a 1 m/s closing speed: no 4 g, no alarm
    assert not fast_but_soft["detection"]["detected"]
    f = tmp_path / "collision_trace.json"
    sha = sos.write_collision_trace(tr, f)
    assert sos.trace("sumo_collision", collision=f)["collision"]["source"] == src
    assert sos.trace("sumo_collision", collision=tmp_path / "none.json") is None
    row = sos.collision_row(f)
    assert row["available"] and row["detected"] and row["sha256"] == sha and row["speed_kmh"] == 44.1
    assert not sos.collision_row(tmp_path / "none.json")["available"]
    monkeypatch.setattr(sos, "COLLISION_TRACE", f)
    c = TestClient(app)
    assert c.get("/api/emergency/sos/trace/sumo_collision").json()["kind"] == "sumo_collision"
    assert c.get("/api/emergency/sos/results").json()["collision"]["detected"] is True
    monkeypatch.setattr(sos, "COLLISION_TRACE", tmp_path / "none.json")
    assert c.get("/api/emergency/sos/trace/sumo_collision").status_code == 404
    assert c.get("/api/emergency/sos/results").json()["collision"]["available"] is False
    assert sos.raise_test("dhaka", 9.9, True, "synthetic:sumo_collision")["tag"]["basis"].startswith("a trace built from SUMO's own collision record")
