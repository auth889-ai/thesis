"""Any city with a config file can be built; nothing in the pipeline names one."""
import ast
import inspect
import json
import shutil
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from core.common.data import city_config
from core.simulation.twin import city_pipeline, network_file, scenario_builder, scene

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/cities"


def _overpass_reachable() -> bool:
    try:
        urllib.request.urlopen(urllib.request.Request(scenario_builder.OVERPASS.replace("interpreter", "status"), headers={"User-Agent": "dhakaflow/1.0"}), timeout=15)
        return True
    except Exception:
        return False


def test_every_tracked_config_loads_and_states_each_field():
    assert {"dhaka", "los_angeles", "berlin"} <= set(city_config.list_ids())
    for cid in city_config.list_ids():
        c = city_config.load(cid)
        assert c.city_id == cid and c.display_name and (c.sumo.prebuilt is not None or c.sumo.build is not None)


def test_a_missing_key_is_an_error_and_null_is_allowed(tmp_path):
    raw = yaml.safe_load((FIXTURES / "vaduz.yaml").read_text())
    (tmp_path / "vaduz.yaml").write_text(yaml.safe_dump({**raw, "emergency_numbers": None, "bounding_box": None}))
    assert city_config.load("vaduz", tmp_path).center is None                     # unknown, stated as null
    del raw["time_zone"]
    (tmp_path / "vaduz.yaml").write_text(yaml.safe_dump(raw))
    with pytest.raises(Exception, match="time_zone"):
        city_config.load("vaduz", tmp_path)                                        # forgotten, not unknown
    (tmp_path / "vaduz.yaml").write_text(yaml.safe_dump({**raw, "time_zone": "Europe/Vaduz", "mayor": "x"}))
    with pytest.raises(Exception, match="mayor"):
        city_config.load("vaduz", tmp_path)


def test_no_city_is_named_in_the_pipeline_the_schema_or_the_network_resolver():
    """No string in the code (docstrings aside) carries a city: paths, ids and names all come from a config."""
    for module in (city_pipeline, city_config, network_file):
        tree = ast.parse(inspect.getsource(module))
        docs = {id(n.body[0].value) for n in ast.walk(tree) if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]
        for name in ("dhaka", "los_angeles", "los angeles", "berlin", "vaduz", "metr-la", "metr_la"):
            assert not [s for s in strings if name in s.lower()], f"{module.__name__} names {name}"


def test_a_city_without_a_box_is_refused_with_the_reason(tmp_path):
    with pytest.raises(SystemExit, match="no bounding box"):
        city_pipeline.run("berlin", city_dir=tmp_path / "c", evidence_dir=tmp_path / "e")
    assert not (tmp_path / "e").exists()                                           # no evidence for a build that did not happen


def test_a_prebuilt_city_is_verified_not_rebuilt_and_a_changed_file_is_caught(tmp_path, monkeypatch):
    cfg = city_config.default()
    if cfg.sumo.prebuilt is None or not (city_pipeline.REPO / cfg.sumo.prebuilt.network).exists():
        pytest.skip("the default city has no prebuilt network on this machine")
    monkeypatch.setattr(city_pipeline, "buildings", lambda cfg, out, log: None)                       # no network request in this test
    monkeypatch.setattr(scenario_builder, "run_random_trips", lambda net, trips, routes, *a: routes.write_text('<routes><vehicle id="v0"/></routes>') and ["--seed", "11"])
    r = city_pipeline.run(cfg.city_id, city_dir=tmp_path / "c", evidence_dir=tmp_path / "e")
    assert r["mode"].startswith("prebuilt") and r.get("prebuilt", r)["network_sha256"] == cfg.sumo.prebuilt.network_sha256
    assert not list((tmp_path / "c").rglob("*.net.xml"))                                             # the network itself is never rebuilt
    if cfg.sumo.build:                                                                               # generated demand beside it, labelled, and found by the live twin's manifest
        man = json.loads((tmp_path / "c" / cfg.city_id / "sumo" / "MANIFEST.json").read_text())
        assert man["demand_reality"] == "SYNTHETIC_WHAT_IF" and man["files"]["net"] == cfg.sumo.prebuilt.network and r["demand"]["calibration"] == "none"
    monkeypatch.setattr(city_pipeline, "sha256", lambda *a, **k: "0" * 64)
    with pytest.raises(SystemExit, match="differ from the config"):
        city_pipeline.run(cfg.city_id, city_dir=tmp_path / "c", evidence_dir=tmp_path / "e2")


@pytest.mark.slow
def test_a_fourth_city_builds_from_its_config_alone(tmp_path):
    if not shutil.which("netconvert"):
        pytest.skip("SUMO is not installed on this machine")
    if not _overpass_reachable():
        pytest.skip("the Overpass API is not reachable from this machine")
    try:
        r = city_pipeline.run("vaduz", config_dir=FIXTURES, city_dir=tmp_path / "cities", evidence_dir=tmp_path / "evidence")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        pytest.skip(f"the Overpass server did not answer the extract request ({exc}); the build could not be attempted")
    out = tmp_path / "cities/vaduz/sumo"
    assert r["mode"] == "built" and r["network"]["edges"] > 50 and r["demand"]["vehicles"] > 10
    assert (out / "vaduz.net.xml").exists() and (out / "vaduz.rou.xml").exists() and (out / "vaduz.sumocfg").exists()
    ev = json.loads((tmp_path / "evidence/vaduz/build.json").read_text())
    assert ev["osm"]["data_date"] and len(ev["osm"]["sha256"]) == 64 and ev["osm"]["sha256"] == city_pipeline.sha256(out / "vaduz.osm.xml")
    assert "--lefthand" not in ev["network"]["netconvert_options"] and ev["demand"]["label"] == "SYNTHETIC_WHAT_IF"
    assert (tmp_path / "evidence/vaduz/build.log").read_text().startswith("overpass ")
    # the same build is what the 3D view draws and what the live twin can run
    man = json.loads((out / "MANIFEST.json").read_text())
    assert man["demand_reality"] == "SYNTHETIC_WHAT_IF" and (city_pipeline.REPO / man["files"]["routes"]).name == "vaduz.rou.xml" or man["files"]["routes"].endswith("vaduz.rou.xml")
    if ev["buildings"].get("file"):
        assert ev["buildings"]["count"] > 0 and len(ev["buildings"]["sha256"]) == 64 and ev["buildings"]["data_date"]


def test_building_height_rule_is_tag_then_levels_then_a_stated_default():
    assert scene.building_height({"height": "12.5 m"}) == (12.5, "osm height tag")
    assert scene.building_height({"building:levels": "4"}) == (4 * scene.LEVEL_M, "osm levels tag x assumed storey height")
    assert scene.building_height({"building": "yes"}) == (scene.DEFAULT_M, "assumed default")
    assert scene.building_height({"height": "tall", "building:levels": "0"})[1] == "assumed default"


def test_a_city_that_was_never_built_has_no_scene(tmp_path):
    s = scene.build("berlin", city_dir=tmp_path)
    assert s["available"] is False and s["note"].startswith(scene.NO_DATA)


def test_scene_of_a_built_city_is_labelled_simulated_and_names_no_city():
    cid = city_config.default().city_id
    s = scene.build(cid)
    if not s["available"]:
        pytest.skip("the default city has not been built on this machine (python -m core.simulation.twin.city_pipeline --city <id>)")
    assert s["label"] == "SIMULATED" and s["attribution"].startswith("©")
    fitted = city_config.load(cid).calibration is not None and s["demand"]["calibrated_to"] is not None      # python -m core.simulation.twin.calibration was run
    assert s["demand"]["label"] == ("SYNTHETIC_PARTLY_CALIBRATED" if fitted else "SYNTHETIC_WHAT_IF")
    assert not fitted or "uncalibrated" in s["demand"]["calibrated_to"]       # it says what is NOT calibrated too
    assert len(s["roads"]["features"]) == s["network"]["edges"] > 0
    assert all(f["properties"]["height"] > 0 and f["properties"]["height_from"] for f in s["buildings"]["features"][:200])
    assert sum(s["heights"]["buildings_by_rule"].values()) == len(s["buildings"]["features"]) and s["heights"]["assumed_default_m"] == scene.DEFAULT_M
    assert all({"tls", "link", "lon", "lat"} <= set(x) for x in s["signals"])
    by = s["lanes"]["sections_by_source"]                                     # every section says where its lane count comes from
    assert sum(by.values()) == s["network"]["edges"] and set(by) == {scene.LANES_OSM, scene.LANES_DEFAULT, scene.LANES_UNKNOWN}
    assert all(f["properties"]["width_m"] > 0 and f["properties"]["lanes"] > 0 and f["properties"]["lanes_source"] in by for f in s["roads"]["features"])
    strings = [n.value for n in ast.walk(ast.parse(inspect.getsource(scene))) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    assert not [x for x in strings if any(c in x.lower() for c in ("dhaka", "los_angeles", "berlin"))]


def test_an_open_outline_is_not_a_building(tmp_path):
    f = tmp_path / "b.json"
    f.write_text(json.dumps({"elements": [
        {"type": "way", "tags": {"building:levels": "3"}, "geometry": [{"lat": 0.0, "lon": 9.0}, {"lat": 0.0, "lon": 9.001}, {"lat": 0.001, "lon": 9.001}, {"lat": 0.0, "lon": 9.0}]},
        {"type": "way", "tags": {"building": "yes"}, "geometry": [{"lat": 0.0, "lon": 9.0}, {"lat": 0.0, "lon": 9.001}]}]}))
    assert [b["properties"]["height"] for b in scene._buildings(f)] == [3 * scene.LEVEL_M]


def test_a_lane_count_says_whether_openstreetmap_tagged_it(tmp_path):
    osm = tmp_path / "x.osm.xml"
    osm.write_text('<osm><way id="1"><nd ref="1"/><tag k="highway" v="primary"/><tag k="lanes" v="4"/></way>'
                   '<way id="2"><tag k="highway" v="residential"/></way><way id="3"><tag k="lanes" v="2"/></way></osm>')
    tagged = scene.tagged_ways(osm)
    assert tagged == {"1", "3"}
    assert scene.lanes_source("1", tagged) == scene.LANES_OSM and scene.lanes_source("2", tagged) == scene.LANES_DEFAULT
    assert scene.lanes_source("1 3", tagged) == scene.LANES_OSM and scene.lanes_source("1 2", tagged) == scene.LANES_DEFAULT   # joined ways: all must be tagged
    assert scene.lanes_source(None, tagged) == scene.LANES_UNKNOWN            # the network kept no way id for the section
    assert scene.tagged_ways(tmp_path / "none.osm.xml") is None and scene.lanes_source("1", None) == scene.LANES_UNKNOWN   # no extract kept
