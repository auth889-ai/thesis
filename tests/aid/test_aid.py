"""AID (step J): stations every 300 m along the route, the California #7 state machine, the pair row, the incident plan and the
metrics. No SUMO here; the runs are checked by scripts/aid/aid.py's own outputs."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]

from core.simulation.aid import california7 as cal  # noqa: E402
from core.simulation.aid import run as R  # noqa: E402
from core.simulation.aid import stations as stn  # noqa: E402


class _Edge:
    def __init__(self, eid, length, lanes=2, fn=""):
        self._id, self._len, self._n, self._fn = eid, length, lanes, fn
    def getID(self): return self._id
    def getLength(self): return self._len
    def getFunction(self): return self._fn
    def getLanes(self): return [type("L", (), {"getID": (lambda self, i=i, e=self._id: f"{e}_{i}")})() for i in range(self._n)]


class _Net:
    def __init__(self, edges): self.e = {x.getID(): x for x in edges}
    def getEdge(self, eid): return self.e[eid]


def test_stations_every_300_m_with_their_segments():
    net = _Net([_Edge("a", 250), _Edge(":j", 5, fn="internal"), _Edge("b", 400), _Edge("c", 100), _Edge("d", 300)])
    sts = stn.stations(net, ["a", ":j", "b", "c", "d"], spacing=300)
    assert [(s["id"], s["edge"], s["pos"], s["chainage"]) for s in sts] == [("s1", "b", 50.0, 300), ("s2", "b", 350.0, 600), ("s3", "d", 150.0, 900)]
    assert sts[0]["segment_edges"] == ["b"] and sts[1]["segment_edges"] == ["b", "c", "d"] and sts[2]["segment_edges"] == ["d"]
    assert sts[0]["lanes"] == ["b_0", "b_1"]


def test_pair_row_encodes_a_missing_speed_as_the_limit_with_a_flag():
    up, down = {"speed": None, "occ": 30.0, "flow": 0}, {"speed": 20.0, "occ": 10.0, "flow": 5}
    r = stn.pair_features(up, down, {"occ": 12.0}, {"occ": 20.0}, 50.0)
    assert r["up_speed"] == 50.0 and r["up_empty"] == 1 and r["down_empty"] == 0
    assert r["occdf"] == 20.0 and r["occrdf"] == round(20 / 30, 4) and r["docctd"] == 0.5 and r["down_occ_prev"] == 12.0
    assert all(f in r for f in stn.FEATURES)


def test_california7_alarms_once_after_persistence_and_resets():
    th = cal.Thresholds(8.0, 0.3, 0.2)
    rows = [dict(occdf=0, occrdf=0, docctd=0), dict(occdf=10, occrdf=0.5, docctd=0.3), dict(occdf=10, occrdf=0.5, docctd=0.0),
            dict(occdf=10, occrdf=0.5, docctd=0.0), dict(occdf=0, occrdf=0.0, docctd=0.0), dict(occdf=10, occrdf=0.5, docctd=0.3), dict(occdf=0, occrdf=0, docctd=0)]
    assert cal.alarms(rows, th) == [False, False, True, False, False, False, False]      # tentative -> confirmed once; a one-off never alarms


def test_incident_plan_is_fixed_by_the_seed_and_spaced():
    a, b = R.plan_incidents(7, 4, [0, 2, 4]), R.plan_incidents(7, 4, [0, 2, 4])
    assert a == b and all(x["pair"] in (0, 2, 4) for x in a) and all(x["start_s"] >= R.WARMUP_S + 400 for x in a)
    assert all(y["start_s"] - x["start_s"] >= 400 for x, y in zip(a, a[1:]))
    assert R.plan_incidents(8, 4, [1]) != a


def test_metrics_count_detections_inside_the_incident_and_false_alarms_outside():
    sys.path.insert(0, str(REPO / "scripts/aid"))
    import aid
    rows = [{"pair": p, "t": t} for p in (0, 1) for t in range(600, 3600, 30)]
    inc = [{"pair": 0, "actual_start_s": 1000.0, "actual_end_s": 1200.0, "duration_s": 200}, {"pair": 1, "actual_start_s": 2000.0, "actual_end_s": 2200.0, "duration_s": 200}]
    m = aid.metrics(rows, {0: [1060.0, 3000.0], 1: []}, inc, 3600)
    assert m["detected"] == 1 and m["detection_rate"] == 0.5 and m["time_to_detect_s_mean"] == 60.0 and m["false_alarms"] == 1
    assert m["false_alarms_per_pair_hour"] == round(1 / ((3600 - 600) / 3600 * 2), 3)


class _Conn:
    """A fake TraCI connection for the camera observer: vehicles on two edges with speeds and waiting times."""
    def __init__(self, on_edge: dict, speed: dict, wait: dict | None = None):
        self.on_edge, self.speed, self.wait = on_edge, speed, wait or {}
        self.edge = type("E", (), {"getLastStepVehicleIDs": lambda _s, e: self.on_edge.get(e, [])})()
        self.vehicle = type("V", (), {"getSpeed": lambda _s, v: self.speed[v], "getWaitingTime": lambda _s, v: self.wait.get(v, 0.0)})()


def test_camera_pair_row_has_travel_time_from_the_two_sightings_and_a_stopped_count():
    """J2 (2026-10-11): a vehicle seen at cam0 at t=10 and at cam1 at t=40 gives a 30 s travel time; a vehicle under 0.1 m/s counts as stopped."""
    from core.simulation.aid import cameras as cam
    cams = [{"id": "cam0", "edge": "A", "chainage": 1367.0, "limit_kmh": 50.0}, {"id": "cam1", "edge": "B", "chainage": 1925.0, "limit_kmh": 50.0}]
    ob = cam.Observer(cams)
    ob.step(_Conn({"A": ["v1", "v2"]}, {"v1": 10.0, "v2": 0.0}, {"v2": 12.0}), 10.0)
    ob.step(_Conn({"B": ["v1"]}, {"v1": 8.0}), 40.0)
    (row,) = ob.window()
    assert row["cam_up_seen"] == 2 and row["cam_up_stopped"] == 1 and row["cam_up_wait"] == 6.0
    assert row["cam_down_seen"] == 1 and row["cam_tt_mean"] == 30.0 and row["cam_tt_n"] == 1 and row["cam_tt_missing"] == 0
    (row2,) = ob.window()                                              # an empty window: speed = the limit with the flag, travel time carried with the flag
    assert row2["cam_up_empty"] == 1 and row2["cam_up_speed"] == 50.0 and row2["cam_tt_missing"] == 1 and row2["cam_tt_prev"] == 30.0
    assert set(cam.CAM_FEATURES) <= set(row)
    assert cam.covers(cams, (1500.0, 1800.0)) and cam.covers(cams, (1200.0, 1500.0)) and not cam.covers(cams, (2100.0, 2400.0))


def test_metrics_any_and_frontier_pooling_count_detections_and_false_alarms():
    """J1 frontier: alarms during an incident window detect it; alarms outside are false, per sensor-hour; pooling sums over runs."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("aid_cli", REPO / "scripts/aid/aid.py")
    cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)
    inc = [{"actual_start_s": 1000.0, "duration_s": 200, "actual_end_s": 1200.0}, {"actual_start_s": 2000.0, "duration_s": 200, "actual_end_s": 2200.0}]
    m = cli.metrics_any([1050.0, 1500.0, 3000.0], inc, 3600)
    assert m["incidents"] == 2 and m["detected"] == 1 and m["false_alarms"] == 2 and m["time_to_detect_s_mean"] == 50.0
    assert m["false_alarms_per_pair_hour"] == round(2 / ((3600 - R.WARMUP_S) / 3600), 3)
    p = cli.pooled([m, m], 3600, [1, 1])
    assert p["incidents"] == 4 and p["detected"] == 2 and p["detection_rate"] == 0.5 and p["false_alarms"] == 4
    assert len(cli.MODEL_THRESHOLDS) >= 10 and len(cli.CAL7_GRID) > 100


def test_run_counts_a_detection_on_a_quiet_pair_as_a_false_alarm():
    """The GUI's counter: `_detected` on a pair with no active incident increments false_alarms (the closed-loop calls are stubbed)."""
    r = R.Run(1, [])
    r.active_pairs = {1}
    r.stations = [{"id": f"s{i}", "edge": f"e{i}", "segment_edges": [f"e{i}"]} for i in range(3)]
    r.share = 0.0
    r.net = type("N", (), {"getEdge": lambda _s, e: type("Ed", (), {"getShape": lambda _s2: [(0.0, 0.0)]})()})()
    c = type("C", (), {"edge": type("E", (), {"adaptTraveltime": lambda *_: None})(), "vehicle": type("V", (), {"getIDList": lambda _s: []})()})()
    from core.networking.v2x import model
    from core.simulation.twin import runtime as prt
    r._detected(c, 1000.0, 0, r.stations[0], None, model, prt)
    assert r.counts["detections"] == 1 and r.counts["false_alarms"] == 1 and r.events[-1]["false"] is True
    r._detected(c, 1000.0, 1, r.stations[1], None, model, prt)
    assert r.counts["false_alarms"] == 1 and r.counts["detections"] == 2


def test_incidentnet_files_are_unchanged_copies_and_the_runner_uses_their_protocol():
    """J3-A (2026-10-11): the five IncidentNet files carry the upstream blob hashes recorded in NOTICE; the runner takes their FIRST
    evaluate() (the file's second definition shadows it) and reproduces its arithmetic on a toy series; `make aid-incidentnet` exists."""
    import hashlib
    import json
    import importlib.util
    import re
    import sys
    tp = REPO / "third_party/incidentnet"
    want = {"LICENSE": "261eeb9e", "README.md": "aa22e537", "models/xgboost/training_scripts/xgboost_incident_detect_train.py": "73f34ac0",
            "models/xgboost/eval_scripts/xgboost_incident_detect_eval.py": "36a08100", "data_preprocessing/process_raw_data.py": "bfb0fb5a"}
    for rel, h in want.items():
        data = (tp / rel).read_bytes()
        blob = hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()           # git's blob hash, as the GitHub API reports it
        assert blob.startswith(h), rel
        assert h in (tp / "NOTICE").read_text()
    assert "Apache License" in (tp / "LICENSE").read_text()
    assert re.search(r"^aid-incidentnet:.*\n\t@PYTHONPATH=.:backend \$\(PY\) scripts/aid/incidentnet_xgb.py", (REPO / "Makefile").read_text(), re.M)
    sys.path.insert(0, str(REPO / "scripts/aid"))
    spec = importlib.util.spec_from_file_location("incidentnet_xgb", REPO / "scripts/aid/incidentnet_xgb.py")
    ix = importlib.util.module_from_spec(spec); spec.loader.exec_module(ix)
    ev = ix.their_evaluate_protocol()
    import pandas as pd

    class M:                                                                   # positive on rows 3-4 and 8 (a false alarm: no incident in the history)
        def predict(self, X):
            return [1 if X[0][0] in (3, 4, 8) else 0]
    X = pd.DataFrame({"i": range(10)}); Y = pd.Series([0, 0, 1, 1, 1, 0, 0, 0, 0, 0])
    det, fa, ttd = ev(1, X, Y, M())
    assert det == 100.0 and ttd == 1.0 and fa == 0.0                                 # row 8's positive is not false: a 1 sits in the last 1 000 history entries
    assert ix.their_layout([{"t": 30.0, **{f: 0.0 for f in ix.CAM_FEATURES}, "label_any": 1}]).columns[0] == "step"
    out = REPO / "evidence/aid/frontier/incidentnet.json"
    if out.exists():
        d = json.loads(out.read_text())
        assert d["label"].endswith("not a reproduction") and d["their_eval_entry_point_as_written"].startswith("TypeError") and d["their_way"]["repeats"] >= 1
