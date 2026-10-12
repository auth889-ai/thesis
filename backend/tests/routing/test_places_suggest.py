"""Place suggestions: Photon for search-as-you-type (Nominatim's policy forbids it), bounded to the city, cached, paced; nothing asked for short text or coordinates."""
from __future__ import annotations

import io
import json
import urllib.request

import pytest

from core.simulation.routing.trip import places


def photon_answer(name, lon, lat, where="Dhaka"):
    return {"features": [{"geometry": {"coordinates": [lon, lat]}, "properties": {"name": name, "district": where, "osm_key": "place", "osm_value": "suburb"}}]}


@pytest.fixture
def geocoders(monkeypatch):
    asked = []
    def fake_open(req, timeout=0):
        asked.append(req.full_url)
        assert req.get_header("User-agent", "").startswith("traffictwin/1.0 (research")      # the policy: an identifying User-Agent, never a stock one
        assert req.full_url.startswith(places.PHOTON_URL), "suggestions must never go to Nominatim"
        return io.BytesIO(json.dumps(photon_answer("Motijheel", 90.4212, 23.7273)).encode())
    monkeypatch.setattr(urllib.request, "urlopen", fake_open)
    monkeypatch.setattr(places, "city_box", lambda c: {"label": "Dhaka", "lat": 23.78, "lng": 90.40, "bbox": [90.30, 23.66, 90.52, 23.92]})
    places._SUGGEST_CACHE.clear()
    return asked


def test_short_text_and_coordinates_ask_no_geocoder(geocoders):
    assert places.suggest("berlin", "Mo") == []
    assert places.suggest("berlin", "23.81, 90.41") == []
    assert places.suggest("berlin", "   ") == []
    assert geocoders == []


def test_photon_bounded_to_the_city_and_cached(geocoders):
    out = places.suggest("berlin", "Motijheel")
    assert out == [{"label": "Motijheel, Dhaka", "lat": 23.7273, "lng": 90.4212, "source": "OpenStreetMap (Photon)"}]
    assert "bbox=90.3%2C23.66%2C90.52%2C23.92" in geocoders[0] and "q=Motijheel" in geocoders[0]
    places.suggest("berlin", "Motijheel")
    assert len(geocoders) == 1                                                                  # the same text again is served from the cache


def test_pacing_at_most_one_request_per_second(geocoders, monkeypatch):
    slept = []
    import time
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))
    places._SUGGEST_LAST[0] = time.monotonic()
    places.suggest("berlin", "Motijheel")
    assert slept and 0.9 <= slept[0] <= 1.0


def test_a_silent_geocoder_means_no_suggestions_not_another_geocoder(monkeypatch):
    def down(req, timeout=0):
        raise OSError("down")
    monkeypatch.setattr(urllib.request, "urlopen", down)
    monkeypatch.setattr(places, "city_box", lambda c: {"label": "Dhaka", "lat": 23.78, "lng": 90.40, "bbox": [90.30, 23.66, 90.52, 23.92]})
    places._SUGGEST_CACHE.clear()
    assert places.suggest("berlin", "Motijheel") == []
