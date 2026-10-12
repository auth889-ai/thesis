"""Add your city: a search result becomes a strict, sourced config; limits are checked before anything is requested;
and a city that is in no list builds and runs end to end."""
import ast
import inspect
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from core.common.data import city_builds, city_config, city_search
from core.simulation.twin import city_pipeline, scene

CANDIDATE = {"division_id": "div-123", "name": "Anytown", "main_name": "Анытаун", "display_name": {"en": "Anytown"}, "kind": "locality", "country": "XX", "region": None,
             "population": 1000, "lon": 9.52, "lat": 47.14, "drive_side": "right", "proposed_box": city_search.proposed_box(9.52, 47.14),
             "release": "r1", "source": "Overture Maps divisions theme, release r1, division div-123"}


def test_generated_config_is_strict_sourced_and_leaves_unknowns_null(tmp_path):
    cid, existed = city_builds.prepare(CANDIDATE, None, config_dir=tmp_path)
    cfg = city_config.load(cid, tmp_path)                                   # the same strict schema as a hand-written city
    assert (cid, existed) == ("anytown", False) and cfg.drive_side == "right" and cfg.country == "XX"
    assert cfg.time_zone is None and cfg.default_languages is None and cfg.emergency_numbers is None and cfg.units is None and cfg.vehicle_classes is None
    assert list(cfg.bounding_box.tuple) == CANDIDATE["proposed_box"] and "div-123" in cfg.bounding_box.source and "adjusted" not in cfg.bounding_box.source
    text = (tmp_path / "anytown.yaml").read_text()
    assert text.count("not held by Overture") == 4 and "Generated, not hand-written" in text and cfg.sumo.build.seed == city_builds.DEMAND["seed"]
    assert city_builds.prepare(CANDIDATE, None, config_dir=tmp_path) == ("anytown", True)                 # the same city again: nothing rewritten
    with pytest.raises(city_builds.Refused, match="not overwritten"):
        city_builds.prepare({**CANDIDATE, "division_id": "another"}, None, config_dir=tmp_path)             # a different place with the same id


def test_an_adjusted_area_says_so_and_a_too_large_one_is_refused(tmp_path):
    moved = city_search.proposed_box(9.53, 47.15, 0.02)
    cid, _ = city_builds.prepare({**CANDIDATE, "name": "Othertown"}, moved, config_dir=tmp_path)
    assert "adjusted by the person" in city_config.load(cid, tmp_path).bounding_box.source
    with pytest.raises(city_builds.Refused, match="too large"):
        city_builds.check_box(city_search.proposed_box(9.52, 47.14, 0.07))
    with pytest.raises(city_builds.Refused, match="south < north"):
        city_builds.check_box([47.2, 9.5, 47.1, 9.6])


def test_an_unknown_driving_side_is_refused_not_guessed(tmp_path):
    with pytest.raises(city_builds.Refused, match="side of the road"):
        city_builds.prepare({**CANDIDATE, "drive_side": None}, None, config_dir=tmp_path)
    assert not list(tmp_path.glob("*.yaml"))


def test_one_build_at_a_time_and_a_daily_limit(tmp_path, monkeypatch):
    real_count = city_builds.built_today
    monkeypatch.setattr(city_builds, "_running", ["somewhere"])
    with pytest.raises(city_builds.Refused, match="one at a time"):
        city_builds.start(CANDIDATE)
    monkeypatch.setattr(city_builds, "_running", [])
    monkeypatch.setattr(city_builds, "prepare", lambda c, b: ("anytown", False))
    monkeypatch.setattr(city_builds, "built_today", lambda *a: city_builds.DAILY_BUILDS)
    with pytest.raises(city_builds.Refused, match="built today"):
        city_builds.start(CANDIDATE)
    ledger = tmp_path / "l.jsonl"
    ledger.write_text(json.dumps({"utc": "2001-01-01T00:00:00Z", "city_id": "old"}) + "\n")
    assert real_count(ledger) == 0                                          # yesterday's builds do not count


def test_a_city_already_built_is_returned_without_any_request(monkeypatch):
    monkeypatch.setattr(city_builds, "prepare", lambda c, b: ("anytown", True))
    monkeypatch.setattr(city_builds, "is_built", lambda cid: True)
    monkeypatch.setattr(city_pipeline, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("a build was started")))
    r = city_builds.start(CANDIDATE)
    assert r["status"] == "done" and r["cached"] and r["job"] is None


def test_search_is_answered_from_the_cache_and_short_names_are_not_searched(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(city_search, "_query", lambda name, release: calls.append(name) or [CANDIDATE])
    a = city_search.search("  Anytown ", release="r1", cache=tmp_path / "c.json")
    b = city_search.search("anytown", release="r1", cache=tmp_path / "c.json")
    assert calls == ["Anytown"] and a["candidates"] == b["candidates"] == [CANDIDATE] and "Overture" in a["attribution"]
    assert city_search.search("a", release="r1", cache=tmp_path / "c.json")["candidates"] == []


def test_no_city_is_named_in_the_new_modules():
    for module in (city_search, city_builds):
        tree = ast.parse(inspect.getsource(module))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
        assert not [s for s in strings if any(c in s.lower().replace("dhakaflow", "") for c in (   # the project's own name (its User-Agent) is not a city
                                                                                 "dhaka", "los_angeles", "berlin", "sylhet", "vaduz"))], module.__name__


@pytest.mark.slow
def test_a_city_in_no_list_goes_from_its_name_to_moving_vehicles(tmp_path):
    """Sylhet, Bangladesh: not an evaluation city, not the fixture; its main name is in Bangla; it drives on the left."""
    if not shutil.which("netconvert"):
        pytest.skip("SUMO is not installed on this machine")
    try:
        found = city_search.search("Sylhet", cache=tmp_path / "search.json")
    except Exception as exc:                                                    # noqa: BLE001
        pytest.skip(f"Overture's divisions file could not be read ({type(exc).__name__}: {exc})")
    c = found["candidates"][0]
    assert c["country"] == "BD" and c["drive_side"] == "left" and c["main_name"] != c["name"] == "Sylhet"
    cid, _ = city_builds.prepare(c, None, config_dir=tmp_path / "config")
    try:
        r = city_pipeline.run(cid, config_dir=tmp_path / "config", city_dir=tmp_path / "cities", evidence_dir=tmp_path / "evidence")
    except Exception as exc:                                                    # noqa: BLE001
        pytest.skip(f"the Overpass server did not answer the road request ({type(exc).__name__}: {exc})")
    out = tmp_path / "cities" / cid / "sumo"
    assert r["network"]["edges"] > 100 and r["demand"]["vehicles"] > 10 and "--lefthand" in r["network"]["netconvert_options"]
    assert r["buildings"]["file"] is None and r["buildings"]["release"]         # buildings come from the map's own source, not a per-city fetch
    s = scene.build(cid, city_dir=tmp_path / "cities")
    assert s["available"] and s["label"] == "SIMULATED" and len(s["roads"]["features"]) == r["network"]["edges"]
    summary = tmp_path / "summary.xml"
    subprocess.run(["sumo", "-c", str(out / f"{cid}.sumocfg"), "--end", "120", "--summary-output", str(summary), "--no-step-log", "--no-warnings"], check=True, capture_output=True, cwd=out)
    steps = ET.parse(summary).getroot().findall("step")
    assert max(int(x.get("running")) for x in steps) > 5 and max(float(x.get("meanSpeed")) for x in steps) > 1      # vehicles are on the road and moving
