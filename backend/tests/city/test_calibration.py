"""Calibration: counts become SUMO edge data, only untouched background is kept, and a miss is reported as a miss."""
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from core.common.data import city_config
from core.simulation.twin import calibration as cal


def test_geh_is_zero_for_a_match_and_grows_with_the_gap():
    assert cal.geh(100, 100, 300) == 0.0
    assert cal.geh(50, 100, 300) > cal.geh(90, 100, 300) > 0
    assert cal.geh(0, 0, 300) == 0.0


def test_an_incomplete_interval_constrains_nothing(tmp_path):
    sites = [{"section": "a", "counts": [10, None]}, {"section": "b", "counts": [5, 7]}]
    cal.write_counts(sites, 300, tmp_path / "c.xml")
    ivs = ET.parse(tmp_path / "c.xml").getroot().findall("interval")
    assert [(e.get("id"), e.get("entered")) for e in ivs[0]] == [("a", "10"), ("b", "5")]
    assert [(e.get("id"), e.get("entered")) for e in ivs[1]] == [("b", "7")] and ivs[1].get("begin") == "300"


def test_background_that_touches_a_counted_section_is_dropped(tmp_path):
    (tmp_path / "s.xml").write_text('<routes><vehicle id="cal0" depart="5"><route edges="x a y"/></vehicle></routes>')
    (tmp_path / "b.xml").write_text('<routes><vType id="t"/><vehicle id="v0" depart="1"><route edges="p q"/></vehicle>'
                                    '<vehicle id="v1" depart="2"><route edges="p a"/></vehicle></routes>')
    got = cal.merge(tmp_path / "s.xml", tmp_path / "b.xml", {"a"}, tmp_path / "out.xml")
    assert got == {"sampled_through_counted_sections": 1, "background_uncalibrated": 1, "background_dropped_for_touching_a_counted_section": 1}
    assert [v.get("id") for v in ET.parse(tmp_path / "out.xml").getroot().findall("vehicle")] == ["v0", "cal0"]


def test_a_miss_is_reported_as_a_miss():
    sites = [{"site": "S", "day": "2026-01-01", "section": "a", "section_distance_m": 1.0, "bearing_deg": 0.0, "counts": [100, None, 100]}]
    runs = {1: {"entered": {"a": [100, 0, 40]}}, 2: {"entered": {"a": [98, 0, 44]}}}
    rep = cal.report(sites, {"a": [100, 0, 100]}, runs, SimpleNamespace(interval_s=300))
    s = rep["sites"][0]
    assert s["intervals_counted"] == 2 and s["observed_total"] == 200 and s["intervals_within_geh_5_simulated"] == 1
    assert rep["overall"]["within_geh_5_sampler_pct"] == 100.0 and rep["overall"]["within_geh_5_simulated_pct"] == 50.0


def test_every_city_config_still_loads_and_only_declared_cities_are_calibrated():
    for cid in city_config.list_ids():
        cfg = city_config.load(cid)
        assert cfg.calibration is None or cfg.calibration.dataset
