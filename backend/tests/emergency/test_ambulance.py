"""The ambulance experiments: honest refusals, the device's own side rule, and which configurations may run."""
import pytest

from core.common.data import city_config
from core.simulation.ambulance import service
from core.simulation.ambulance.makeway import MakeWay, side
from core.networking.v2x import model


def test_the_side_is_the_bluelight_devices_own_rule():
    assert [side(i, 3) for i in range(3)] == ["right", "right", "left"]      # MSDevice_Bluelight: the highest-index lane goes left, the others right
    assert side(0, 1) == "left"


def test_a_city_without_an_ambulance_trip_is_refused():
    without = next(c for c in city_config.list_ids() if city_config.load(c).emergency is None)
    service.scenario.cache_clear()
    with pytest.raises(service.Refused, match="no data for this city"):
        service.scenario(without)
    with pytest.raises(service.Refused, match="no data for this city"):
        service.scenario("no_such_city")


def test_a_technology_with_an_unsourced_parameter_is_left_out_and_named():
    confs, refused = service.configurations()
    techs = {c[1] for c in confs if c[1]}
    assert set(refused) == {t for t in service.settings()["technologies"] if model.unsourced(t)}
    assert not techs & set(refused) and ("no_alert", None, 0.0) in confs
    assert not [c for c in confs if c[0] == "alert" and c[2] == 0]              # share 0 without preemption is the baseline itself
    for t in techs:
        assert ("alert_preemption", t, 0.0) in confs


def test_an_alert_arm_refuses_an_unsourced_technology_before_anything_runs():
    unsourced = [t for t in service.settings()["technologies"] if model.unsourced(t)]
    if not unsourced:
        pytest.skip("every configured technology is sourced")
    with pytest.raises(model.Refused, match=unsourced[0]):
        service.AmbulanceRun(None, {}, "alert", unsourced[0], 1.0, 11)


def test_make_way_restores_what_it_changed():
    class V:
        def __init__(self):
            self.mode, self.align, self.par = 1621, "center", {"laneChangeModel.lcStrategic": "1.0"}
        getLaneChangeMode = lambda s, v: s.mode
        getLateralAlignment = lambda s, v: s.align
        getParameter = lambda s, v, k: s.par[k]
        getLaneIndex = lambda s, v: 2
        getRoadID = lambda s, v: "e"
        def setLaneChangeMode(s, v, m): s.mode = m
        def setLateralAlignment(s, v, a): s.align = a
        def setParameter(s, v, k, x): s.par[k] = x
    from types import SimpleNamespace
    veh = V()
    mw = MakeWay(SimpleNamespace(vehicle=veh, edge=SimpleNamespace(getLaneNumber=lambda e: 3)))
    assert mw.alert("a") and not mw.alert("a")
    assert (veh.mode, veh.align, veh.par["laneChangeModel.lcStrategic"]) == (1605, "left", "-1")
    mw.release("a", present=True)
    assert (veh.mode, veh.align, veh.par["laneChangeModel.lcStrategic"]) == (1621, "center", "1.0") and not mw.before


def test_the_api_refuses_honestly_and_tables_are_per_city_and_labelled(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from core.simulation.twin.live import runtime as live
    started = []
    monkeypatch.setattr(live.live_sim, "start", lambda params, owner=None: started.append(params) or {"run_id": "x", "status": "starting"})
    c = TestClient(app)
    without = next(i for i in city_config.list_ids() if city_config.load(i).emergency is None)
    r = c.post("/api/emergency/runs", json={"city_id": without, "arm": "no_alert"})
    assert r.status_code == 409 and "no data for this city" in r.json()["detail"] and not started
    unsourced = [t for t in service.settings()["technologies"] if model.unsourced(t)]
    if unsourced:
        with_trip = next(i for i in city_config.list_ids() if city_config.load(i).emergency is not None)
        r = c.post("/api/emergency/runs", json={"city_id": with_trip, "arm": "alert", "technology": unsourced[0]})
        assert r.status_code in (409,) and not started                      # refused: the technology has a parameter without a source (or the city is not built here)
    got = c.get(f"/api/emergency/results/{without}").json()
    assert got["label"] == "SIMULATED" and all(not t["available"] and "no data for this city" in t["reason"] for t in got["tables"])
    assert c.get("/api/emergency/runs/nothing").status_code == 404


def test_a_simulated_ambulance_appears_in_the_feed_only_for_its_city_and_only_while_driving(monkeypatch):
    from app.alerts import service as alerts
    from core.common import tag
    from core.simulation.twin.live import runtime as live
    e = {"label": "SIMULATED", "arm": "alert", "technology": "its_g5", "state": "driving", "vehicles_alerted": 4, "junctions_preempted_now": [], "demand": {"label": "SYNTHETIC_WHAT_IF", "calibrated_to": None}}
    monkeypatch.setattr(live.live_sim, "state", lambda with_vehicles=True: {"run_id": "r1", "status": "running", "params": {"network": "here"}, "emergency": e})
    items = alerts.ambulance_items("here")
    assert [(i["kind"], i["stamp"], i["tag"]["kind"], i["tag"]["calibrated_to"]) for i in items] == [("ambulance", "SIMULATED", "simulated", "uncalibrated")]
    assert tag.untagged(items) == [] and alerts.ambulance_items("elsewhere") == []
    e["state"] = "arrived"
    assert alerts.ambulance_items("here") == []


def test_nothing_in_the_ambulance_code_can_notify_or_call_anyone():
    import ast, inspect
    from core.simulation.ambulance import makeway, results
    from app.emergency import router
    from core.simulation.signals.preemption import sumo_adapter
    banned = {"requests", "httpx", "urllib", "smtplib", "boto3", "socket", "app.plan.notifications", "app.plan", "twilio"}
    for mod in (service, makeway, results, router, sumo_adapter):
        tree = ast.parse(inspect.getsource(mod))
        names = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names} | {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not {n for n in names if n in banned or n.split(".")[0] in banned}, mod.__name__


def test_result_rows_are_paired_by_seed_and_count_crashes(tmp_path):
    import json
    from core.simulation.ambulance import results
    def write(arm, tech, share, seed, state, amb, loss):
        d = tmp_path / "c" / "generated" / service.run_name(arm, tech, share, seed)
        d.mkdir(parents=True)
        (d / "metrics.json").write_text(json.dumps({"arm": arm, "technology": tech, "equipped_share": share, "seed": seed, "state": state, "demand": {"label": "x", "calibrated_to": None}, "route_m": 1.0,
            "signals_on_route": 0, "sumo_extra": [], "vehicles_alerted": 3, "messages": {"delivered": 5}, "junctions_preempted": [], "teleports": 0 if state == "arrived" else None,
            "ambulance": {"travel_time_s": amb}, "others": {"mean_time_loss_s": loss, "total_vehicle_hours": 1.0} if state == "arrived" else None}))
    for seed, base, alert in ((1, 200.0, 180.0), (2, 210.0, 200.0), (3, 220.0, None)):
        write("no_alert", None, 0.0, seed, "arrived", base, 50.0)
        write("alert", "its_g5", 1.0, seed, "arrived" if alert else "sumo_crashed", alert, 51.0)
    write("alert", "its_g5", 1.0, 4, "arrived", 100.0, 51.0)                       # its baseline never ran: it pairs with nothing
    out = results.build("c", "generated", root=tmp_path, evidence=None)
    row = next(r for r in out["rows"] if r["arm"] == "alert")
    assert row["pairs"] == 2 and row["seeds"] == [1, 2] and row["crashed"] == 1
    assert row["ambulance_time_saved_s"]["mean"] == 15.0 and row["others_mean_time_loss_change_s"]["mean"] == 1.0
    assert out["runs"] == {"total": 7, "finished": 6, "sumo_crashed": 1, "ambulance_not_arrived": 0}
    assert results.read("c", "calibrated", root=tmp_path)["available"] is False


def test_the_plain_sentence_numbers_come_from_the_same_rows_as_the_table(tmp_path):
    """CLAUDE.md, plain language rule 5: the everyday Emergency sentence is computed from the result file, never typed in."""
    import json
    from core.simulation.ambulance import results
    def write(arm, tech, share, seed, amb):
        d = tmp_path / "c" / "generated" / service.run_name(arm, tech, share, seed)
        d.mkdir(parents=True)
        (d / "metrics.json").write_text(json.dumps({"arm": arm, "technology": tech, "equipped_share": share, "seed": seed, "state": "arrived", "demand": {"label": "x", "calibrated_to": None}, "route_m": 1,
            "signals_on_route": 0, "sumo_extra": [], "vehicles_alerted": 3, "messages": {"delivered": 5}, "junctions_preempted": [], "teleports": 0,
            "ambulance": {"travel_time_s": amb}, "others": {"mean_time_loss_s": 50.0, "total_vehicle_hours": 1.0}}))
    for seed in (1, 2):
        write("no_alert", None, 0.0, seed, 200.0)
        write("alert", "its_g5", 1.0, seed, 180.0)                 # 10 % saved
        write("alert_preemption", "its_g5", 1.0, seed, 170.0)      # 15 %
        write("alert_preemption", "c_v2x", 1.0, seed, 160.0)       # 20 %
        write("alert_preemption", "c_v2x", 0.5, seed, 150.0)       # not every vehicle equipped: not in the sentence
    out = results.build("c", "generated", root=tmp_path, evidence=None)
    p = out["plain"]
    assert p["trip_s"] == 200.0 and p["alert_only_saved_pct"] == {"min": 10.0, "max": 10.0, "technologies": 1}
    assert p["alert_and_signals_saved_pct"] == {"min": 15.0, "max": 20.0, "technologies": 2}
    means = sorted(r["ambulance_time_saved_pct"]["mean"] for r in out["rows"] if r["arm"] == "alert_preemption" and r["equipped_share_pct"] == 100)
    assert [p["alert_and_signals_saved_pct"]["min"], p["alert_and_signals_saved_pct"]["max"]] == [means[0], means[-1]]


def test_the_checked_in_dhaka_sentence_matches_its_table():
    from core.simulation.ambulance import results
    t = results.read("dhaka", "generated")
    if not t.get("available"):
        pytest.skip("no Dhaka result built here")
    assert t["plain"] == results.plain_numbers(t["rows"])
