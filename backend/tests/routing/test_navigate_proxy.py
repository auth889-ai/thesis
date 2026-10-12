"""The navigation proxy: Ferrostar's Valhalla request forwarded unchanged and the answer returned unchanged; other costings, oversize
bodies and cities without a server refused."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from core.simulation.routing import valhalla

BODY = {"locations": [{"lat": 23.81, "lon": 90.41}, {"lat": 23.73, "lon": 90.39}], "costing": "motorcycle", "format": "osrm", "banner_instructions": True, "voice_instructions": True}


def test_forwarded_unchanged(monkeypatch):
    seen = {}
    monkeypatch.setattr(valhalla, "_server", lambda city, profile="car": (None, "http://engine", "auto"))
    def ask(city, url, body, action, timeout=15):
        seen.update(body=body, action=action, url=url)
        return None, {"code": "Ok", "routes": [{"distance": 12320}]}
    monkeypatch.setattr(valhalla, "_ask", ask)
    r = TestClient(app).post("/api/navigate/dhaka/route", content=json.dumps(BODY))
    assert r.status_code == 200 and r.json() == {"code": "Ok", "routes": [{"distance": 12320}]}
    assert seen == {"body": BODY, "action": "route", "url": "http://engine"}


def test_refusals(monkeypatch):
    c = TestClient(app)
    assert c.post("/api/navigate/dhaka/route", content=json.dumps({**BODY, "costing": "truck"})).status_code == 422
    assert c.post("/api/navigate/dhaka/route", content=b"{" + b" " * 70000 + b"}").status_code == 413
    assert c.post("/api/navigate/dhaka/route", content=b"not json").status_code == 422
    monkeypatch.setattr(valhalla, "_server", lambda city, profile="car": ({"available": False, "code": "no_engine", "note": "no data for this city"}, "", ""))
    r = c.post("/api/navigate/rangpur/route", content=json.dumps(BODY))
    assert r.status_code == 503 and r.json()["code"] == "no_engine"
