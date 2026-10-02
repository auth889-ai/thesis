"""The phone as the sensor: fixes in, cells out, nothing invented, privacy by construction."""
import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DHAKAFLOW_NO_OBSERVATORY", "1")


@pytest.fixture
def db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path}/probes.sqlite"
    monkeypatch.setenv("LIFEOS_DATABASE_URL", url)
    from app.lifeos import db as core
    assert core.init(url) == "0002_probes"
    return url


class FakeSnap:
    name = "fake"
    def snap(self, points):
        return [{**p, "snapped_lat": p["lat"] + 0.0001, "snapped_lng": p["lng"], "snap_confidence": 0.9} for p in points]


def _trace(n=6, start=None, speed=None, heading=90.0):
    t0 = start or datetime(2026, 10, 3, 8, 0, tzinfo=timezone.utc)
    return [{"lat": 23.7500 + i * 0.0002, "lng": 90.4000, "recorded_at": (t0 + timedelta(seconds=10 * i)).isoformat(),
             "accuracy_m": 8.0, "heading": heading, "speed_kmh": speed} for i in range(n)]


def test_fixes_become_cells_with_counts_and_speeds(db):
    from app.probes import service
    r = service.ingest("browser-abc", "dhaka", _trace(speed=36.0), snapper=FakeSnap(), db_url=db)
    assert r["accepted"] == 6 and r["snapped"] == 6 and r["snapper"] == "fake" and r["device"] != "browser-abc"
    c = service.cells("dhaka", minutes=10 ** 6, db_url=db)
    assert c["cells"] and all(x["n_devices"] == 1 and x["mean_speed_kmh"] == 36.0 for x in c["cells"])
    assert all(x["heading_octant"] == "2" for x in c["cells"])                     # 90 degrees east -> octant 2


def test_speed_is_derived_from_consecutive_fixes_when_the_device_gives_none(db):
    from app.probes import service
    pts = service.prepare(_trace(speed=None))
    assert pts[0].get("speed_kmh") is None and all(5 < p["speed_kmh"] < 12 for p in pts[1:])   # ~22 m per 10 s


def test_untrustworthy_fixes_are_dropped_not_guessed(db):
    from app.probes import service
    bad = _trace(speed=36.0)
    bad[0]["accuracy_m"] = 500.0                                                  # cannot say which road
    bad[1]["speed_kmh"] = 400.0                                                   # a glitch
    r = service.ingest("browser-abc", "dhaka", bad, snapper=FakeSnap(), db_url=db)
    assert r["accepted"] == 4 and r["dropped"] == 2


def test_two_devices_in_one_cell_count_as_two(db):
    from app.probes import service
    service.ingest("a", "dhaka", _trace(speed=30.0), snapper=FakeSnap(), db_url=db)
    service.ingest("b", "dhaka", _trace(speed=50.0), snapper=FakeSnap(), db_url=db)
    c = service.cells("dhaka", minutes=10 ** 6, db_url=db)
    assert all(x["n_devices"] == 2 and x["mean_speed_kmh"] == 40.0 for x in c["cells"])


def test_raw_fixes_are_purged_after_retention_and_cells_remain(db):
    from app.probes import service
    from app.probes.db import ProbePointRow, RETAIN_HOURS
    from app.lifeos.db import session
    service.ingest("a", "dhaka", _trace(speed=30.0), snapper=FakeSnap(), db_url=db)
    with session(db) as s:
        for row in s.query(ProbePointRow).all():
            row.received_at = datetime.now(timezone.utc) - timedelta(hours=RETAIN_HOURS + 1)
        s.commit()
    service.ingest("b", "dhaka", _trace(speed=30.0, start=datetime.now(timezone.utc)), snapper=FakeSnap(), db_url=db)
    st = service.status("dhaka", db_url=db)
    assert st["points_retained"] == 6 and st["cells"] >= 2


def test_without_aws_the_status_says_unsnapped(db, monkeypatch):
    from app.probes import service, snap
    monkeypatch.setattr(snap.AmazonSnap, "configured", property(lambda self: False))
    st = service.status("dhaka", db_url=db)
    assert st["snapper"] == "none" and "not configured" in st["snapping"]


def test_http_round_trip(db, client):
    body = {"device_id": "browser-xyz", "city": "dhaka", "points": _trace(speed=36.0)}
    from app.probes import service, snap
    import app.probes.service as svc
    orig = svc.default
    svc.default = lambda: FakeSnap()
    try:
        r = client.post("/api/probes", json=body)
        assert r.status_code == 200 and r.json()["accepted"] == 6
        cells = client.get("/api/probes/cells?city=dhaka&minutes=1000000").json()["cells"]
        assert cells and cells[0]["n_points"] >= 1
        assert client.post("/api/probes", json={**body, "points": []}).status_code == 422
    finally:
        svc.default = orig
