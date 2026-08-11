"""Integration test on a tiny handcrafted OSM fixture (requires SUMO; skips locally).

A 4-junction diamond with two-way primary roads and one mapped traffic signal:
exercises netconvert import, validation, representative routing, demand and a
short simulation — the full Lab 02 chain minus the Overpass download.
"""
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TINY_OSM = """<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6" generator="dhakaflow-fixture">
  <node id="1" lat="23.7400" lon="90.3900"/>
  <node id="2" lat="23.7450" lon="90.3850"/>
  <node id="3" lat="23.7450" lon="90.3950"/>
  <node id="4" lat="23.7500" lon="90.3900">
    <tag k="highway" v="traffic_signals"/>
  </node>
  <node id="5" lat="23.7550" lon="90.3900"/>
  <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/><tag k="lanes" v="2"/></way>
  <way id="11"><nd ref="1"/><nd ref="3"/><tag k="highway" v="primary"/><tag k="lanes" v="2"/></way>
  <way id="12"><nd ref="2"/><nd ref="4"/><tag k="highway" v="primary"/><tag k="lanes" v="2"/></way>
  <way id="13"><nd ref="3"/><nd ref="4"/><tag k="highway" v="primary"/><tag k="lanes" v="2"/></way>
  <way id="14"><nd ref="4"/><nd ref="5"/><tag k="highway" v="secondary"/></way>
</osm>
"""


@pytest.mark.skipif(shutil.which("netconvert") is None,
                    reason="SUMO not installed locally; runs in the Colab gate")
def test_tiny_osm_end_to_end(tmp_path):
    from src.network.build import build_network
    from src.validation.network_checks import validate_network, representative_routes
    from src.demand.generate import generate_and_route, run_simulation
    from src.metrics.summarize import summarize_tripinfo

    osm = tmp_path / "tiny.osm"
    osm.write_text(TINY_OSM)
    net = tmp_path / "tiny.net.xml"
    rec = build_network(osm, net, tmp_path)
    assert rec["returncode"] == 0 and net.exists()

    val = validate_network(net, tmp_path)
    assert val["n_edges"] >= 6            # two-way ways -> >=2 edges each (minus prune)
    assert val["scc_edge_fraction"] > 0.8
    assert val["n_tls"] >= 1
    assert val["tls_all_have_yellow"]

    rep = representative_routes(net, tmp_path)
    assert rep["n_ok"] == rep["n_total"]

    dem = generate_and_route(net, tmp_path, seed=42, end_time=120, period=4.0)
    assert dem["n_routed"] > 0
    sim = run_simulation(net, Path(dem["routes_file"]), tmp_path, seed=42, end_time=120)
    assert sim["returncode"] == 0 and sim["collisions"] == 0
    m = summarize_tripinfo(tmp_path / "tripinfo.xml")
    assert m["n_arrived_trips"] > 0
