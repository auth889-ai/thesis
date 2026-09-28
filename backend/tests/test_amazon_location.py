"""The Amazon Location provider: record shape, congestion bands from span times, coverage flag, provider order. No network."""
from app.data.live_providers import amazon_location as al, live


def _route(spans, line):
    return {"Summary": {"Distance": 3000, "Duration": sum(s["Duration"] for s in spans)},
            "Legs": [{"Geometry": {"LineString": line}, "VehicleLegDetails": {"Spans": spans}}]}


def test_route_record_colours_spans_by_live_over_best_case_and_flags_coverage():
    line = [[90.38, 23.75], [90.381, 23.751], [90.382, 23.752], [90.383, 23.753]]
    spans = [{"GeometryOffset": 0, "Duration": 60, "BestCaseDuration": 60, "TypicalDuration": 60}, {"GeometryOffset": 2, "Duration": 100, "BestCaseDuration": 60, "TypicalDuration": 90}]
    rec = al._route_record(_route(spans, line))
    assert rec["duration_s"] == 160 and rec["static_duration_s"] == 120 and rec["category"] == "SLOW" and rec["traffic_coverage"] is True
    assert [s["speed"] for s in rec["segments"]] == ["NORMAL", "TRAFFIC_JAM"]
    assert rec["geometry"][0] == [23.75, 90.38], "geometry is [lat, lng] for the map"


def test_no_traffic_coverage_is_reported_not_hidden():
    line = [[90.38, 23.75], [90.381, 23.751]]
    rec = al._route_record(_route([{"GeometryOffset": 0, "Duration": 251, "BestCaseDuration": 251, "TypicalDuration": 251}], line))
    assert rec["traffic_coverage"] is False and rec["category"] == "NORMAL" and rec["traffic_penalty_s"] == 0


def test_provider_order_prefers_amazon_then_google_then_none(monkeypatch):
    from app.data.live_providers import google_routes
    monkeypatch.setattr(type(al.service), "configured", property(lambda self: True))
    assert live.provider() is al.service
    monkeypatch.setattr(type(al.service), "configured", property(lambda self: False))
    monkeypatch.setattr(type(google_routes.service), "configured", property(lambda self: False))
    assert live.provider() is None


def test_traffic_words_say_when_a_city_has_no_live_coverage():
    assert "no live traffic coverage" in live.traffic_words({"source": "amazon_location", "traffic_coverage": False})
    assert "live traffic on this trip" in live.traffic_words({"source": "amazon_location", "traffic_coverage": True})
    assert "recorded" in live.traffic_words({"source": "local_sumo_router"}, "RECORDED corridor states as of x").lower()


def test_missing_credentials_never_call_aws(monkeypatch):
    monkeypatch.setattr(type(al.service), "configured", property(lambda self: False))
    r = al.service.routes((23.75, 90.38), (23.74, 90.39))
    assert r["is_live"] is False and r["request_status"] == "NO_CREDENTIALS" and r["routes"] == []
