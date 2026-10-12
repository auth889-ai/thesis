"""The Veins ambulance loop (core/simulation/ambulance/veins_loop.py, Phase 1 of the Veins loops, 2026-10-12).

Unit tests on the files the loop writes and on its reading of Veins's scalars run everywhere; the end-to-end test (SUMO 1.21 with two
clients: Veins in Cmdenv + the loop) runs only where Veins, OMNeT++ and the apps are built, and never alongside the SUMO jobs."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
from core.simulation.ambulance import veins_loop as vl  # noqa: E402

PY_RL = Path.home() / ".dhakaflow/venvs/sumo-rl-np1/bin/python"


def test_veins_stats_reads_per_rsu_and_sums_the_ambulance_modules():
    vals = {"SharedSumoScenario.node[3].appl": {"alertsSent": 50, "ambulanceTimeInNetwork": 50, "alertsReceived": 0, "madeWay": 0},
            "SharedSumoScenario.node[9].appl": {"alertsSent": 220, "ambulanceTimeInNetwork": 220},
            "SharedSumoScenario.node[4].appl": {"alertsReceived": 300, "madeWay": 7, "generatedBSMs": 10, "receivedBSMs": 400},
            "SharedSumoScenario.rsu[0].appl": {"denmReceived": 4, "flagsWritten": 8}, "SharedSumoScenario.rsu[0].nic.phy80211p": {"SNIRLostPackets": 2, "RXTXLostPackets": 1},
            "SharedSumoScenario.rsu[1].appl": {"denmReceived": 30, "flagsWritten": 60}, "SharedSumoScenario.rsu[1].nic.phy80211p": {"SNIRLostPackets": 5, "RXTXLostPackets": 0}}
    s = vl.veins_stats(vals, [{"tls": "A"}, {"tls": "B"}])
    assert s["denm_sent"] == 270 and s["ambulance_time_in_veins_s"] == 270 and s["ambulance_modules"] == 2
    assert s["per_rsu"]["A"] == {"rsu": 0, "sent": 270, "received": 4, "lost_interference_or_collision": 2, "lost_while_transmitting": 1, "not_received_below_sensitivity": 263, "flags_written": 8}
    assert s["per_rsu"]["B"]["received"] == 30 and s["rsu_receptions"] == 34 and s["car_receptions"] == 300 and s["cars_made_way"] == 7
    assert s["beacons_generated"] == 10 and s["frames_lost_all_nodes"] == {"interference_or_collision": 7, "while_transmitting": 1}


def test_read_scalars_parses_a_sca_file(tmp_path):
    (tmp_path / "Default-#0.sca").write_text("version 3\nrun x\nscalar SharedSumoScenario.rsu[0].appl denmReceived 12\nscalar SharedSumoScenario.node[1].appl alertsSent 99\nattr unit s\n")
    v = vl.read_scalars(tmp_path)
    assert v["SharedSumoScenario.rsu[0].appl"]["denmReceived"] == 12 and v["SharedSumoScenario.node[1].appl"]["alertsSent"] == 99


@pytest.mark.skipif(not (REPO / "data/cities/dhaka/sumo/corridor/dhaka_corridor.net.xml.gz").exists(), reason="corridor not built")
def test_rsu_positions_lie_inside_the_veins_playground():
    net = REPO / "data/cities/dhaka/sumo/corridor/dhaka_corridor.net.xml.gz"
    x0, y0, x1, y1 = vl.net_bounds(net)
    import pickle
    q = pickle.loads((REPO / "results/emergency/dhaka/rq2/rl/q_dhaka_density_x0.78.pkl").read_bytes())
    rsus = vl.rsu_positions(net, list(q))
    assert len(rsus) == 3
    for r in rsus:
        vx, vy = r["veins_xy"]
        assert 0 <= vx <= (x1 - x0) + 200 and 0 <= vy <= (y1 - y0) + 200          # inside playgroundSizeX/Y of the ini
        sx, sy = r["sumo_xy"]
        assert abs((sx - x0 + 25) - vx) < 1e-6 and abs(((y1 - y0) - (sy - y0) + 25) - vy) < 1e-6


def test_ini_and_sumo_cfg_follow_the_arm(tmp_path):
    scen = {"net": REPO / "data/cities/dhaka/sumo/corridor/dhaka_corridor.net.xml.gz", "routes": REPO / "data/cities/dhaka/sumo/corridor/dhaka_density.rou.xml"}
    if not Path(scen["net"]).exists():
        pytest.skip("corridor not built")
    cfg = {"sumo": {"lateral_resolution": 0.8, "time_to_teleport_s": 300}, "alert": {"makeway": {"distance_m": 100}}}
    rsus = [{"tls": "T1", "veins_xy": [10.0, 20.0]}, {"tls": "T2", "veins_xy": [30.0, 40.0]}]
    cfgf = vl.write_sumo_cfg(tmp_path, scen, tmp_path / "vt.rou.xml", 0.78, 3600, cfg)
    text = cfgf.read_text()
    assert '<scale value="0.78"/>' in text and '<end value="3600"/>' in text and "tripinfo-output.write-unfinished" in text and "dhaka_buildings.poly.xml" in text
    for arm, active in (("fixed", "false"), ("rl", "false"), ("rl_v2i", "true")):
        d = vl.write_veins(tmp_path / arm, cfgf, scen, rsus, 11, arm, 1.0, 3600, 9977, False, cfg)
        ini = (d / "omnetpp.ini").read_text()
        assert f"*.rsu[*].appl.active = {active}" in ini and f"*.node[*].appl.active = {active}" in ini
        assert "*.manager.order = 1" in ini and "--num-clients 2" in ini and "*.manager.port = 9977" in ini and "*.numRsu = 2" in ini
        assert '*.rsu[1].appl.tlsId = "T2"' in ini and "*.rsu[1].mobility.x = 30.0" in ini and "sim-time-limit = 3600s" in ini
        assert "*.node[*].appl.makewayDistance = 100m" in ini and "*.node[*].appl.sendBeacons = false" in ini
    ini = (vl.write_veins(tmp_path / "cam", cfgf, scen, rsus, 11, "rl_v2i", 1.0, 3600, 9977, True, cfg, beacons=True) / "omnetpp.ini").read_text()
    assert "*.node[*].appl.sendBeacons = true" in ini and "sumo-gui" in ini and "--start --quit-on-end" in ini


def test_the_apps_carry_the_gpl_header_and_are_derived_from_veins():
    src = REPO / "research/veins_loops/src"
    for f in ("AmbulanceLoop11p.h", "AmbulanceLoopRSU11p.h"):
        t = (src / f).read_text()
        assert "SPDX-License-Identifier: GPL-2.0-or-later" in t and "Derived from Veins" in t
    assert "TraCIDemo11p" in (src / "AmbulanceLoop11p.h").read_text() and "TraCIDemoRSU11p" in (src / "AmbulanceLoopRSU11p.h").read_text()


@pytest.mark.slow
@pytest.mark.skipif(vl.ready() is not None or not PY_RL.exists() or os.environ.get("DHAKAFLOW_SKIP_SUMO") == "1", reason="Veins loop not runnable here")
def test_two_clients_drive_one_sumo_and_the_rsu_flag_preempts(tmp_path):
    """SUMO 1.21 with --num-clients 2: Veins (Cmdenv, order 1) and the loop (order 2) run seed 11 / rl_v2i to 1 200 s; the ambulance departs
    at 900 s, its DENMs are really received by the route's RSUs and the junctions are pre-empted on those receptions; metrics come from
    SUMO's tripinfo and Veins's scalars."""
    out = REPO / "evidence/live_runs/veins_loop_pytest"
    r = subprocess.run([str(PY_RL), str(REPO / "core/simulation/ambulance/veins_loop.py"), "--no-gui", "--seeds", "11", "--arms", "rl_v2i", "--horizon", "1200", "--out", str(out)],
                       cwd=REPO, capture_output=True, text=True, env={**os.environ, "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}, timeout=900)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    m = json.loads(next((out / "runs").glob("rl_v2i_p100_s11_x*/metrics.json")).read_text())
    assert m.get("state") != "crashed" and m["veins_exit"] == 0 and m["sumo"].startswith("1.21.0 --num-clients 2")
    assert m["ambulance"]["depart_s"] == 900.0 and m["veins"]["denm_sent"] > 0 and m["veins"]["rsu_receptions"] > 0
    route = [s for s in m["messages_per_junction"]]
    assert len(route) == 2 and all(m["messages_per_junction"][t]["delivered"] > 0 for t in route)
    assert {e["what"] for e in m["preemption_events"]} >= {"informed", "takeover"}
    assert re.search(r"junction .* INFORMED", (next((out / "runs").glob("rl_v2i_p100_s11_x*")) / "run.log").read_text())
    assert (out / "SHA256SUMS").exists()
