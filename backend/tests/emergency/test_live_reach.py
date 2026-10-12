"""Step K (2026-10-11): live reach from a tapped point. The server is mocked; the shape, the timing and the untouched thesis number are checked."""
from fastapi.testclient import TestClient

from app.main import app
from core.safety import reach


def _mock(monkeypatch):
    file = {"hospitals": [{"osm_id": "n/1", "name": "Near Hospital", "lat": 23.74, "lon": 90.39, "emergency": "yes"},
                          {"osm_id": "n/2", "name": "Far Hospital", "lat": 23.80, "lon": 90.42, "emergency": None}]}
    monkeypatch.setattr(reach.hosp, "load", lambda city: file)
    calls = {"matrix": 0, "iso": 0}

    def matrix(city, sources, targets, profile):
        calls["matrix"] += 1
        return {"available": True, "times_s": [[300 * (i + j + 1) for j in range(len(targets))] for i in range(len(sources))],
                "distances_m": [[1000 for _ in targets] for _ in sources]}

    def iso(city, lat, lon, minutes=(10, 20, 30), profile="car"):
        calls["iso"] += 1
        return {"city_id": city, "available": True, "contours": [{"minutes": m, "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], [lon + 0.01, lat], [lon, lat + 0.01], [lon, lat]]]}} for m in (10, 20, 30)]}
    monkeypatch.setattr(reach.valhalla, "matrix", matrix)
    monkeypatch.setattr(reach.valhalla, "isochrone", iso)
    return calls


def test_live_reach_gives_nearest_hospitals_their_polygons_and_the_thesis_number_unchanged(monkeypatch):
    calls = _mock(monkeypatch)
    got = reach.live("dhaka", 23.75, 90.40, k=2)
    assert got["available"] and got["label"] == "LIVE" and got["computed_s"] >= 0
    assert [h["name"] for h in got["hospitals"]] == ["Near Hospital", "Far Hospital"]
    assert [m["minutes"] for m in got["hospitals"][0]["contours"]] == [10, 20, 30]
    assert got["hospitals"][0]["to_point_s"] == 300 and got["hospitals"][0]["reached_within_min"] == 10
    assert got["hospitals"][1]["to_point_s"] == 600 and got["hospitals"][1]["reached_within_min"] == 10
    assert calls == {"matrix": 2, "iso": 2}                                  # point->hospitals, hospitals->point; one isochrone per hospital
    saved = reach.read("dhaka", with_points=False)
    if saved.get("available"):
        assert got["thesis"]["map_pct"] == saved["plain"]["map_pct"] == {"10": 9.7, "20": 27.7, "30": 45.9}


def test_live_reach_route_caches_each_hospital_isochrone(monkeypatch):
    from app.emergency import router as er
    calls = _mock(monkeypatch)
    monkeypatch.setattr(er, "_ISO", {})
    c = TestClient(app)
    a = c.get("/api/emergency/reach/dhaka/live", params={"lat": 23.75, "lon": 90.40, "k": 2}).json()
    b = c.get("/api/emergency/reach/dhaka/live", params={"lat": 23.751, "lon": 90.401, "k": 2}).json()
    assert a["isochrones_cached"] == 0 and b["isochrones_cached"] == 2 and calls["iso"] == 2
    assert c.get("/api/emergency/reach/dhaka/live", params={"lat": 23.75, "lon": 90.40, "k": 99}).json()["hospitals"].__len__() == 2
