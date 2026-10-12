"""Map matching on the city's own routing server: the trace answer read into the snapped fields; the server chosen before a provider; nothing invented when it is silent."""
from __future__ import annotations

from app.probes import snap
from core.simulation.routing import valhalla

FIXES = [{"lat": 23.7788, "lng": 90.4000, "recorded_at": "2026-10-06T08:00:00Z"}, {"lat": 23.7810, "lng": 90.4010, "recorded_at": "2026-10-06T08:00:10Z"}]


def test_trace_answer_becomes_snapped_fields(monkeypatch):
    monkeypatch.setattr(valhalla, "trace", lambda city, pts, profile="car": {"available": True, "matched": [
        {"lat": 23.779005, "lng": 90.399868, "type": "matched", "way_id": 33784477, "name": "Mohakhali School Road", "moved_m": 26.4},
        {"lat": 23.781349, "lng": 90.401021, "type": "interpolated", "way_id": 35475461, "name": None, "moved_m": 38.6}]})
    out = snap.ValhallaSnap("dhaka").snap(FIXES)
    assert [(p["snapped_lat"], p["snap_confidence"], p["way_id"]) for p in out] == [(23.779005, 1.0, 33784477), (23.781349, 0.5, 35475461)]


def test_a_silent_server_leaves_points_unsnapped(monkeypatch):
    monkeypatch.setattr(valhalla, "trace", lambda city, pts, profile="car": {"available": False, "code": "engine_down", "note": "x"})
    out = snap.ValhallaSnap("dhaka").snap(FIXES)
    assert all(p["snapped_lat"] is None and p["snap_confidence"] is None for p in out)


def test_the_city_server_is_chosen_before_a_provider(monkeypatch):
    monkeypatch.setattr(valhalla, "_server", lambda city, profile="car": (None, "http://x", "auto") if city == "dhaka" else ({"code": "no_engine"}, "", ""))
    monkeypatch.setattr(snap.AmazonSnap, "configured", property(lambda self: False))
    assert snap.default("dhaka").name == "valhalla"
    assert snap.default("rangpur").name == "none"
    assert snap.default().name == "none"
