"""Live corridor -> R1 edges -> SUMO weights: the level->magnitude assumption and the map itself."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from traffictwin.forecasting.live.live_to_edges import BAND_MID, MAP_FILE, multiplier, write_weights  # noqa: E402
from traffictwin.digital_twin.runtime import load_weights  # noqa: E402

pytestmark = pytest.mark.skipif(not MAP_FILE.exists(), reason="run: python -m traffictwin.forecasting.live.live_to_edges --map")


def cmap():
    return json.loads(MAP_FILE.read_text())


def test_multiplier_is_monotonic_and_hits_band_midpoints():
    for level, m in BAND_MID.items():
        assert multiplier(level) == m
    assert multiplier(0) < multiplier(1) < multiplier(2) < multiplier(3)
    assert multiplier(0.5) == pytest.approx((BAND_MID[0] + BAND_MID[1]) / 2)   # linear interpolation
    assert multiplier(-5) == BAND_MID[0] and multiplier(99) == BAND_MID[3]      # clipped, never negative
    assert multiplier(0) >= 1.0, "a multiplier below 1 would make live traffic faster than free flow"


def test_every_corridor_maps_to_a_contiguous_path_on_the_real_network():
    import sumolib
    net = sumolib.net.readNet(str(REPO / "data/cities/dhaka_r1/dhaka_r1.net.xml.gz"))
    m = cmap()
    assert len(m) == 6 and all(r["status"] == "MAPPED" for r in m.values())
    for cid, r in m.items():
        edges = r["edges"]
        assert edges and len(edges) == len(r["edge_free_tt_s"])
        for a, b in zip(edges, edges[1:]):                       # path must actually be drivable
            assert net.getEdge(b) in net.getEdge(a).getOutgoing(), f"{cid}: {a} -> {b} not connected"
        assert r["free_flow_s"] == pytest.approx(sum(r["edge_free_tt_s"].values()), abs=0.5)
        assert 10 < r["free_flow_s"] < 900, f"{cid}: implausible free-flow time {r['free_flow_s']}s"
        assert max(r["snap_m"]) < 300


def test_weights_scale_free_flow_by_the_level(tmp_path):
    m = cmap()
    cid = next(iter(m))
    out = tmp_path / "w.xml"
    rec = write_weights({cid: 2.0}, m, out, 0.0, 3600.0, {"test": True})
    assert rec["edges_written"] == len(m[cid]["edges"])
    rows = load_weights(out)
    by_edge = {e: tt for _, _, e, tt in rows}
    for eid, free in m[cid]["edge_free_tt_s"].items():
        assert by_edge[eid] == pytest.approx(free * BAND_MID[2], abs=0.02)


def test_shared_edges_take_the_worst_corridor(tmp_path):
    m = cmap()
    a, b = list(m)[:2]
    shared = set(m[a]["edges"]) & set(m[b]["edges"])
    if not shared:
        pytest.skip("these two corridors share no edge")
    out = tmp_path / "w.xml"
    write_weights({a: 0.0, b: 3.0}, m, out, 0.0, 600.0, {})
    by_edge = {e: tt for _, _, e, tt in load_weights(out)}
    eid = sorted(shared)[0]
    assert by_edge[eid] == pytest.approx(m[b]["edge_free_tt_s"][eid] * BAND_MID[3], abs=0.02)


def test_unmapped_corridors_contribute_nothing(tmp_path):
    m = dict(cmap())
    cid = next(iter(m))
    m[cid] = {"corridor_id": cid, "status": "UNMAPPED", "edges": []}
    out = tmp_path / "w.xml"
    rec = write_weights({cid: 3.0}, m, out, 0.0, 600.0, {})
    assert rec["edges_written"] == 0 and rec["corridors"] == {}
    assert load_weights(out) == []
