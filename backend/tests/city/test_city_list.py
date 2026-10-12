"""The city list a fresh visitor loads first: one bad config file must not take it down (a test user saw 500, no city, and 'loading…')."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from core.common.data import city_config
from app.main import app

GOOD = (Path(__file__).resolve().parents[3] / "config/cities/dhaka.yaml").read_text()


def test_the_city_list_is_served_even_when_one_config_is_broken(tmp_path, monkeypatch):
    (tmp_path / "dhaka.yaml").write_text(GOOD)
    (tmp_path / "broken.yaml").write_text("city_id: broken\ndisplay_name: {en: Broken}\nnot_a_field: 1\n")
    list_ids, load = city_config.list_ids, city_config.load                  # the functions bind the directory at import, so they are pointed at the folder here
    monkeypatch.setattr(city_config, "list_ids", lambda directory=tmp_path: list_ids(tmp_path))
    monkeypatch.setattr(city_config, "load", lambda city_id, directory=tmp_path: load(city_id, tmp_path))
    r = TestClient(app).get("/api/operate/cities")
    assert r.status_code == 200
    body = r.json()
    ids = [c["id"] for c in body["configured"]]
    assert "dhaka" in ids and "broken" not in ids
    assert "broken" in body["problems"]
    assert sum(c["default"] for c in body["configured"]) == 1          # a fresh visitor always gets one selected city


def test_a_fresh_visitor_gets_a_default_city_from_the_checked_in_configs():
    body = TestClient(app).get("/api/operate/cities").json()
    assert body["problems"] == {}, body["problems"]
    defaults = [c for c in body["configured"] if c["default"]]
    assert len(defaults) == 1 and defaults[0]["center"] is not None
