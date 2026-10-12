"""RQ2 building blocks (docs/PAPER_MAP.md, RQ2): the free-space and queue measures, the gridlock and frontier rules, the correlation."""
from __future__ import annotations

from types import SimpleNamespace

import json

import numpy as np
import pytest

from core.simulation.ambulance.measures import RouteObserver, narrowest_gap
from core.common.paths import REPO
from core.simulation.ambulance.study import gridlocked
from core.simulation.ambulance.summary import frontier, spearman


def test_narrowest_gap_is_the_road_minus_the_fullest_slice():
    assert narrowest_gap(7.0, []) == 7.0
    assert narrowest_gap(7.0, [(3.0, 1.8), (4.0, 1.8), (30.0, 2.5)]) == pytest.approx(3.4)     # two cars side by side 3-4 m ahead
    assert narrowest_gap(3.2, [(1.0, 1.8), (2.0, 1.8)]) == 0.0                                   # never below zero
    assert narrowest_gap(7.0, [(60.0, 1.8)]) == 7.0                                              # beyond the 50 m looked at


class FakeConn:
    """Just enough of TraCI for one second of RouteObserver: an ambulance on a 2-lane road with two cars ahead and a queue."""
    def __init__(self):
        lat = {"car1": 0.0, "car2": 0.0}
        self.lat = lat
        self.vehicle = SimpleNamespace(getIDList=lambda: ["amb", "car1", "car2"], getWidth=lambda v: 2.0 if v == "amb" else 1.8,
                                       getSpeed=lambda v: 1.0, getRoadID=lambda v: "e1", getLanePosition=lambda v: {"amb": 10.0, "car1": 20.0, "car2": 22.0}[v],
                                       getLateralLanePosition=lambda v: lat[v], getRouteIndex=lambda v: 0)
        self.lane = SimpleNamespace(getWidth=lambda l: 3.2, getLength=lambda l: 100.0)
        self.edge = SimpleNamespace(getLaneNumber=lambda e: 2, getLastStepVehicleIDs=lambda e: ["amb", "car1", "car2"],
                                    getLastStepHaltingNumber=lambda e: 6, getLastStepVehicleNumber=lambda e: 3)


def test_route_observer_measures_gap_blocking_yield_and_queue():
    c = FakeConn()
    scen = {"lengths": [150.0, 80.0], "signals": [{"tls": "J1", "route_index": 0, "in_edge": "e1"}]}
    o = RouteObserver(c, scen, "amb")
    o.step(901, True, {"car1", "car2"})
    c.lat["car1"] = 1.2                                        # car1 moves aside more than half the ambulance's width; car2 does not
    o.step(902, True, {"car1", "car2"})
    s = o.summary()
    assert s["free_width_m"] == pytest.approx(6.4 - 3.6)       # cars 10 and 12 m ahead share the 10-15 m slice: 3.6 m of 6.4 taken
    assert s["blocked_s"] == 2 and s["yield_share"] == 0.5 and s["queue_at_signals"] == 6


def test_gridlock_rule():
    arrived = lambda a: {"ambulance": {"arrived": a}, "teleports": 0}
    assert not gridlocked([arrived(True)] * 5, [1000] * 5)["gridlock"]
    assert gridlocked([arrived(False)] * 3 + [arrived(True)] * 2, [1000] * 5)["gridlock"]
    assert gridlocked([{"ambulance": {"arrived": True}, "teleports": 80}] * 5, [1000] * 5)["gridlock"]   # 8 % teleported


def test_frontier_finds_the_lowest_helping_share_and_where_help_stops():
    tab = {"alert": {"0.25": {"1": {"saved_pct_median": 4}, "4": {"saved_pct_median": 1}}, "1": {"1": {"saved_pct_median": 18}, "4": {"saved_pct_median": 3}}},
           "alert_preemption": {"0.25": {"1": {"saved_pct_median": 12}, "4": {"saved_pct_median": 11}}}}
    f = frontier(tab, [1, 4])
    assert f["alert"]["lowest_share_that_helps"] == {"1": 1.0, "4": None} and f["alert"]["stops_helping_at_scale"] == 4
    assert f["alert_preemption"]["stops_helping_at_scale"] is None


def test_spearman_on_known_orders():
    x = np.arange(20.0)
    assert spearman(x, x ** 2)["rho"] == 1.0 and spearman(x, -x)["rho"] == -1.0
    assert spearman([1, 2, 3], [3, 2, 1])["rho"] is None                                       # too few to say


def test_rq2_endpoint_says_plainly_when_not_run(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.emergency import router as r
    from app.main import app
    monkeypatch.setattr(r, "RQ2_DIR", tmp_path)
    c = TestClient(app)
    assert c.get("/api/emergency/rq2").json()["available"] is False
    (tmp_path / "summary.json").write_text('{"findings": {"stops": "x"}}')
    assert c.get("/api/emergency/rq2").json() == {"available": True, "findings": {"stops": "x"}}
    assert c.get("/api/emergency/rq2/figures/summary.json").status_code == 404


# RQ2b: the Dhaka-density corridor
def test_corridor_keep_list_holds_the_route_and_both_camera_sections():
    from core.simulation.ambulance import corridor

    class E:
        def __init__(self, i, shape): self.i, self.s = i, shape
        def getID(self): return self.i
        def getShape(self): return self.s

    class N:
        edges = {"r1": E("r1", [(0, 0), (100, 0)]), "near": E("near", [(150, 250)]), "far": E("far", [(5000, 5000)])}
        def getEdge(self, i): return self.edges[i]
        def getEdges(self): return list(self.edges.values())

    assert corridor.keep_edges(N(), ["r1"], 300) == ["near", "r1"]
    if corridor.NET.exists():                                   # the built corridor network itself
        import sumolib
        net = sumolib.net.readNet(str(corridor.NET))
        ids = {e.getID() for e in net.getEdges()}
        route = json.loads((corridor.EVIDENCE / "calibration.json").read_text())
        assert {corridor.INT, corridor.BM} <= ids
        assert {s["section"] for s in route["sites"]} <= ids
        from core.simulation.ambulance import service
        assert set(service.scenario("dhaka", "generated")["edges"]) <= ids    # the whole ambulance route survived the cut


def test_tighter_lateral_gaps_touch_only_the_four_classes():
    from core.simulation.ambulance import corridor
    text = '<vType id="Motor_Cycle" vClass="motorcycle"/><vType id="Car" vClass="passenger"/><vType id="CNG" x="1"/><vType id="Bus"/>'
    out = corridor.tighten(text)
    assert 'id="Car" vClass="passenger"/>' in out and '<vType id="Bus"/>' in out
    assert 'id="Motor_Cycle" vClass="motorcycle" minGapLat="0.1"' in out and 'id="CNG" x="1" minGapLat="0.2"' in out
    assert set(corridor.TIGHT) == {"Motor_Cycle", "Bicycle", "Rickshaw", "CNG"}


def test_dhaka_density_label_only_inside_the_recorded_iqr():
    from core.simulation.ambulance.summary import dhaka_label
    rec = {"density_q25": 36.5, "density_q75": 126.6}
    assert dhaka_label(54.37, rec, 0.78) == "Dhaka density"
    assert dhaka_label(20.3, rec, 0.72) == "corridor x0.72"
    assert dhaka_label(130.0, rec, 0.9) == "corridor x0.9"


def test_dhaka_density_sentence_states_the_table_numbers():
    from core.simulation.ambulance.summary import dhaka_sentence
    dl = {"reached": True, "INT_density_median": 54.37, "INT_entered_per_hour_median": 653, "recorded": {"density_median": 57.7, "flow_veh_h_median": 1184}}
    tab = {"alert": {"1": {"dhaka": {"saved_s_median": 23.0, "saved_s_q25": 10.0, "saved_s_q75": 40.5, "seeds": 10, "slower_runs": 2}}},
           "rl_signals": {"0": {"dhaka": {"saved_s_median": 31.0, "saved_s_q25": 20.0, "saved_s_q75": 44.0}}}}
    s = dhaka_sentence(dl, tab)
    for x in ("54.37", "57.7", "saves a median 23.0 s", "10.0 to 40.5", "10 paired seeds", "2 of them slower", "31.0 s", "653", "1184"):
        assert x in s
    assert dhaka_sentence({"reached": False}, tab) is None


def test_summary_dhaka_row_matches_its_sentence():
    p = REPO / "results/emergency/dhaka/rq2/summary.json"
    if not p.exists():
        return
    s = json.loads(p.read_text())
    c = s["saved"].get("alert", {}).get("1", {}).get("dhaka")
    if not c:
        return
    assert f"a median {abs(c['saved_s_median'])} s (time saved, 25-75 %: {c['saved_s_q25']} to {c['saved_s_q75']} s) over {c['seeds']} paired seeds" in s["findings"]["dhaka_density"]
    assert str(s["dhaka_level"]["INT_density_median"]) in s["findings"]["dhaka_density"]


def test_plain_sentence_numbers_come_from_the_table_and_wait_for_a_complete_dhaka_row():
    import pandas as pd
    from core.simulation.ambulance.summary import plain
    cell = lambda m, n=10, q=5.0, slow=0: {"saved_s_median": m, "saved_s_q25": q, "seeds": n, "slower_runs": slow}
    j = pd.DataFrame([{"arm": "alert", "share": 1.0, "level": lv, "base_s": b, "saved_s": sv} for lv, b, sv in
                      (("1", 200, 23), ("1", 220, -10), ("dhaka", 350, -230))])
    tab = {"alert": {"1": {"1": cell(22.5, q=-1.0, slow=1), "dhaka": cell(-230.0, q=-291.8, slow=7)}}, "rl_signals": {"0": {"1": cell(32.5), "dhaka": cell(40.0, n=3)}}}
    p = plain(tab, j)
    assert p["level"] == "1"                                   # the Dhaka row's sumo-rl arm is not complete yet
    assert p["not_every_time"] is True                         # 1 of 2 runs slower: the sentence says "though not every time", no counts
    assert (p["alert_s"], p["signals_s"], p["trip_s"], p["alert_reliable"], p["signals_more"]) == (23, 33, 210, False, True)
    assert (p["slower_runs"], p["alert_runs"]) == (1, 2)                   # the sentence's own runs: alert to every vehicle at its level
    tab["rl_signals"]["0"]["dhaka"] = cell(40.0)
    p = plain(tab, j)
    assert (p["level"], p["alert_s"], p["signals_s"], p["trip_s"], p["slower_runs"], p["alert_runs"]) == ("dhaka", -230, 40, 350, 1, 1)
    tab["rl_signals"]["0"]["dhaka"] = cell(-49.5)
    assert plain(tab, j)["signals_more"] is False                             # less bad than the alert is not "did more"


def test_slowdown_cause_reads_the_chain_ahead():
    import importlib.util
    spec = importlib.util.spec_from_file_location("sd", REPO / "research/ambulance_rq2/scripts/slowdown_summary.py")
    sd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sd)
    lead = {"making_way": True, "needs_lane_change": False}
    stuck = {"making_way": True, "needs_lane_change": True}
    assert sd.cause({"leader": None}) == "nothing within 100 m ahead"
    assert sd.cause({"leader": lead, "ahead_of_leader": [lead, stuck]}) == "behind a vehicle waiting at a lane end it may not leave (alerted)"
    assert sd.cause({"leader": lead, "ahead_of_leader": []}) == "behind alerted vehicles, no such lane end in the 4 ahead"
    assert sd.cause({"leader": {"making_way": False}, "ahead_of_leader": []}) == "behind vehicles that were not alerted"


def test_make_way_default_is_the_bluelight_settings_and_the_variant_only_keeps_strategic():
    from core.simulation.ambulance.makeway import MakeWay

    class V:
        def __init__(self): self.p = {}
        def getLaneChangeMode(self, v): return 1621
        def getLateralAlignment(self, v): return "center"
        def getParameter(self, v, k): return ""
        def setLaneChangeMode(self, v, m): self.p["mode"] = m
        def setLateralAlignment(self, v, a): self.p["align"] = a
        def setParameter(self, v, k, x): self.p[k] = x
        def getLaneIndex(self, v): return 0
        def getRoadID(self, v): return "e"

    for keep, strategic in ((False, "-1"), (True, None)):
        c = SimpleNamespace(vehicle=V(), edge=SimpleNamespace(getLaneNumber=lambda e: 2))
        MakeWay(c, keep_strategic=keep).alert("x")
        assert c.vehicle.p["mode"] == 1605 and c.vehicle.p["align"] == "right"
        assert c.vehicle.p.get("laneChangeModel.lcStrategic") == strategic


# RQ2c: make-way v2
def test_make_way_v2_is_the_default_and_v1_stays_reproducible_by_config():
    from core.simulation.ambulance import service
    mk = service.settings()["alert"]["makeway"]
    assert mk["version"] == 2 and mk["keep_strategic"] is True and mk["distance_m"] == 100
    choice = json.loads((REPO / "evidence/ambulance_rq2/makeway_v2/choice.json").read_text())
    assert choice["chosen_distance_m"] == mk["distance_m"]
    for overrides, (dist, keep) in (({}, (100, True)), ({"makeway": {"version": 1}}, (None, False))):
        cfg = json.loads(json.dumps(service.settings()))
        cfg["alert"].update(overrides)
        run = service.AmbulanceRun(SimpleNamespace(), {}, "no_alert", None, 0.0, 11, cfg)
        assert (run.makeway_m, run.makeway.keep_strategic) == (dist, keep)


def test_current_results_read_alerting_arms_only_from_runs_v2(tmp_path, monkeypatch):
    from core.simulation.ambulance import summary as S

    v1, v2 = tmp_path / "runs", tmp_path / "runs_v2"
    for root, name, arm, tt in ((v1, "no_alert_s11", "no_alert", 200), (v1, "alert_s11", "alert", 150), (v2, "alert_s11", "alert", 190)):
        d = root / "dhaka" / "generated" / name
        d.mkdir(parents=True)
        (d / "metrics.json").write_text(json.dumps({"arm": arm, "equipped_share": 0.0 if arm == "no_alert" else 1.0, "seed": 11, "scale": 1.0, "demand_id": "generated",
                                                    "ambulance": {"arrived": True, "travel_time_s": tt}}))
    monkeypatch.setattr(S, "RUNS", v1)
    monkeypatch.setattr(S, "RUNS_V2", v2)
    cur, old = S.rows(2), S.rows(1)
    assert sorted(cur[cur.arm == "alert"].travel_s) == [190] and sorted(old[old.arm == "alert"].travel_s) == [150]
    assert list(cur[cur.arm == "no_alert"].travel_s) == [200] == list(old[old.arm == "no_alert"].travel_s)
    ovn = S.old_vs_new(S.table(S.paired(old)), S.table(S.paired(cur)))
    assert ovn["alert"]["1"]["1"]["v1"]["saved_s_median"] == 50.0 and ovn["alert"]["1"]["1"]["v2"]["saved_s_median"] == 10.0
