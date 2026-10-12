"""The map's forecast layer: every number from a saved file, best time only with skill, explicit "no data" otherwise."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.common.paths import REPO
from core.ml.forecasting.layer import service

LA_SUMMARY = REPO / "results/forecasting/layer/summary.json"
RQ1 = REPO / "results/forecasting/rq1/summary.json"
client = TestClient(app)
CARD_SKILL = {h: {"mae": 1.0, "no_change_mae": 2.0, "skill": 0.5} for h in service.HORIZONS}


def test_pick_same_weekday_and_time_latest_date():
    times = [datetime(2012, 6, 4, 8, 0), datetime(2012, 6, 11, 8, 0), datetime(2012, 6, 11, 8, 5), datetime(2012, 6, 12, 8, 0)]
    monday_8_03 = datetime(2026, 10, 12, 8, 3)                    # a Monday
    assert service.pick(times, monday_8_03) == 1
    assert service.pick(times, datetime(2026, 10, 14, 8, 0)) is None   # no Wednesday recorded


def test_replay_uses_the_city_time_zone_across_dst():
    tz = ZoneInfo("America/Los_Angeles")
    winter = datetime(2026, 12, 7, 16, 0, tzinfo=timezone.utc).astimezone(tz)    # PST: 08:00
    summer = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc).astimezone(tz)     # PDT: 08:00
    times = [datetime(2012, 6, 4, 8, 0)]
    assert service.pick(times, winter) == 0 and service.pick(times, summer) == 0


def test_best_time_needs_skill_at_every_horizon():
    now, fc, keep = np.full(5, 20.0), np.full((3, 5), 40.0), np.ones(5, bool)
    assert service.best_time(now, fc, CARD_SKILL, keep)["leave_in_min"] == 15
    no = {**CARD_SKILL, "60": {"mae": 3.0, "no_change_mae": 2.0, "skill": -0.5}}
    assert service.best_time(now, fc, no, keep) is None


def test_best_time_says_now_when_no_clear_gain():
    now, fc = np.full(5, 30.0), np.full((3, 5), 30.5)
    b = service.best_time(now, fc, CARD_SKILL, np.ones(5, bool))
    assert b["leave_in_min"] == 0 and b["clear"] is False


def test_city_without_layer_says_no_data():
    r = client.get("/api/forecast-layer/berlin").json()
    assert r["available"] is False and "no data" in r["reason"]
    assert client.get("/api/forecast-layer/atlantis").json()["available"] is False


@pytest.mark.skipif(not LA_SUMMARY.exists(), reason="layer not built: python -m core.ml.forecasting.layer.build_la")
def test_la_card_equals_the_build_summary():
    s = json.loads(LA_SUMMARY.read_text())
    r = client.get("/api/forecast-layer/los_angeles", params={"at": "2026-10-12T15:00:00+00:00"}).json()   # Monday 08:00 in Los Angeles
    assert r["available"] and r["kind"] == "replay" and r["units"] == "mph" and r["recorded_weekday"] == "Monday"
    assert r["recorded_at"].endswith("08:00")
    for h in service.HORIZONS:
        assert r["card"]["horizons"][h]["mae"] == round(s["card"][h]["mae"], 2)
        assert r["card"]["horizons"][h]["skill"] == s["card"][h]["skill"]
    assert len(r["points"]) == 207
    assert s["model"]["rq1_check"]["max_abs_diff_mph"] <= 1e-3
    assert (r["best_time"] is not None) == all(s["card"][h]["skill"] > 0 for h in service.HORIZONS)


def test_dhaka_recorded_day_card_from_rq1_and_no_best_time():
    r = client.get("/api/forecast-layer/dhaka", params={"at": "2026-10-10T03:00:00+00:00"}).json()     # 09:00 in Dhaka
    if not r["available"]:
        pytest.skip(r["reason"])
    s = json.loads(RQ1.read_text())["dhaka"]
    assert r["kind"] == "recorded_day" and r["best_time"] is None
    bm = next(p for p in r["points"] if p["id"] == "BM")
    assert bm["day"] == "2026-04-20" and bm["interval_start"].startswith("2026-04-20 09:00")
    for h in service.HORIZONS:
        c = r["card"]["sites"]["BM"][h]
        assert c["no_change_mae"] == s["persistence"][h]["per_site"]["BM"]
        assert c["mae"] == min(s[m][h]["per_site"]["BM"] for m in service.ZERO_SHOT)
    assert all(p["id"] != "BS" for p in r["points"])                 # BS has no stated place
