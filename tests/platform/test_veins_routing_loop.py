"""The Veins forecast-routing loop (core/simulation/routing/veins_routing_loop.py, Phase 2 of the Veins loops, 2026-10-12).

Unit tests on the files the loop writes, its RSU placement and its reading of Veins's scalars run everywhere; the end-to-end test (SUMO 1.21
with two clients on the LA twin, both arms, 5 minutes after the warm-up) runs only where Veins, OMNeT++, the apps and the forecaster are
present, and never alongside the SUMO jobs."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
from core.simulation.ambulance import veins_loop as vl  # noqa: E402
from core.simulation.routing import veins_routing_loop as vr  # noqa: E402

LA_NET = REPO / "data/cities/la_c4_central_wide/sumo/la_c4_central_wide.net.xml"


def test_veins_stats_reads_cars_and_rsus():
    vals = {"SharedSumoScenarioExt.node[1].appl": {"statusSent": 40, "adviceReceived": 2, "adviceApplied": 1, "adviceInapplicable": 1, "adviceDeferred": 1},
            "SharedSumoScenarioExt.node[2].appl": {"statusSent": 30}, "SharedSumoScenarioExt.node[2].nic.phy80211p": {"SNIRLostPackets": 3, "RXTXLostPackets": 0},
            "SharedSumoScenario.rsu[0].appl": {"statusReceived": 25, "adviceSent": 2}, "SharedSumoScenario.rsu[0].nic.phy80211p": {"SNIRLostPackets": 4, "RXTXLostPackets": 1},
            "SharedSumoScenario.rsu[1].appl": {"statusReceived": 5, "adviceSent": 0}}
    s = vr.veins_stats(vals, [{"node": "A"}, {"node": "B"}])
    assert s["status_sent"] == 70 and s["status_received_at_rsus"] == 30 and s["advice_sent_by_rsus"] == 2
    assert s["advice_received"] == 2 and s["advice_applied"] == 1 and s["advice_inapplicable"] == 1 and s["advice_deferred_on_junction"] == 1
    assert s["per_rsu"][0] == {"rsu": 0, "node": "A", "status_received": 25, "advice_sent": 2, "lost_interference_or_collision": 4, "lost_while_transmitting": 1}
    assert s["frames_lost_all_nodes"] == {"interference_or_collision": 7, "while_transmitting": 1}


def test_busiest_junctions_are_ranked_and_spaced(tmp_path):
    if not LA_NET.exists():
        pytest.skip("LA twin not built")
    from core.simulation.twin.network import net_for
    net = net_for(LA_NET)
    edges = [e for e in net.getEdges() if not e.getID().startswith(":")][:6]
    rows = "".join(f'<edge id="{e.getID()}" entered="{(i + 1) * 100}"/>' for i, e in enumerate(edges))
    ed = tmp_path / "edgedata.xml"; ed.write_text(f'<meandata><interval begin="0" end="300">{rows}</interval><interval begin="300" end="600">{rows}</interval></meandata>')
    got = vr.busiest_junctions(net, ed, 3, min_gap_m=0.0)
    assert len(got) == 3 and got[0]["entered"] >= got[1]["entered"] >= got[2]["entered"]
    assert got[0]["node"] == edges[-1].getToNode().getID() or got[0]["entered"] >= 1200       # the edge with the most entered vehicles (summed over intervals) leads
    far = vr.busiest_junctions(net, ed, 3, min_gap_m=1e9)
    assert len(far) == 1                                                                     # a huge spacing leaves the single best junction


def test_ini_and_cfg_follow_the_arm(tmp_path):
    if not LA_NET.exists():
        pytest.skip("LA twin not built")
    P = {"network": str(LA_NET.relative_to(REPO)), "time_to_teleport_s": 300, "penetration": 0.3}
    cfgf = vr.write_sumo_cfg(tmp_path, P, tmp_path / "demand.rou.xml", 2100)
    text = cfgf.read_text()
    assert '<end value="2100"/>' in text and '<route-steps value="0"/>' in text and "tripinfo-output.write-unfinished" in text and "summary-output" in text
    rsus = [{"node": "n1", "sumo_xy": [10.0, 20.0], "veins_xy": [35.0, 1005.0]}, {"node": "n2", "sumo_xy": [30.0, 40.0], "veins_xy": [55.0, 985.0]}]
    for arm, active in (("baseline", "false"), (vr.ARM, "true")):
        ini = (vr.write_veins(tmp_path / arm, cfgf, P, rsus, 201, arm, 2100, 9977, False, 10) / "omnetpp.ini").read_text()
        assert f"*.rsu[*].appl.active = {active}" in ini and f"*.node[*].appl.active = {active}" in ini
        assert "network = SharedSumoScenarioExt" in ini and "*.manager.order = 1" in ini and "*.manager.port = 9977" in ini and "*.manager.penetrationRate = 0.3" in ini
        assert '*.rsu[1].appl.poiId = "RSU 1"' in ini and "*.rsu[1].mobility.x = 55.0" in ini and "*.numRsu = 2" in ini and "*.node[*].appl.statusInterval = 10s" in ini
        assert "*.manager.commandLine" not in ini                                            # the Python client owns SUMO in Phase 2


def test_the_routing_apps_carry_the_gpl_header():
    src = REPO / "research/veins_loops/src"
    for f in ("RoutingCar11p.h", "RoutingRSU11p.h", "PoiParams.h"):
        t = (src / f).read_text()
        assert "SPDX-License-Identifier: GPL-2.0-or-later" in t and "Sommer" in t
    assert (REPO / "research/veins_loops/SharedSumoScenarioExt.ned").exists()


@pytest.mark.slow
@pytest.mark.skipif(vl.ready() is not None or not LA_NET.exists() or os.environ.get("DHAKAFLOW_SKIP_SUMO") == "1", reason="Veins routing loop not runnable here")
def test_both_arms_run_on_one_sumo_and_advice_travels_over_veins():
    """Seed 201, 5 minutes after the warm-up, both arms on one SUMO 1.21 each: statuses really received by RSUs reach the server, advice goes
    back through an RSU frame, the comparison is written with SHA256SUMS."""
    out = REPO / "evidence/live_runs/veins_routing_pytest"
    r = subprocess.run([sys.executable, "-m", "core.simulation.routing.veins_routing_loop", "--no-gui", "--minutes", "5", "--rsus", "20", "--out", str(out)],
                       cwd=REPO, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}, timeout=1800)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    s = json.loads((out / "summary.json").read_text())
    assert s["arms"]["baseline"]["state"] == "ok" and s["arms"][vr.ARM]["state"] == "ok"
    n = s["arms"][vr.ARM]["network"]
    assert n["uplink"]["messages_tx"] > 0 and n["uplink"]["unique_to_server"] > 0 and n["connected_vehicles"] > 0
    assert s["arms"]["baseline"]["network"]["uplink"]["messages_tx"] == 0                   # radios silent in the baseline
    assert s["comparison"]["difference_vehicle_hours"] is not None and (out / "SHA256SUMS").exists()
