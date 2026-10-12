"""The Amazon Location provider: record shape, congestion bands from span times, coverage flag, provider order. No network."""
from core.common.data.live_providers import amazon_location as al, live


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
    from core.common.data.live_providers import google_routes
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


def test_a_free_flow_answer_is_answered_but_not_live(monkeypatch):
    """Dhaka through Amazon Location: the same 251 s with traffic on, off, at peak and a week ahead (checked 2026-10-04)."""
    line = [[90.38, 23.75], [90.381, 23.751]]
    flat = {"Routes": [_route([{"GeometryOffset": 0, "Duration": 251, "BestCaseDuration": 251, "TypicalDuration": 251}], line)]}
    moving = {"Routes": [_route([{"GeometryOffset": 0, "Duration": 548, "BestCaseDuration": 417, "TypicalDuration": 519}], line)]}
    monkeypatch.setattr(type(al.service), "configured", property(lambda self: True))
    for payload, is_live, words in ((flat, False, "free-flow estimate"), (moving, True, "traffic-aware")):
        monkeypatch.setattr(al.service, "_client", lambda p=payload: type("C", (), {"calculate_routes": lambda self, **kw: p})())
        r = al.service.routes((23.75, 90.38), (23.74, 90.39))
        c = al.service.corridor_from({"id": "x", "origin": {"lat": 23.75, "lng": 90.38}, "destination": {"lat": 23.74, "lng": 90.39}})
        assert r["answered"] and c["answered"] and live.answered(r) and r["routes"]            # the roads and the time are usable
        assert r["is_live"] is is_live and c["is_live"] is is_live                              # but only real traffic is called live
        assert words in r["routing_preference"] and words in c["routing_preference"] and "HERE" not in r["routing_preference"]
    assert "free-flow road times" in live.traffic_words({"source": "amazon_location", "traffic_coverage": False})


def test_provider_sampling_is_paused_and_provider_rows_are_never_own_history(monkeypatch, tmp_path):
    from core.common.data.live_providers import observatory as obs
    monkeypatch.setattr(obs, "DB", tmp_path / "o.sqlite")
    monkeypatch.setattr(type(al.service), "configured", property(lambda self: True))
    monkeypatch.setattr(al.service, "corridors_for", lambda city: (_ for _ in ()).throw(AssertionError("a paid call was made")))
    monkeypatch.delenv(obs.PROVIDER_SAMPLING_ENV, raising=False)
    o = obs.Observatory()
    assert o.sample("dhaka")["status"] == "PAUSED"                                              # no request leaves the machine
    import time
    now = time.time()
    with o._conn() as c:
        for age_days, provider in ((1, "amazon_location"), (31, "amazon_location"), (32, "probes")):
            c.execute("INSERT INTO samples (city, t, utc, nodes, values_json, provider) VALUES (?,?,?,?,?,?)",
                      ("dhaka", now - age_days * 86400, "2026-10-01T00:00:00+00:00", '["a"]', "[12.5]", provider))
    with o._conn() as c:                                                                        # opening the store applies the 30-day limit
        kept = sorted(r[0] for r in c.execute("SELECT provider FROM samples"))
    assert kept == ["amazon_location", "probes"]
    own = o.own_history("dhaka")
    assert own["steps_own"] == 1 and own["steps_total"] == 2 and "Amazon Location" in own["rule"]


def test_no_google_api_is_called_from_any_of_the_three_request_sites(monkeypatch):
    import urllib.request
    from core.common.data.live_providers import google_guard, google_providers, google_routes
    from core.simulation.routing import route_advisor
    monkeypatch.delenv(google_guard.ALLOW_ENV, raising=False)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "a-key-is-present")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a request reached Google")))
    assert google_routes.service.configured is False and live.provider() is not google_routes.service
    assert google_routes._http("https://routes.googleapis.com/x", b"{}", {})[1] == "GOOGLE_CALLS_DISABLED"
    for module in (google_providers, route_advisor):
        src = __import__("inspect").getsource(module)
        assert src.count("urllib.request.urlopen(") == src.count("google_guard.check()\n    with urllib.request.urlopen(") == 1

