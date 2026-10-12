"""P2 sensor-graph tests — placement determinism, adjacency recipe, parsing.

Everything here runs on fixtures or the frozen network file; no SUMO run.
"""
from __future__ import annotations

import numpy as np
import pytest

from core.simulation.twin.sensor_graph import (CHANNELS, DAILY_PROFILE,
                                        EVIDENCE_DOMAIN,
                                        gaussian_kernel_adjacency,
                                        node_list_sha256, parse_edgedata,
                                        select_sensor_edges,
                                        write_sensor_additional)


def test_evidence_domain_is_simulated_sensor_graph():
    assert EVIDENCE_DOMAIN == "DHAKA_SIMULATED_SENSOR_GRAPH"


def test_daily_profile_is_a_two_peak_day():
    assert len(DAILY_PROFILE) == 24
    am = max(range(24), key=lambda h: DAILY_PROFILE[h] if h < 12 else 0)
    pm = max(range(24), key=lambda h: DAILY_PROFILE[h] if h >= 12 else 0)
    assert 6 <= am <= 10 and 16 <= pm <= 20
    assert min(DAILY_PROFILE) > 0            # traffic never fully vanishes


def test_n_target_outside_mandate_rejected(tmp_path):
    with pytest.raises(ValueError, match="100-300"):
        select_sensor_edges(tmp_path / "x.net.xml", n_target=50)
    with pytest.raises(ValueError, match="100-300"):
        select_sensor_edges(tmp_path / "x.net.xml", n_target=400)


# ------------------------------------------------- placement on the frozen net
@pytest.fixture(scope="module")
def frozen_nodes():
    from core.common.city import DHAKA_R1
    if not DHAKA_R1.network_path.exists():
        pytest.skip("frozen R1 network not present")
    return select_sensor_edges(DHAKA_R1.network_path, n_target=250)


def test_placement_count_and_determinism(frozen_nodes):
    from core.common.city import DHAKA_R1
    assert len(frozen_nodes) == 250
    again = select_sensor_edges(DHAKA_R1.network_path, n_target=250)
    assert node_list_sha256(frozen_nodes) == node_list_sha256(again)


def test_placement_is_spatially_spread(frozen_nodes):
    xs = np.array([n.x for n in frozen_nodes])
    ys = np.array([n.y for n in frozen_nodes])
    # Sensors must span most of the region in both axes, not one arterial.
    assert (xs.max() - xs.min()) > 0 and (ys.max() - ys.min()) > 0
    left = ((xs - xs.min()) / (xs.max() - xs.min()) < 0.5).mean()
    assert 0.2 < left < 0.8                  # neither half-region is starved


def test_additional_file_declares_every_sensor(frozen_nodes, tmp_path):
    add = write_sensor_additional(frozen_nodes, tmp_path / "s.add.xml",
                                  tmp_path / "out.xml")
    text = add.read_text()
    assert 'period="300"' in text and 'excludeEmpty="false"' in text
    for n in frozen_nodes[:5] + frozen_nodes[-5:]:
        assert n.edge_id in text


# ----------------------------------------------------------- adjacency recipe
def test_gaussian_kernel_adjacency_properties():
    d = np.array([[0.0, 100.0, np.inf],
                  [100.0, 0.0, 3000.0],
                  [np.inf, 3000.0, 0.0]])
    w = gaussian_kernel_adjacency(d, threshold=0.1)
    assert np.allclose(np.diag(w), 1.0)
    assert w[0, 2] == 0.0                    # unreachable ⇒ no edge
    assert 0.0 < w[0, 1] <= 1.0
    assert w[0, 1] > w[1, 2]                 # nearer ⇒ stronger


def test_disconnected_distances_rejected():
    with pytest.raises(ValueError, match="disconnected"):
        gaussian_kernel_adjacency(np.full((3, 3), np.inf))


# ------------------------------------------------------------ edgedata parsing
EDGEDATA_XML = """<?xml version="1.0"?>
<meandata>
  <interval begin="0.00" end="300.00" id="p2_sensor_graph">
    <edge id="eA" sampledSeconds="120.0" speed="8.5" density="12.0"
          occupancy="4.2" entered="17"/>
    <edge id="eB" sampledSeconds="0.00" speed="-1.00" density="0.00"
          occupancy="0.00" entered="0"/>
  </interval>
  <interval begin="300.00" end="600.00" id="p2_sensor_graph">
    <edge id="eA" sampledSeconds="90.0" speed="6.0" density="20.0"
          occupancy="9.0" entered="11"/>
    <edge id="eB" sampledSeconds="30.0" speed="11.0" density="2.0"
          occupancy="0.8" entered="3"/>
  </interval>
</meandata>
"""


def test_parse_edgedata_zero_traffic_speed_is_nan_not_zero(tmp_path):
    f = tmp_path / "ed.xml"
    f.write_text(EDGEDATA_XML)
    data, mask = parse_edgedata(f, ["eA", "eB"])
    assert data.shape == (2, 2, len(CHANNELS))
    assert mask.shape == (2, 2)
    # eA bin 0: measured
    assert data[0, 0, 0] == 8.5 and mask[0, 0]
    # eB bin 0: zero traffic — flow is a TRUE zero, speed is NaN, mask False
    assert np.isnan(data[0, 1, 0])
    assert data[0, 1, 3] == 0.0
    assert not mask[0, 1]
    # eB bin 1: traffic returned
    assert data[1, 1, 0] == 11.0 and mask[1, 1]


def test_parse_edgedata_empty_file_raises(tmp_path):
    f = tmp_path / "empty.xml"
    f.write_text("<meandata></meandata>")
    with pytest.raises(ValueError, match="no intervals"):
        parse_edgedata(f, ["eA"])
