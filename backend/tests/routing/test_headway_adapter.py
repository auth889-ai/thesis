"""The map app's adapters (backend/app/routing/headway_adapter.py): they translate our services into what Headway's web frontend
expects and decide nothing else. No network: inputs are fixed dicts."""
from __future__ import annotations

import json

from core.common.paths import REPO
from app.routing import headway_adapter as H


def test_style_points_headway_at_our_provider_with_bengali_fonts():
    provider = {"sources": {"ne": {"type": "raster", "tiles": ["x"]}, "openmaptiles": {"type": "vector", "url": "https://tiles.example/planet"}},
                "glyphs": "https://tiles.example/fonts/{fontstack}/{range}.pbf"}
    headway = json.loads((REPO / "frontend/map/upstream/tileserver/styles/basic-v3.json").read_text())
    s = H.style_for(provider, headway, "https://host/")
    assert s["sources"] == {"openmaptiles": {"type": "vector", "url": "https://tiles.example/planet"}}
    assert s["glyphs"] == provider["glyphs"] and s["sprite"] == "https://host/tileserver/sprite/sprites"
    assert all(l.get("source") in (None, "openmaptiles") for l in s["layers"])
    fonts = {f for l in s["layers"] for f in (l.get("layout") or {}).get("text-font", []) if isinstance(f, str)}
    assert fonts <= {"Noto Sans Regular", "Noto Sans Bold", "Noto Sans Italic"}                 # the provider's Noto Sans covers Bengali
    assert set(s["metadata"]["traffictwin"]["layers_left_out"]) == {l["id"] for l in headway["layers"] if l.get("source") in ("landcover", "terrain")}
    assert headway["sources"]["openmaptiles"]["url"] == "/areamap-mlt"                          # Headway's own file is not edited


def test_photon_feature_becomes_the_pelias_feature_headway_reads():
    f = {"geometry": {"type": "Point", "coordinates": [90.3976, 23.7255]},
         "properties": {"osm_type": "W", "osm_id": 1049690948, "osm_key": "amenity", "osm_value": "hospital", "name": "Dhaka Medical College Hospital",
                        "district": "Bokshibazar", "city": "Dhaka", "state": "Dhaka Division", "country": "Bangladesh", "countrycode": "bd",
                        "extent": [90.39, 23.73, 90.40, 23.72]}}
    p = H.from_photon(f)
    assert p["properties"]["gid"] == "openstreetmap:venue:way/1049690948"
    assert p["properties"]["country_code"] == "BD" and p["properties"]["name"] == "Dhaka Medical College Hospital"
    assert p["properties"]["label"].startswith("Dhaka Medical College Hospital, Bokshibazar, Dhaka")
    assert p["bbox"] == [90.39, 23.72, 90.40, 23.73]
    assert H.from_photon({"geometry": {}, "properties": {"name": "x"}}) is None


def test_nominatim_hit_carries_phone_website_and_hours_for_the_card():
    h = {"osm_type": "node", "osm_id": 42, "class": "amenity", "lat": "23.7", "lon": "90.4", "name": "Clinic", "display_name": "Clinic, Road, Dhaka",
         "address": {"country_code": "bd", "road": "Road", "city": "Dhaka"}, "extratags": {"phone": "+880 1", "opening_hours": "24/7"},
         "boundingbox": ["23.69", "23.71", "90.39", "90.41"]}
    p = H.from_nominatim(h)["properties"]
    assert p["gid"] == "openstreetmap:venue:node/42" and p["addendum"] == {"osm": {"phone": "+880 1", "opening_hours": "24/7"}}
    assert H.from_nominatim({**h, "type": "clinic"})["properties"]["category"] == ["clinic"]
    assert H.from_nominatim({**h, "extratags": {}})["properties"].get("addendum") is None


def test_a_point_belongs_to_the_nearest_routed_city_or_to_none():
    centre = {"dhaka": (23.78, 90.40), "los_angeles": (34.05, -118.24)}.get
    assert H.city_at(23.75, 90.39, ["dhaka", "los_angeles"], centre) == "dhaka"
    assert H.city_at(34.0, -118.3, ["dhaka", "los_angeles"], centre) == "los_angeles"
    assert H.city_at(52.52, 13.40, ["dhaka", "los_angeles"], centre) is None                    # Berlin: no routed city, never another city's


def test_directions_outside_every_routed_city_say_no_data(client, monkeypatch):
    monkeypatch.setattr(H, "city_at", lambda lat, lng, *a, **k: None)
    r = client.get("/travelmux/v8/plan", params={"fromPlace": "13.40,52.52", "toPlace": "13.41,52.53", "mode": "CAR"})
    assert r.status_code == 404 and "no data for this city" in r.json()["error"]["message"]
    monkeypatch.setattr(H, "city_at", lambda lat, lng, *a, **k: None)
    assert client.get("/api/map/city", params={"lat": 52.52, "lng": 13.40}).json()["available"] is False


def test_headway_config_has_no_transit_and_no_hard_bounds(client, monkeypatch):
    monkeypatch.setattr(H, "routed_cities", lambda: [])
    c = client.get("/static/headway-config.json").json()
    assert c["transitRoutingEnabled"] is False and c["maxBounds"] is None and c["initialCenter"] is None


def test_old_links_open_the_same_page_under_app(client):
    r = client.get("/lab/evidence?x=1", follow_redirects=False)
    assert r.status_code == 308 and r.headers["location"].endswith("/app/lab/evidence?x=1")
    assert client.get("/emergency", follow_redirects=False).headers["location"].endswith("/app/emergency")
