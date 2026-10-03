"""Regime-aware alerts: thresholds from the train split, onset flags from the forecast, hysteresis and cooldown."""
import os

import numpy as np
import pytest

os.environ.setdefault("DHAKAFLOW_NO_OBSERVATORY", "1")


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/alerts.sqlite"
    monkeypatch.setenv("LIFEOS_DATABASE_URL", url)
    from app.lifeos import db as core
    assert core.init(url) == "0003_road_watches"
    return url


def test_flags_mark_onset_only_for_roads_free_now_and_forecast_below_threshold():
    from app.forecasting.operations.onset_now import flags
    now = np.array([60.0, 30.0, 60.0, 0.0])
    thr = np.array([40.0, 40.0, 40.0, 40.0])
    pred = np.tile(now, (12, 1)); pred[5, 0] = 35.0; pred[2, 2] = 61.0
    f = {r["node"]: r for r in flags(now, pred, thr)}
    assert f["S0"]["onset_in_min"] == 30 and f["S0"]["free_now"]
    assert f["S1"]["congested_now"] and f["S1"]["onset_in_min"] is None
    assert f["S2"]["onset_in_min"] is None
    assert "S3" not in f                                            # an outage is not a road state


def _fake_onsets(schedule):
    """schedule[as_of] = set of nodes with onset predicted at that moment."""
    def onsets(dataset, as_of, model=None):
        nodes = schedule.get(as_of, set())
        roads = [{"node": n, "index": int(n[1:]), "now": 55.0, "threshold": 40.0, "free_now": True, "congested_now": False,
                  "predicted": {"15": 35.0, "30": 33.0, "60": 30.0}, "onset_in_min": 15} for n in nodes]
        return {"dataset": dataset, "as_of": as_of, "model": "fake", "roads": roads, "tipping": roads}
    return onsets


def test_alert_needs_two_consecutive_moments_and_fires_once_per_episode(db):
    from app.alerts import service
    sent = []
    service.watch("eva", "METR_LA", "S7", "Mirpur Road north", db_url=db)
    sched = {100: {"S7"}, 101: {"S7"}, 102: {"S7"}, 103: {"S7"}, 110: {"S7"}, 111: {"S7"}}
    pub = lambda p, k, t, d="": sent.append((p, k, t))
    r = service.evaluate("METR_LA", 100, onsets=_fake_onsets(sched), db_url=db, publish=pub)
    assert r["alerts"] == [] and r["watches_checked"] == 1                       # first moment alone is not enough
    r = service.evaluate("METR_LA", 101, onsets=_fake_onsets(sched), db_url=db, publish=pub)
    assert len(r["alerts"]) == 1 and "Mirpur Road north" in sent[0][2] and sent[0][1] == "onset"
    r = service.evaluate("METR_LA", 102, onsets=_fake_onsets(sched), db_url=db, publish=pub)
    assert r["alerts"] == []                                                      # same episode: cooldown
    r = service.evaluate("METR_LA", 111, onsets=_fake_onsets(sched), db_url=db, publish=pub)
    assert len(r["alerts"]) == 1 and len(sent) == 2                               # a new episode after the cooldown
    assert len(service.alerts("eva", db_url=db)) == 2


def test_watch_round_trip_over_http(db, client):
    r = client.post("/api/watch/roads", json={"person_id": "eva", "dataset": "METR_LA", "node": "S3", "label": "I-10 west"})
    assert r.status_code == 200 and r.json()["node"] == "S3"
    wid = r.json()["id"]
    assert [w["id"] for w in client.get("/api/watch/roads?person_id=eva").json()["watches"]] == [wid]
    assert client.delete(f"/api/watch/roads/{wid}?person_id=someone-else").status_code == 404
    assert client.delete(f"/api/watch/roads/{wid}?person_id=eva").status_code == 200


def test_onset_now_runs_on_the_served_model(client):
    from app.forecasting.operations import served_checkpoints as sc
    r = client.get("/api/protocol-b/onset-now?dataset=METR_LA&as_of=20000&model=GWNet")
    assert r.status_code == 200
    j = r.json()
    assert j["counts"]["roads"] > 150 and "train split" in j["rule"] and all(t["free_now"] for t in j["tipping"])
