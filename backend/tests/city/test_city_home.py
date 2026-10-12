"""The everyday home's backend: a route on a city's own network, real speeds or nothing, a forecast only from an
unbroken series, every traffic value tagged, and an alerts feed that keeps cities apart."""
from __future__ import annotations

import ast
import inspect
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from core.common import tag
from core.common.data import real_speeds
from core.ml.forecasting.adapters.base import Forecast, NotAvailable
from core.ml.forecasting.operations import section_forecast
from core.simulation.routing import city_router
from app.routing import city_trip
from app.data import probe_speeds

NOW = datetime(2026, 10, 5, 9, 2, tzinfo=timezone.utc)
OSM = """<osm version="0.6">
 <node id="1" lat="47.1400" lon="9.5200"/><node id="2" lat="47.1400" lon="9.5260"/><node id="3" lat="47.1400" lon="9.5320"/><node id="4" lat="47.1440" lon="9.5260"/>
 <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/><tag k="maxspeed" v="60"/></way>
 <way id="11"><nd ref="2"/><nd ref="3"/><tag k="highway" v="primary"/><tag k="maxspeed" v="60"/></way>
 <way id="12"><nd ref="2"/><nd ref="4"/><tag k="highway" v="residential"/></way>
</osm>"""
WEST, EAST, NORTH = (47.1400, 9.5205), (47.1400, 9.5315), (47.1435, 9.5260)


@pytest.fixture(scope="module")
def cities(tmp_path_factory):
    """A three-road town built by SUMO's own netconvert, laid out as the city pipeline lays a city out."""
    if not shutil.which("netconvert"):
        pytest.skip("SUMO's netconvert is not installed")
    root = tmp_path_factory.mktemp("cities")
    folder = root / "town" / "sumo"
    folder.mkdir(parents=True)
    (folder / "town.osm.xml").write_text(OSM)
    subprocess.run(["netconvert", "--osm-files", str(folder / "town.osm.xml"), "--output-file", str(folder / "town.net.xml"), "--no-warnings"], check=True, capture_output=True)
    (folder / "MANIFEST.json").write_text(json.dumps({"city_id": "town", "bbox": [47.13, 9.51, 47.15, 9.54], "network_reality": "REAL", "generated_utc": "2026-10-05T00:00:00+00:00",
                                                     "files": {"net": str(folder / "town.net.xml")}}))
    return root


@pytest.fixture
def db(tmp_path):
    from app.lifeos import db as core
    url = f"sqlite:///{tmp_path}/home.sqlite"
    core.init(url)
    return url


def cell(db, lat, lon, octant, minutes_ago, kmh, phones, city="town"):
    from app.lifeos.db import session
    from app.probes.db import ProbeCellRow
    start = (NOW - timedelta(minutes=minutes_ago)).replace(minute=((NOW - timedelta(minutes=minutes_ago)).minute // 5) * 5, second=0, microsecond=0)
    with session(db) as s:
        s.add(ProbeCellRow(cell=f"c{lat}{lon}:{octant}", bin_start=start, city=city, lat=lat, lng=lon, n_points=6, n_devices=phones, mean_speed_kmh=kmh, p50_speed_kmh=kmh, updated_at=NOW))
        s.commit()


class FakeModel:
    """Stands in for the released model: says the last speed continues, 5 km/h either side. It is never used by the app."""
    def forecast(self, data, horizons):
        last = [float(x) for x in data.values[-1]]
        return Forecast(model="fake", checkpoint=None, dataset_schema="", input_window_steps=len(data.values), output_horizon_steps=12, horizons_min=horizons,
                        values={h: last for h in horizons}, unit="km/h", node_ids=data.node_ids, inference_utc="", city_id=data.city_id,
                        provenance={"lower_q10": {h: [v - 5 for v in last] for h in horizons}, "upper_q90": {h: [v + 5 for v in last] for h in horizons}})


class NoModel:
    def forecast(self, data, horizons):
        raise NotAvailable("none", ["cannot run here"])


def test_the_route_follows_the_citys_own_roads_and_is_the_same_every_time(cities):
    a = city_router.route("town", WEST, EAST, cities)
    assert a == city_router.route("town", WEST, EAST, cities)
    assert len(a["sections"]) == 2 and all(s["limit_kmh"] == 60.0 and 80 < s["heading_deg"] < 100 for s in a["sections"])
    assert 750 < a["length_m"] < 950 and a["length_m"] == round(sum(s["length_m"] for s in a["sections"]), 1)
    turn = city_router.route("town", WEST, NORTH, cities)
    assert turn["sections"][0]["id"] == a["sections"][0]["id"] and turn["sections"][-1]["id"] != a["sections"][-1]["id"]


def test_a_route_is_refused_outside_the_built_area_and_for_a_city_never_built(cities):
    for origin, dest, code in ((WEST, (47.20, 9.53), "outside_area"), ((47.1480, 9.5150), EAST, "no_road_near")):
        with pytest.raises(city_router.Refused) as no:
            city_router.route("town", origin, dest, cities)
        assert no.value.code == code
    with pytest.raises(city_router.Refused) as no:
        city_router.route("nowhere", WEST, EAST, cities)
    assert no.value.code == "no_network" and no.value.message.startswith("no data for this city")


def test_a_reading_needs_three_phones_the_right_direction_and_to_be_recent(cities, db):
    net, man = city_router.network("town", str(cities))
    box = man["bbox"]
    edges = [net.getEdge(s["id"]) for s in city_router.route("town", WEST, EAST, cities)["sections"]]
    first = edges[0].getID()
    cell(db, 47.1400, 9.5230, "2", 2, 30.0, phones=2)                               # two phones: not a reading
    assert probe_speeds.read("town", net, edges, box, NOW, db) == {}
    cell(db, 47.14001, 9.5232, "6", 2, 30.0, phones=5)                              # driving west: the other direction's traffic
    cell(db, 47.1420, 9.5232, "2", 2, 30.0, phones=5)                               # 220 m away: another road
    cell(db, 47.14002, 9.5234, "2", 40, 30.0, phones=5)                             # 40 minutes old: history, not now
    assert probe_speeds.read("town", net, edges, box, NOW, db) == {}
    cell(db, 47.14003, 9.5238, "2", 2, 24.0, phones=3, city="whatever the phone's profile said")   # the position decides, not the label
    got = probe_speeds.read("town", net, edges, box, NOW, db)
    assert list(got) == [first] and got[first]["kmh"] == 24.0
    assert got[first]["tag"]["kind"] == "real" and got[first]["tag"]["phones_at_least"] == 3 and got[first]["tag"]["as_of"].startswith("2026-10-05T09:00")
    assert [r["kmh"] for r in got[first]["series"]] == [30.0, 24.0]                 # the old bin is history; the gap between is not filled


def test_a_forecast_needs_eight_readings_in_a_row_and_a_model_that_runs():
    bins = lambda minutes: [{"bin_start": (NOW - timedelta(minutes=m)).isoformat(), "kmh": 20.0 + i} for i, m in enumerate(minutes)]
    full = {"s": {"series": bins(range(35, -1, -5))}}                               # 8 consecutive bins
    assert section_forecast.unbroken_tail(full["s"]["series"]) == [20.0 + i for i in range(8)]
    gap = {"s": {"series": bins([60, 55, 50, 45, 30, 25, 20, 15, 10, 5, 0])}}       # 11 readings, but only 7 since the gap
    assert len(section_forecast.unbroken_tail(gap["s"]["series"])) == 7
    assert section_forecast.forecast("town", gap, "phones", FakeModel()) == ({}, "too_few_readings")
    assert section_forecast.forecast("town", full, "phones", NoModel()) == ({}, "model_unavailable")
    out, why = section_forecast.forecast("town", full, "phones", FakeModel())
    assert why is None and set(out["s"]) == {"15", "30", "60"}
    f = out["s"]["30"]
    assert f["value"] == 27.0 and f["range"] == [22.0, 32.0] and f["tag"]["kind"] == "forecast" and "uncalibrated" in f["tag"]["uncertainty"] and f["tag"]["readings_used"] == 8


def test_a_trip_without_data_gives_no_traffic_time_and_one_with_data_says_how_much_it_covers(cities, db):
    none = city_trip.trip("town", WEST, EAST, NOW, db, FakeModel(), cities)
    assert none["available"] and none["traffic"] == "none" and none["travel"] == {"0": None, "15": None, "30": None, "60": None}
    assert all(s["now"] is None and s["forecast"] == {} for s in none["sections"])
    assert none["at_limits"]["tag"] == tag.simulated(city_trip.LIMITS_BASIS) and none["at_limits"]["tag"]["calibrated_to"] == "uncalibrated"
    assert tag.untagged(none) == []
    for m in range(35, -1, -5):
        cell(db, 47.1400 + m * 1e-7, 9.5230, "2", m + 2, 30.0, phones=4)            # 8 bins in a row on the first section only
    some = city_trip.trip("town", WEST, EAST, NOW, db, FakeModel(), cities)
    first, second = some["sections"]
    assert first["now"]["value"] == 30.0 and second["now"] is None and second["forecast"] == {}
    now = some["travel"]["0"]
    share = round(first["length_m"] / some["length_m"], 3)
    assert now["tag"]["kind"] == "real" and now["tag"]["covers_share_of_length"] == share and now["tag"]["rest"] == city_trip.REST
    assert now["value"] == round(first["length_m"] / 1000 / 30 * 60 + second["length_m"] / 1000 / 60 * 60, 1)
    later = some["travel"]["30"]
    assert later["tag"]["kind"] == "forecast" and later["range"][0] < later["value"] < later["range"][1]
    assert tag.untagged(some) == [] and some["no_forecast_because"] is None
    assert city_trip.trip("nowhere", WEST, EAST, NOW, db, None, cities) == {"city_id": "nowhere", "available": False, "code": "no_network", "note": "no data for this city: no road network has been built for it"}


def test_a_number_without_a_tag_is_found():
    assert tag.untagged({"a": {"value": 3, "unit": "min", "tag": tag.real("x", "t")}, "geometry": [[1.0, 2.0]]}) == []
    assert tag.untagged({"a": {"speed": 3.5}, "b": [{"value": 1, "tag": {"kind": "guess"}}], "ok": True}) == [".a.speed", ".b[0]"]


def test_the_feed_lists_a_citys_own_alerts_only_and_stamps_them(db):
    from app.alerts import service
    from app.alerts.db import RoadAlertRow, RoadWatchRow
    from core.common.data import city_config
    from app.lifeos.db import session
    owner = next(c for c in map(city_config.load, city_config.list_ids()) if any(d.kind == "sensor_benchmark" for d in c.datasets))
    other = next(c for c in map(city_config.load, city_config.list_ids()) if not any(d.kind == "sensor_benchmark" for d in c.datasets))
    dataset = next(d.id for d in owner.datasets if d.kind == "sensor_benchmark")
    with session(db) as s:
        s.add(RoadWatchRow(id="w1", person_id="p", dataset=dataset, node="S7", label="Ramp 7", created_at=NOW))
        s.commit()
        s.add(RoadAlertRow(id="a1", watch_id="w1", as_of=20000, model="m", horizon_min=30, now_speed=60.0, predicted_speed=31.0, threshold=40.0, created_at=NOW))
        s.commit()
    mine = service.feed(owner.city_id, db_url=db)
    assert [i["kind"] for i in mine["items"]] == ["congestion_onset"] and mine["items"][0]["stamp"] == "RECORDED DATA"
    assert mine["items"][0]["key"] == "alerts.onset" and mine["items"][0]["values"] == {"road": "Ramp 7", "minutes": 30}
    assert mine["items"][0]["tag"]["kind"] == "forecast" and "not today's traffic" in mine["items"][0]["tag"]["based_on"] and tag.untagged(mine) == []
    assert service.feed(other.city_id, db_url=db)["items"] == [] and service.feed("no_such_city", db_url=db)["items"] == []
    assert {k["kind"]: k["built"] for k in mine["kinds"]} == {"congestion_onset": True, "ambulance": True, "mesh": True, "sos": True}   # sos: TEST alerts raised on this machine (Q2)


def test_the_endpoints_answer_for_a_city_without_a_network_and_refuse_bad_coordinates(client):
    from core.common.data import city_config
    unbuilt = next(c.city_id for c in map(city_config.load, city_config.list_ids()) if c.bounding_box is None)
    r = client.get(f"/api/trip/{unbuilt}", params={"origin": "1,2", "destination": "1,3"}).json()
    assert r["available"] is False and r["code"] == "no_network"
    assert client.get(f"/api/trip/{unbuilt}", params={"origin": "here", "destination": "1,3"}).status_code == 422
    assert client.get("/api/alerts/feed", params={"city_id": unbuilt}).json()["items"] == []


def test_only_the_listed_researcher_device_is_exempt_from_the_three_phone_rule(cities, db, tmp_path, monkeypatch):
    from core.common.data import researcher
    from app.probes import service
    listed = tmp_path / "researcher_devices.txt"
    monkeypatch.setenv(researcher.FILE_ENV, str(listed))
    net, man = city_router.network("town", str(cities))
    edges = [net.getEdge(s["id"]) for s in city_router.route("town", WEST, EAST, cities)["sections"]]
    trace = lambda: [{"lat": 47.1400, "lng": 9.5225 + i * 0.0002, "recorded_at": (NOW - timedelta(seconds=60 - 10 * i)).isoformat(), "accuracy_m": 8.0, "heading": 90.0, "speed_kmh": 21.0} for i in range(6)]

    class NoSnap:
        name = "none"
        snap = staticmethod(lambda pts: pts)
    service.ingest("someone-else", "town", trace(), snapper=NoSnap, db_url=db)             # no file: nobody is exempt
    assert probe_speeds.read("town", net, edges, man["bbox"], NOW, db) == {} and not researcher.devices()
    listed.write_text(service.device_hash("the-researcher") + "   # mine\n")
    service.ingest("the-researcher", "town", trace(), snapper=NoSnap, db_url=db)
    got = probe_speeds.read("town", net, edges, man["bbox"], NOW, db)
    assert got and all(r["tag"]["researcher"] is True and r["tag"]["source"] == researcher.SOURCE and r["kmh"] == 21.0 for r in got.values())
    assert all(c["cell"].endswith(":r") or c["n_devices"] == 1 for c in service.cells("town", 10 ** 6, db)["cells"])
    assert {"kind": "researcher", "state": "active", "note": researcher.SOURCE} in probe_speeds.sources("town", man["bbox"], db)
    listed.unlink()                                                                        # on a machine without the file the same cells are not shown
    assert probe_speeds.read("town", net, edges, man["bbox"], NOW, db) == {}


class FakeDataset:
    """A recorded dataset with one site on the town's eastbound main road, one on no road, and one with no stated place."""
    NAME, VERSION, CITATION, LICENCE, CAVEAT = "FakeCam", "1", "Someone. FakeCam. CC BY 4.0.", "CC BY 4.0", "a test"
    available = staticmethod(lambda: True)
    sites = staticmethod(lambda: ({"site": "E", "day": "2026-04-20", "located": True, "lat": 47.14001, "lon": 9.5230, "bearing_deg": 92.0},
                                  {"site": "W", "day": "2026-04-20", "located": True, "lat": 47.14001, "lon": 9.5232, "bearing_deg": 270.0},
                                  {"site": "FIELD", "day": "2026-04-20", "located": True, "lat": 47.1460, "lon": 9.5150, "bearing_deg": 90.0},
                                  {"site": "ELSEWHERE", "day": "2026-04-20", "located": True, "lat": 10.0, "lon": 10.0, "bearing_deg": 90.0},
                                  {"site": "NOWHERE", "day": "2026-04-06", "located": False, "lat": None, "lon": None, "bearing_deg": None}))
    reading_at = staticmethod(lambda site, hhmm: {"start": "2026-04-20 08:30:00", "median_kmh": 9.0, "vehicles": 40, "stretch_m": 60.0} if hhmm.startswith("08:3") else None)


@pytest.fixture
def recorded_town(monkeypatch):
    from types import SimpleNamespace as NS
    from core.common.data import city_config
    src = NS(kind="recorded", dataset="fakecam", citation=None, licence=None, status="active", note="")
    monkeypatch.setattr(city_config, "load", lambda cid, *a: NS(live=NS(real_sources=[src])) if cid == "town" else (_ for _ in ()).throw(KeyError(cid)))
    monkeypatch.setattr(real_speeds, "_readers", lambda: {"fakecam": FakeDataset})


def test_a_recorded_site_is_placed_on_the_section_it_measures_or_on_none(cities, recorded_town):
    net, man = city_router.network("town", str(cities))
    (src,) = real_speeds.recorded_sources("town", net, man["bbox"])
    by = {s["site"]: s for s in src["sites"]}
    east = city_router.route("town", WEST, EAST, cities)["sections"][0]["id"]
    assert by["E"]["section"] == east and by["W"]["section"] not in (None, east)          # the two directions of one road are two sections
    assert by["FIELD"]["section"] is None and by["NOWHERE"]["section"] is None and by["NOWHERE"]["located"] is False
    assert "ELSEWHERE" not in by                                                           # a site in another place is not this city's
    assert src["citation"] == FakeDataset.CITATION and src["licence"] == "CC BY 4.0"
    assert real_speeds.recorded_sources("nowhere") == []


def test_a_recorded_reading_carries_its_own_date_and_never_reaches_now_or_the_travel_times(cities, db, recorded_town):
    plain = city_trip.trip("town", WEST, EAST, NOW, db, FakeModel(), cities)
    assert all(s["recorded"] is None for s in plain["sections"]) and plain["recorded"]["at"] is None
    past = city_trip.trip("town", WEST, EAST, NOW, db, FakeModel(), cities, recorded_at="08:32")
    first, second = past["sections"]
    assert first["recorded"]["value"] == 9.0 and second["recorded"] is None
    t = first["recorded"]["tag"]
    assert t["kind"] == "real" and t["recorded"] is True and t["label"] == "Recorded, FakeCam, 2026-04-20" and t["as_of"].startswith("2026-04-20 08:30") and t["citation"] == FakeDataset.CITATION
    assert first["now"] is None and first["forecast"] == {} and past["travel"] == plain["travel"] == {"0": None, "15": None, "30": None, "60": None}
    assert past["traffic"] == "none" and past["at_limits"] == plain["at_limits"] and tag.untagged(past) == []
    assert all(s["recorded"] is None for s in city_trip.trip("town", WEST, EAST, NOW, db, FakeModel(), cities, recorded_at="12:00")["sections"])   # no reading then: nothing borrowed
    back = [s["recorded"]["tag"]["source"] for s in city_trip.trip("town", EAST, WEST, NOW, db, FakeModel(), cities, recorded_at="08:32")["sections"] if s["recorded"]]
    assert back and all("site W" in x for x in back)                                      # westbound gets the westbound camera, never the eastbound one


def test_the_dhatrax_reader_uses_published_rows_only(tmp_path):
    from core.common.data.recorded import dhatrax
    (tmp_path / "Traffic_Analysis").mkdir(); (tmp_path / "Homography").mkdir(); (tmp_path / "MANIFEST.json").write_text("{}")
    (tmp_path / "world_transform_summary.csv").write_text("site,video_name\nAA,cam_ch1_main_20260420060000_20260420070000.dav\nBB,other_ch2_main_20260406060000_20260406070000.dav\n")
    (tmp_path / "Traffic_Analysis/trajectory_direction_summary.csv").write_text("site,configured_direction\nAA,decreasing_y\nBB,decreasing_y\n")
    pts = [{"world_m": [0, 0], "raw_gps": [23.7460, 90.3940]}, {"world_m": [0, 50], "raw_gps": [23.7455, 90.3940]}, {"world_m": [10, 0], "raw_gps": [23.7460, 90.3941]}, {"world_m": [10, 50], "raw_gps": [23.7455, 90.3941]}]
    (tmp_path / "Homography/cam_ch1_main_20260420060000_20260420070000.json").write_text(json.dumps({"calibration_points": pts}))
    (tmp_path / "Homography/other_ch2_main_20260406060000_20260406070000.json").write_text(json.dumps({"calibration_points": [{"world_m": [0, 0], "raw_gps": None}] * 4}))
    head = "site,interval_start,is_complete_interval,median_speed_pts_kmh,vehicles_with_valid_pts_speed,flow_rate_veh_per_hour,active_length_m\n"
    (tmp_path / "Traffic_Analysis/combined_traffic_5min.csv").write_text(head + "AA,2026-04-20 08:30:00.000,True,8.26,120,1500,62.4\nAA,2026-04-20 08:35:00.000,False,30,5,100,62.4\nAA,2026-04-20 08:40:00.000,True,,0,0,62.4\n")
    (tmp_path / "Traffic_Analysis/vehicle_class_composition_by_site.csv").write_text("site,class_name,vehicle_count\nAA,Car,30\nBB,Car,30\nAA,CNG,40\n")
    a, b = dhatrax.sites(tmp_path)
    assert a == {"site": "AA", "day": "2026-04-20", "located": True, "lat": 23.74575, "lon": 90.39405, "bearing_deg": 0.0}     # y runs south, vehicles travel in decreasing y: north
    assert b["located"] is False and b["lat"] is None and b["day"] == "2026-04-06"                                             # no GPS point: no place is made up
    assert dhatrax.reading_at("AA", "08:33", tmp_path)["median_kmh"] == 8.3 and dhatrax.reading_at("AA", "08:33", tmp_path)["start"] == "2026-04-20 08:30:00"
    assert dhatrax.reading_at("AA", "08:37", tmp_path) is None and dhatrax.reading_at("AA", "08:41", tmp_path) is None          # a part interval and one without a speed are not readings
    assert dhatrax.reading_at("AA", "09:00", tmp_path) is None and dhatrax.reading_at("BB", "08:33", tmp_path) is None
    m = dhatrax.mix(tmp_path)
    assert m["crossings"] == 100 and m["classes"] == {"Car": {"count": 60, "share_pct": 60.0}, "CNG": {"count": 40, "share_pct": 40.0}}


def test_the_mix_is_applied_at_its_shares_once_and_never_puts_a_class_where_it_may_not_drive(cities, tmp_path):
    from types import SimpleNamespace as NS
    from core.common.data import city_config
    from core.simulation.twin import city_pipeline
    net_file = cities / "town" / "sumo" / "town.net.xml"
    east = " ".join(s["id"] for s in city_router.route("town", WEST, EAST, cities)["sections"])
    routes = tmp_path / "town.rou.xml"
    routes.write_text("<routes>" + "".join(f'<vehicle id="v{i}" depart="{i}"><route edges="{east}"/></vehicle>' for i in range(20)) + '<vehicle id="bare" depart="0"/></routes>')
    share = lambda name, pct, vclass: city_config.VehicleShare(name=name, share_pct=pct, sumo_class=vclass)
    cfg = NS(vehicle_mix=city_config.VehicleMix(source="s", citation="c", counted="not a census", simulated_as="y", classes=[share("Car", 60, "passenger"), share("Bus", 30, "bus"), share("Ship", 10, "ship")]))
    log: list[str] = []
    out = city_pipeline.apply_mix(cfg, routes, net_file, 11, log)
    got = {c["name"]: c["vehicles"] for c in out["classes"]}
    assert got == {"Car": 14, "Bus": 6, "Ship": 0} and out["vehicles"] == 20                  # no road admits a ship: its share goes to the commonest class, and the record says so
    assert [c["achieved_pct"] for c in out["classes"]] == [70.0, 30.0, 0.0] and [c["asked_pct"] for c in out["classes"]] == [60, 30, 10]
    text = routes.read_text()
    assert text.count("<vType") == 3 and '<vehicle id="bare" depart="0"' in text and 'id="bare" type' not in text
    assert city_pipeline.apply_mix(cfg, routes, net_file, 11, log) == out and routes.read_text() == text      # applied once; a second run changes nothing
    assert city_pipeline.apply_mix(NS(vehicle_mix=None), routes, net_file, 11, log) is None


def test_a_citys_vehicle_mix_is_whole_and_says_where_it_was_counted():
    from core.common.data import city_config
    mixes = [c.vehicle_mix for c in map(city_config.load, city_config.list_ids()) if c.vehicle_mix]
    assert mixes, "no city declares a vehicle mix"
    for m in mixes:
        assert abs(sum(c.share_pct for c in m.classes) - 100) <= 0.1 and m.source and m.citation and "not a census" in m.counted and m.simulated_as
    with pytest.raises(ValueError):
        city_config.VehicleMix(source="s", citation="c", counted="x", simulated_as="y", classes=[city_config.VehicleShare(name="a", share_pct=60, sumo_class="passenger")])


def test_no_city_is_named_in_the_new_modules():
    from core.common.data.recorded import dhatrax
    for module in (city_router, city_trip, real_speeds, probe_speeds, section_forecast, tag, dhatrax):
        tree = ast.parse(inspect.getsource(module))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
        for name in ("dhaka", "los_angeles", "los angeles", "berlin", "sylhet", "metr-la", "metr_la"):
            assert not [s for s in strings if name in s.lower()], f"{module.__name__} names {name}"


def _replay_dir(tmp_path):
    import gzip
    d = tmp_path / "replay" / "E"
    d.mkdir(parents=True)
    frames = {"30600.0": [[9.5230, 47.14001, 12.3, 0, "7", 92.0, "CNG"], [9.5231, 47.14002, None, 0, "8", 90.0, "Car_Micro"]], "30600.5": [[9.5230, 47.14001, 12.3, 0, "7", 92.0, "CNG"]], "32399.5": [[9.52, 47.14, 5.0, 0, "9", 1.0, "Bus_Minibus"]]}
    with gzip.open(d / "080000.json.gz", "wt") as f:
        json.dump({"site": "E", "day": "2026-04-20", "video_start": "080000", "t_start": 30600.0, "t_end": 32399.5, "coverage_m": 62.5, "hz": 2.0, "calibration_sha256": "abc", "frames": frames}, f)
    with gzip.open(d / "090000.json.gz", "wt") as f:
        json.dump({"site": "E", "day": "2026-04-20", "video_start": "090000", "t_start": 32400.0, "t_end": 32400.0, "coverage_m": 62.5, "hz": 2.0, "calibration_sha256": "abc", "frames": {"32400.0": [[9.52, 47.14, 5.0, 0, "9", 1.0, "Bus_Minibus"]]}}, f)
    return tmp_path / "replay"


def test_the_replay_gives_real_recorded_vehicles_at_a_clock_time_and_nothing_elsewhere(cities, recorded_town, tmp_path, monkeypatch):
    from core.common.data.recorded import replay
    FakeDataset.REPLAY_DIR = _replay_dir(tmp_path)
    from core.common.data.recorded import dhatrax
    FakeDataset.replay_available = staticmethod(lambda: dhatrax.replay_available(tmp_path))
    replay._hour.cache_clear()
    net, man = city_router.network("town", str(cities))
    got = replay.window("town", "08:30", 60, net, man["bbox"])
    assert got["available"] and "replay, not live" in got["label"]
    (e,) = [b for b in got["sites"] if b["site"] == "E"]                       # W has no replay files and is listed as not converted
    assert "W" in got["not_converted"] and e["value"] == 2 and e["coverage_m"] == 62.5
    assert [f["clock"] for f in e["frames"]] == ["08:30:00.0", "08:30:00.5"]
    assert e["frames"][0]["vehicles"][1][2] is None                            # a vehicle the authors did not time has no speed, not a guess
    t = e["tag"]
    assert t["kind"] == "real" and t["recorded"] and t["replay"] and t["label"].startswith("REAL · recorded traffic, FakeCam, 2026-04-20 08:30") and "not validated" not in t["label"]
    assert "ours" in t and t["citation"] == FakeDataset.CITATION and tag.untagged(got) == []
    across = replay.window("town", "08:59:59", 2, net, man["bbox"])["sites"]
    assert [f["clock"] for f in across[0]["frames"]] == ["08:59:59.5", "09:00:00.0"]        # an hour boundary is crossed
    empty = replay.window("town", "11:00", 10, net, man["bbox"])["sites"][0]
    assert empty["frames"] == [] and empty["value"] == 0 and "no recorded frame" in empty["note"]
    assert replay.window("nowhere", "08:30", 60)["available"] is False
    with pytest.raises(ValueError):
        replay.parse_at("8:30")
    del FakeDataset.REPLAY_DIR, FakeDataset.replay_available


def test_the_calibration_maps_the_authors_ground_plane_onto_their_own_gps_points(tmp_path):
    from core.common.data.recorded import dhatrax
    from pyproj import Transformer
    e0, n0 = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True).transform(90.3940, 23.7460)
    cal = {"homography": {"H_base_world_to_final_world": [[0.0, 1.0, 0.0], [-1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]},     # a quarter turn between base and final
           "coordinate_reference": {"origin_info": {"E0": e0, "N0": n0, "epsg": 32646, "x_axis_utm": [1.0, 0.0], "y_axis_utm": [0.0, 1.0]}}, "calibration_points": []}
    f = tmp_path / "cam.json"
    f.write_text(json.dumps(cal))
    c = dhatrax.Calibration(f)
    lon, lat = c.to_lonlat([0.0, 100.0], [0.0, 0.0])                         # final (100, 0) is base (0, 100): 100 m north of the origin
    assert abs(lon[0] - 90.3940) < 1e-6 and abs(lat[0] - 23.7460) < 1e-6
    assert abs(lon[1] - 90.3940) < 3e-5 and abs((lat[1] - 23.7460) * 111_320 - 100) < 0.5      # grid north is not true north: a 2 m drift over 100 m

