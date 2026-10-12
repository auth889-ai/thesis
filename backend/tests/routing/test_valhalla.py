"""Whole-city routes through Valhalla: the answer read faithfully, recorded stretches re-timed and labelled, honest refusals."""
from __future__ import annotations

import ast
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient

from core.common import credentials
from core.common.data import city_config, real_speeds
from app.main import app
from core.simulation.routing import valhalla


def encode6(points: list[tuple[float, float]]) -> str:
    """Google's polyline encoding at precision 6, (lat, lon) pairs; the inverse of valhalla.decode_polyline6."""
    out, last = [], (0, 0)
    for lat, lon in points:
        cur = (round(lat * 1e6), round(lon * 1e6))
        for v in (cur[0] - last[0], cur[1] - last[1]):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63)); v >>= 5
            out.append(chr(v + 63))
        last = cur
    return "".join(out)


SHAPE = [(23.80, 90.40), (23.79, 90.40), (23.78, 90.41), (23.77, 90.41)]           # 4 points, roughly 3.4 km, heading south
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/valhalla_route.json"


def fake_answer() -> dict:
    leg = {"shape": encode6(SHAPE), "summary": {"length": 3.4, "time": 420},
           "maneuvers": [{"instruction": "Drive south.", "length": 1.1, "time": 130, "type": 1, "street_names": ["Airport Road"]},
                         {"instruction": "Turn left.", "length": 2.3, "time": 290, "type": 15, "street_names": []}]}
    alt = {"shape": encode6([(23.80, 90.40), (23.785, 90.395), (23.77, 90.41)]), "summary": {"length": 3.9, "time": 470}, "maneuvers": [{"instruction": "Drive.", "length": 3.9, "time": 470, "type": 1}]}
    return {"trip": {"legs": [leg], "summary": {"length": 3.4, "time": 420}, "status": 0, "units": "kilometers"},
            "alternates": [{"trip": {"legs": [alt], "summary": {"length": 3.9, "time": 470}}}]}


@pytest.fixture
def served(monkeypatch):
    """A city with a routing server whose answer is the document above (hand-made until a real one is recorded)."""
    if not FIXTURE.exists():
        FIXTURE.write_text(json.dumps({"_note": "hand-made minimal Valhalla answer for tests; replace with a recorded one from the server", **fake_answer()}, indent=1))
    answer = json.loads(FIXTURE.read_text())
    calls = []
    def urlopen(req, timeout=0):
        calls.append(json.loads(req.data.decode()))
        return io.BytesIO(json.dumps(answer).encode())
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: _ctx(urlopen(req, timeout)))
    monkeypatch.setattr(credentials, "load", lambda var: "http://routing.test:8002" if var == "URL_TOWN" else "")
    routing = NS(engine="valhalla", url_env="URL_TOWN", extract="x/town", extract_date="2026-10-04", credit="© OpenStreetMap contributors · Valhalla")
    monkeypatch.setattr(city_config, "load", lambda cid, *a: NS(routing=routing, time_zone="Asia/Dhaka", live=None) if cid == "town" else NS(routing=None, time_zone=None, live=None))
    monkeypatch.setattr(real_speeds, "recorded_sources", lambda cid, net=None, bbox=None: [])
    return calls


class _ctx:
    def __init__(self, f): self.f = f
    def __enter__(self): return self.f
    def __exit__(self, *a): return False


def test_the_polyline_decoder_inverts_the_encoding():
    assert [[round(x, 6), round(y, 6)] for x, y in valhalla.decode_polyline6(encode6(SHAPE))] == [[lon, lat] for lat, lon in SHAPE]


def test_routes_alternatives_and_maneuvers_are_read_and_times_are_labelled_map_speeds(served):
    r = valhalla.route("town", (23.80, 90.40), (23.77, 90.41), profile="motorcycle", at="08:30")
    assert r["available"] and r["engine"] == "Valhalla" and r["profile"] == "motorcycle" and r["credit"].startswith("©")
    assert served[0]["costing"] == "motorcycle" and served[0]["alternates"] == 2
    assert [x["summary"]["length_m"] for x in r["routes"]] == [3400, 3900] and [x["summary"]["time_s"] for x in r["routes"]] == [420, 470]
    assert all(x["summary"]["time_source"] == "map speeds, not live traffic" and x["recorded"] == [] for x in r["routes"])
    assert [m["instruction"] for m in r["routes"][0]["maneuvers"]] == ["Drive south.", "Turn left."] and r["routes"][0]["maneuvers"][0]["length_m"] == 1100
    assert len(r["routes"][0]["geometry"]) == 4


def test_a_recorded_site_on_the_route_retimes_its_stretch_and_says_so(served, monkeypatch):
    site = {"site": "CAM", "day": "2026-04-20", "located": True, "lat": 23.79, "lon": 90.40, "bearing_deg": 180.0}    # on the shape's second point, heading south
    off = {"site": "FAR", "day": "2026-04-20", "located": True, "lat": 23.79, "lon": 90.45, "bearing_deg": 180.0}     # 5 km east: not on the route
    reader = NS(NAME="fakecam", reading_at=lambda s, at: {"start": "08:30", "median_kmh": 10.0, "vehicles": 40, "stretch_m": 100.0} if s == "CAM" else None)
    monkeypatch.setattr(real_speeds, "_readers", lambda: {"fakecam": reader})
    monkeypatch.setattr(real_speeds, "recorded_sources", lambda cid, net=None, bbox=None: [{"kind": "researcher", "state": "active", "note": "x"},
                                                                                           {"dataset": "fakecam", "citation": "Cam et al.", "licence": "CC BY 4.0", "sites": [site, off]}])
    r = valhalla.route("town", (23.80, 90.40), (23.77, 90.41), at="08:31")
    first = r["routes"][0]
    assert [s["site"] for s in first["recorded"]] == ["CAM"]
    s = first["recorded"][0]
    map_speed = 3400 / 420
    assert s["time_s_before"] == round(100 / map_speed, 1) and s["time_s_after"] == round(100 / (10 / 3.6), 1) and s["citation"] == "Cam et al."
    assert first["summary"]["time_with_recorded_s"] == round(420 - 100 / map_speed + 100 / (10 / 3.6))
    assert "recorded there at 08:31" in first["summary"]["recorded_note"] and first["summary"]["time_s"] == 420       # the map time stays beside it
    # a site heading the other way is not matched
    site["bearing_deg"] = 0.0
    assert valhalla.route("town", (23.80, 90.40), (23.77, 90.41), at="08:31")["routes"][0]["recorded"] == []


def test_refusals_are_honest(served, monkeypatch):
    assert valhalla.route("elsewhere", (0, 0), (1, 1))["code"] == "no_engine"
    monkeypatch.setattr(credentials, "load", lambda var: "")
    assert valhalla.route("town", (0, 0), (1, 1))["code"] == "engine_not_configured"
    monkeypatch.setattr(credentials, "load", lambda var: "http://routing.test:8002")
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.URLError("refused")))
    assert valhalla.route("town", (0, 0), (1, 1))["code"] == "engine_down"
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=0: (_ for _ in ()).throw(urllib.error.HTTPError("u", 400, "Bad Request", {}, io.BytesIO(b'{"error":"No path could be found"}'))))
    assert valhalla.route("town", (0, 0), (1, 1))["code"] == "no_path"
    assert valhalla.route("town", (0, 0), (1, 1), profile="rocket")["code"] == "bad_profile"


def test_the_endpoint_checks_its_inputs_and_names_the_city():
    c = TestClient(app)
    assert c.get("/api/route/berlin?origin=52.5,13.4&destination=52.52,13.41").json()["code"] == "no_engine"
    assert c.get("/api/route/berlin?origin=x&destination=1,2").status_code == 422
    assert c.get("/api/route/berlin?origin=1,2&destination=3,4&at=25:00").status_code == 422


def test_the_client_sends_nothing_anywhere_else_and_names_no_city():
    src = Path(valhalla.__file__).read_text()
    tree = ast.parse(src)
    names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not {n for n in names if n.split(".")[0] in {"requests", "httpx", "boto3", "smtplib", "socket", "twilio"}}
    body = src.split('"""', 2)[2].lower().replace("dhakaflow", "")                                   # after the module docstring; "dhakaflow" is the project's name, not a city
    assert not any(w in body for w in ("dhaka", "los angeles", "berlin", "bangladesh")), "the client is city-agnostic"
