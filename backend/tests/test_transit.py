"""Transit planning on a line given in the test (no network): nearest stops, legs, hours, provenance."""
from datetime import datetime, timezone

from app.transit import osm, schedule, service

LINE6 = {"id": 1, "mode": "subway", "name": "Dhaka Metro Rail Line 6", "network": "Dhaka Metro Rail", "ref": "6", "operator": None, "interval_s": None, "duration_s": None,
         "stops": [{"id": 1, "name": "Agargaon", "lat": 23.7784, "lon": 90.3802}, {"id": 2, "name": "Bijoy Shoroni", "lat": 23.7664, "lon": 90.3831}, {"id": 3, "name": "Farmgate", "lat": 23.7591, "lon": 90.3871},
                   {"id": 4, "name": "Karwan Bazar", "lat": 23.7513, "lon": 90.3928}, {"id": 5, "name": "Shahbagh", "lat": 23.7401, "lon": 90.3962}, {"id": 6, "name": "Motijheel", "lat": 23.7281, "lon": 90.4191}], "osm_timestamp": "2026-09-28T21:35:36Z"}
FARMGATE, MOTIJHEEL = (23.7573, 90.3854), (23.7330, 90.4172)


def test_a_trip_along_the_line_gets_walk_wait_ride_walk_with_published_headway():
    depart = datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc)                 # 08:30 Dhaka, a weekday peak
    opts = service.options(FARMGATE, MOTIJHEEL, depart, 6.0, lines=[LINE6, {**LINE6, "id": 2, "stops": list(reversed(LINE6["stops"]))}])
    assert len(opts) == 1, "the two directions are one option"
    o = opts[0]
    assert o["board"] == "Farmgate" and o["alight"] == "Motijheel" and o["stops_passed"] == 3 and o["open"] is True
    assert [l["kind"] for l in o["legs"]] == ["walk", "wait", "ride", "walk"]
    assert o["legs"][1]["headway_s"] == 360 and o["legs"][1]["seconds"] == 180
    assert 300 < o["legs"][2]["seconds"] < 1500 and 600 < o["total_s"] < 2400
    assert "Wikipedia" in o["provenance"]["schedule"] and "estimated" in o["provenance"]["ride"]


def test_closed_hours_and_off_peak_headway_are_applied():
    facts = schedule.facts_for(LINE6)
    assert schedule.is_open(facts, datetime(2026, 9, 30, 23, 0)) is False and schedule.is_open(facts, datetime(2026, 10, 2, 9, 0)) is False, "23:00, and a Friday morning"
    assert schedule.headway_s(facts, datetime(2026, 9, 30, 13, 0)) == 420 and schedule.headway_s(facts, datetime(2026, 9, 30, 8, 0)) == 360


def test_osm_tags_override_published_facts_and_unknown_lines_are_estimates():
    tagged = {**LINE6, "interval_s": 300}
    assert schedule.facts_for(tagged)["headway_peak_s"] == 300 and schedule.facts_for(tagged)["from_osm"]["headway"]
    unknown = {**LINE6, "name": "Green Line", "network": "Metro X"}
    assert "estimate" in schedule.facts_for(unknown)["source"]


def test_a_trip_out_of_walking_reach_has_no_option():
    far = (23.90, 90.50)
    assert service.options(far, MOTIJHEEL, datetime(2026, 9, 30, 2, 30, tzinfo=timezone.utc), 6.0, lines=[LINE6]) == []


def test_interval_tag_forms_are_parsed():
    assert osm._seconds("PT6M") == 360 and osm._seconds("00:07") == 420 and osm._seconds("6") == 360 and osm._seconds(None) is None
