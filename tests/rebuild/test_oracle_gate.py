"""The oracle gate's statistics, concentration and measured-table aggregation, without SUMO runs."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.routing import oracle_gate as og  # noqa: E402


def _runs(vals: dict[str, list[float]]):
    seeds = range(len(next(iter(vals.values()))))
    return {s: {arm: {"metrics": {"m": vals[arm][s]}} for arm in vals} for s in seeds}


def test_paired_helped_when_ci_excludes_zero():
    st = og.paired(_runs({"oracle": [95, 94, 96, 95, 93], "baseline": [100, 100, 100, 100, 100]}), "oracle", "baseline", "m")
    assert st["label"] == "HELPED" and st["wins"] == 5 and st["losses"] == 0 and st["ci95"][1] < 0
    assert st["mean_pct"] == pytest.approx(-5.4, abs=0.01) and st["median_pct"] == -5.0


def test_paired_inconclusive_when_ci_crosses_zero_even_if_mean_is_negative():
    st = og.paired(_runs({"oracle": [90, 105, 95], "baseline": [100, 100, 100]}), "oracle", "baseline", "m")
    assert st["label"] == "INCONCLUSIVE" and st["mean_pct"] < 0 and st["ci95"][0] < 0 < st["ci95"][1]


def test_paired_hurt_and_higher_is_better_metrics():
    st = og.paired(_runs({"oracle": [104, 105, 106, 104], "baseline": [100, 100, 100, 100]}), "oracle", "baseline", "m")
    assert st["label"] == "HURT"
    st2 = og.paired(_runs({"oracle": [104, 105, 106, 104], "baseline": [100, 100, 100, 100]}), "oracle", "baseline", "m", lower_is_better=False)
    assert st2["label"] == "HELPED" and st2["wins"] == 4


def test_concentration_uses_the_last_driven_route(tmp_path):
    f = tmp_path / "vehroutes.xml"
    f.write_text('<routes>\n<vehicle id="a" depart="0"><routeDistribution><route replacedAtTime="10" edges="e1 e2 e3"/><route edges="e1 e4 e3"/></routeDistribution></vehicle>\n'
                 '<vehicle id="b" depart="0"><route edges="e1 e4 e3"/></vehicle>\n<vehicle id="c" depart="0"><route edges="e5 e6"/></vehicle>\n</routes>\n')
    c = og.concentration(f)
    assert c["vehicles_in_vehroutes"] == 3 and c["top_route_share"] == pytest.approx(2 / 3, abs=1e-4)
    assert c["top_edge_flow_concentration"] == pytest.approx(2 / 3, abs=1e-4)      # e1/e3/e4 by two of three vehicles


@pytest.mark.skipif(not (REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml").exists(), reason="Dhaka net not built here")
def test_oracle_table_aggregates_only_the_window_weighted_by_presence(tmp_path):
    from pipeline.routing import edge_costs as ec, predictive_routing as pr
    import sumolib
    net = sumolib.net.readNet(str(pr.DEFAULT_NET))
    e = next(x for x in net.getEdges() if x.allows("passenger")); eid = e.getID(); free = e.getLength() / e.getSpeed()
    ed = tmp_path / "edgedata.xml"
    ed.write_text(f'<meandata>\n<interval begin="0" end="300"><edge id="{eid}" traveltime="{free*2:.3f}" sampledSeconds="100"/></interval>\n'
                  f'<interval begin="300" end="600"><edge id="{eid}" traveltime="{free*4:.3f}" sampledSeconds="300"/></interval>\n'
                  f'<interval begin="600" end="900"><edge id="{eid}" traveltime="{free*10:.3f}" sampledSeconds="100"/></interval>\n</meandata>\n')
    t = ec.oracle_table(ed, pr.DEFAULT_NET, begin=0, end=600)
    assert t["intervals_aggregated"] == 2 and t["priced_edges"] == 1
    assert t["edges"][eid]["future_tt_s"] == pytest.approx((free * 2 * 100 + free * 4 * 300) / 400, abs=0.01)
    assert t["edges"][eid]["source"] == "MEASURED_ORACLE"
    t2 = ec.oracle_table(ed, pr.DEFAULT_NET, begin=600, end=900)
    assert t2["edges"][eid]["future_tt_s"] == pytest.approx(free * 10, abs=0.01) and t2["future_cost_hash"] != t["future_cost_hash"]


def test_protocol_is_frozen_and_hashed():
    P = og.protocol()
    for k in ("network_hash", "demand_source_hash", "routing_config_hash", "sumo_version", "dev_seeds", "final_seeds", "compliance", "min_saving_s", "admission"):
        assert P[k] not in (None, "", [])
    assert not set(P["dev_seeds"]) & set(P["final_seeds"]) and len(P["final_seeds"]) >= 10
