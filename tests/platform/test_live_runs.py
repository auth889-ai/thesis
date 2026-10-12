"""Live runs (scripts/live/): the thesis checks look up exactly the saved run with the same settings, and the second views' scenario
files keep the simulators' own settings except paths and the chosen parameters."""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"live_{name}", REPO / f"scripts/live/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v2x_check_reads_the_saved_run_with_the_same_settings():
    v = load("run_v2x")
    assert v.run_dir("alert_preemption", "its_g5", 1.0, 11, 0.78) == "alert_preemption_its_g5_p100_s11_x0.78"
    m = v.saved("alert_preemption", "its_g5", 1.0, 11, "dhaka_density", 0.78)
    assert m and m["ambulance"]["travel_time_s"] == 284.0
    assert v.saved("no_alert", None, 0.0, 11, "dhaka_density", 0.78)["ambulance"]["travel_time_s"] == 292.0
    assert v.saved("alert", "its_g5", 0.33, 11, "dhaka_density", 0.78) is None          # a share the study never ran: no thesis number


def test_range_ring_is_a_circle_of_the_given_radius():
    pts = load("run_v2x").circle(10.0, 20.0, 425.0)
    assert len(pts) == 36 and all(abs(math.dist(p, (10.0, 20.0)) - 425.0) < 1e-6 for p in pts)


def test_signals_check_compares_the_study_measures():
    s = load("run_signals")
    fixed, rl = s.saved("fixed", 11, "dhaka_density", 0.78), s.saved("rl", 11, "dhaka_density", 0.78)
    assert fixed["travel_time_s"] == 292.0 and rl["travel_time_s"] == 188.0
    assert set(s.KEYS) <= set(fixed)


def test_veins_scenario_keeps_the_example_settings(tmp_path, monkeypatch):
    v = load("run_veins")
    if not (v.VEINS / "examples/veins/omnetpp.ini").exists():
        import pytest
        pytest.skip("Veins not fetched here")
    monkeypatch.setattr(v, "WORK", tmp_path)
    args = v.argparse.Namespace(mode="sos", share=0.5, txpower=10.0, seed=3, window=120, crash_node=7, crash_at=40, ambulance_at=20, makeway=100.0)
    v.scenario(args)
    ini = (tmp_path / "omnetpp.ini").read_text()
    for kept in ("*.**.nic.mac1609_4.bitrate = 6Mbps", '*.node[*].applType = "TraCIDemo11p"', "*.**.nic.phy80211p.noiseFloor = -98dBm"):
        assert kept in ini
    assert "txPower = 10mW" in ini and "penetrationRate = 0.5" in ini and "connectAt = 600s" in ini and "node[7].veinsmobility.accidentStart = 40s" in ini
    assert "rsu[" not in ini


def test_gui_mesh_target_runs_the_one_in_its_gui_with_the_legend():
    """`make gui-mesh` (2026-10-11): The ONE without its batch flag, the thesis setting by default, and a printed legend read from its sources."""
    import re
    import subprocess
    mk = (REPO / "Makefile").read_text()
    assert re.search(r"^gui-mesh:.*\n\t@\$\(PY\) scripts/live/run_mesh_one.py --legend", mk, re.M)
    src = (REPO / "scripts/live/run_mesh_one.py").read_text()
    assert '"-b", "1"] if a.no_gui else []' in src                     # the GUI is the default; -b only with --no-gui
    assert all(w in src for w in ("blue square", "green circle", "black line", "red line", "PONS", "has no GUI"))
    h = subprocess.run(["python", "scripts/live/run_mesh_one.py", "--help"], cwd=REPO, capture_output=True, text=True)
    assert "--legend" in h.stdout and "prophet" in h.stdout
    assert 'default="prophet"' in src and "default=10.0" in src and "default=1)" in src     # the thesis setting: PRoPHET, 10 m, seed 1


def test_gui_veins_colours_are_a_parameter_of_our_app_off_by_default(tmp_path, monkeypatch):
    """`make gui-veins` (2026-10-11): `--gui-colours` sets our app's `guiColours` in the generated ini; without it Veins's colours stay."""
    import re
    v = load("run_veins")
    if not (v.VEINS / "examples/veins/omnetpp.ini").exists():
        import pytest
        pytest.skip("Veins not fetched here")
    monkeypatch.setattr(v, "WORK", tmp_path)
    base = dict(mode="v2x", share=1.0, txpower=20.0, seed=0, window=120, crash_node=10, crash_at=60, ambulance_at=20, makeway=100.0)
    v.scenario(v.argparse.Namespace(**base, gui_colours=True))
    assert "*.node[*].appl.guiColours = true" in (tmp_path / "omnetpp.ini").read_text()
    v.scenario(v.argparse.Namespace(**base))
    assert "*.node[*].appl.guiColours = false" in (tmp_path / "omnetpp.ini").read_text()
    ned = (REPO / "research/veins_dhaka/src/AmbulanceAlert11p.ned").read_text()
    assert "bool guiColours = default(false)" in ned
    assert re.search(r"^gui-veins:.*\n\t@\$\(PY\) scripts/live/run_veins.py v2x --sumo-gui --gui-colours", (REPO / "Makefile").read_text(), re.M)


def test_run_sos_collide_is_a_flag_with_sumo_detecting_the_contact():
    """`make run-sos-collide` (2026-10-11): a real collision inside SUMO behind `--collide` (off by default); SUMO's own collision list
    and collision-output are the trigger and the record; the difference from Veins's TraCIDemo11p is printed."""
    import json
    import re
    src = (REPO / "scripts/live/run_sos_v2v.py").read_text()
    assert re.search(r"^run-sos-collide:.*\n\t@\$\(PY\) scripts/live/run_sos_v2v.py --collide --gui-colours", (REPO / "Makefile").read_text(), re.M)
    assert '"--collision.action", "warn"' in src and '"--collision-output"' in src and "getCollidingVehiclesIDList" in src
    assert "setSpeedMode(v, 0)" in src and 'collide = bool(getattr(a, "collide", False))' in src          # off unless asked
    assert "TraCIDemo11p.cc" in src and all(f"\n    {i}." in src for i in range(1, 6))
    last = REPO / "evidence/live_runs/sos_v2v/last_run.json"
    if last.exists():
        d = json.loads(last.read_text())
        if d.get("args", {}).get("collide"):
            col = d["with_warning"]["collision"]
            assert col and col["rammer"] in col["vehicles"] and col["sumo_collision_output"][0]["type"] == "collision"


def test_make_demo_lists_the_nine_live_parts_in_the_talk_order():
    """`make demo` (step F, 2026-10-11): one command, a part per Enter; --list prints the parts without starting anything."""
    import re
    import subprocess
    assert re.search(r"^demo:.*\n\t@\$\(PY\) scripts/live/demo.py", (REPO / "Makefile").read_text(), re.M)
    out = subprocess.run(["python", "scripts/live/demo.py", "--list"], cwd=REPO, capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}).stdout
    keys = [line.split()[0] for line in out.strip().splitlines() if line.strip()]
    assert keys == ["v2x", "veins", "signals", "twin", "mesh", "collide", "aid", "model-lab", "map"]
    assert "run-sos-collide" in out and "aid-gui" in out and "gui-mesh" in out and "gui-veins" in out and "demo-forecast" not in out


def test_make_demo_watch_text_reads_the_v2x_numbers_from_the_saved_rq2_metrics():
    """Hardcode audit fix (owner, 2026-10-11): part 1's "a s -> b s" comes from results/emergency/dhaka/rq2 metrics.json (key
    ambulance.travel_time_s) for `make run-v2x`'s default settings, through run_v2x.saved; no travel time is typed into demo.py."""
    import json
    import re
    import sys
    sys.path.insert(0, str(REPO / "scripts/live"))
    import demo
    import run_v2x
    demand, scale = run_v2x.LEVELS["dhaka"]
    p0 = run_v2x.SAVED / "runs" / run_v2x.CITY / demand / run_v2x.run_dir("no_alert", None, 0.0, demo.V2X_SEED, scale) / "metrics.json"
    p1 = run_v2x.SAVED / "runs_v2" / run_v2x.CITY / demand / run_v2x.run_dir("alert_preemption", "its_g5", 1.0, demo.V2X_SEED, scale) / "metrics.json"
    assert p0.exists() and p1.exists()
    t0, t1 = json.loads(p0.read_text())["ambulance"]["travel_time_s"], json.loads(p1.read_text())["ambulance"]["travel_time_s"]
    watch = demo.PARTS[0][3]
    assert f"(seed {demo.V2X_SEED}, {t0:g} s -> {t1:g} s)" in watch
    src = (REPO / "scripts/live/demo.py").read_text()
    assert not re.search(rf"\b{t0:g}\b|\b{t1:g}\b", src), "a travel time is typed into demo.py"


def test_run_routing_quick_checks_each_seed_arm_against_the_saved_rq2_report():
    """`make run-routing-quick` (step L, 2026-10-11): the saved run's settings, and an exact per-seed/arm comparison on the study's measures."""
    import json
    import re
    rq = load("run_routing_quick")
    assert re.search(r"^run-routing-quick:.*\n\t@PYTHONPATH=.:backend \$\(PY\) scripts/live/run_routing_quick.py", (REPO / "Makefile").read_text(), re.M)
    saved = json.loads((rq.SAVED / "report.json").read_text())
    proto = saved["protocol"]                                           # the saved run's own protocol block
    assert proto["city_id"] == rq.SETTINGS["city"] and proto["profile"] == rq.SETTINGS["profile"]
    for k in ("demand_scale", "demand_profile", "od_rule"):
        assert proto[k] == rq.SETTINGS[k], k
    assert "fork1200" in rq.SAVED.name and rq.SETTINGS["fork_t0"] == 1200 and "x8_peak_arterial" in rq.SAVED.name
    rows = rq.check(saved, saved)                                       # the saved run against itself reproduces exactly
    assert rows and all(r["check"] == "REPRODUCED exactly" for r in rows)
    tweaked = json.loads(json.dumps(saved))
    arm = next(iter(tweaked["per_seed"][0]["arms"]))
    tweaked["per_seed"][0]["arms"][arm]["metrics"]["arrived"] += 1
    assert rq.check(tweaked, saved)[0]["check"] == "DIFFERENT"


def test_sweep_v2x_covers_the_five_shares_and_treats_share_zero_as_no_alert():
    """`make sweep-v2x` (step I, 2026-10-11): shares 0/25/50/75/100 %, share 0 = the siren-only run, runs kept under evidence/sweeps/."""
    import re
    sw = load("sweep_v2x")
    assert re.search(r"^sweep-v2x:.*\n\t@PYTHONPATH=.:backend \$\(PY\) scripts/live/sweep_v2x.py", (REPO / "Makefile").read_text(), re.M)
    assert sw.SHARES == (0.0, 0.25, 0.5, 0.75, 1.0)
    assert sw.OUT == REPO / "evidence/sweeps"
    src = (REPO / "scripts/live/sweep_v2x.py").read_text()
    assert '("no_alert", None, 0.0) if share == 0' in src and "rv.saved(" in src and 'root=OUT / "runs"' in src


def test_run_twin_target_opens_the_live_twin_page_without_a_simulation_here():
    """`make run-twin` (step E, 2026-10-11): starts the app server if needed and opens /app/lab/live-twin; nothing else runs."""
    import re
    assert re.search(r"^run-twin:.*\n\t@\$\(PY\) scripts/live/run_twin.py", (REPO / "Makefile").read_text(), re.M)
    src = (REPO / "scripts/live/run_twin.py").read_text()
    assert 'present.LOCAL + "app/lab/live-twin"' in src and "present.start_server(" in src and "traci" not in src


class _TL:
    """A fake TraCI for the Max-Pressure controller: one junction, two green phases, links from edges A and B."""
    def __init__(self, halting):
        self.halting = halting
        P = type("P", (), {})
        ph = []
        for state in ("GGrr", "yyrr", "rrGG", "rryy"):
            p = P(); p.state = state; ph.append(p)
        logic = type("L", (), {})(); logic.phases = ph
        self.trafficlight = type("T", (), {"getAllProgramLogics": lambda _s, t: [logic], "getControlledLinks": lambda _s, t: [[("A_0", "X_0", "")], [("A_1", "X_1", "")], [("B_0", "Y_0", "")], [("B_1", "Y_1", "")]],
                                           "getPhase": lambda _s, t: 0, "setPhase": lambda *_: None, "setPhaseDuration": lambda *_: None})()
        self.lane = type("La", (), {"getLastStepHaltingNumber": lambda _s, l: self.halting.get(l, 0)})()


def test_max_pressure_ev_prefers_the_ambulance_approach_until_released():
    """Step S (2026-10-11): without priority the busier approach (B) wins the pressure; with a preference for edge A, phase 0 is chosen; release restores."""
    from core.simulation.ambulance import mp_signals
    c = mp_signals.MaxPressureEV(_TL({"A_0": 1, "B_0": 6, "B_1": 5}), ["j"])
    assert c.choose("j") == 2
    c.prefer("j", "A")
    assert c.priority == {"j": 0} and c.requests == 1 and c.choose("j") == 0
    c.prefer("j", "A")                                                  # a second call while active is not a new request
    assert c.requests == 1
    c.release("j")
    assert c.choose("j") == 2 and c.green_phase_for("j", "B") == 2 and c.green_phase_for("j", "Z") is None


def test_run_signals_controller_flag_defaults_to_rl_and_compare_target_exists():
    import re
    rs = load("run_signals")
    a = rs.main.__globals__["argparse"].ArgumentParser()
    assert "--controller" in (REPO / "scripts/live/run_signals.py").read_text()
    src = (REPO / "scripts/live/run_signals.py").read_text()
    assert 'choices=["rl", "maxpressure", "maxpressure_ev"], default="rl"' in src
    assert re.search(r"^compare-signals:.*\n\t@PYTHONPATH=.:backend \$\(PY\) scripts/live/compare_signals.py", (REPO / "Makefile").read_text(), re.M)
    m = rs.measures({"ambulance": {"travel_time_s": 1.0}, "why": {"queue_at_signals": 2, "blocked_s": 3, "queue_peaks": []}, "others": {"total_vehicle_hours": 4.0, "mean_time_loss_s": 5.0}})
    assert m["mean_time_loss_s"] == 5.0 and m["travel_time_s"] == 1.0 and m["ev_priority_requests"] is None
    cs = load("compare_signals")
    assert cs.ARMS == ("fixed", "rl", "maxpressure", "maxpressure_ev") and cs.OUT == REPO / "evidence/signals/controllers"


def test_sweep_mesh_parks_absent_phones_out_of_range_and_knows_maxprop(tmp_path):
    """Step P (2026-10-11): phones ranked by presence; an absent phone is parked outside the map, 50 m from the next parked one."""
    import re
    sm = load("sweep_mesh")
    assert sm.ROUTER["maxprop"] == "MaxPropRouter" and set(sm.ROUTER) == {"epidemic", "spray_and_wait", "prophet", "maxprop"}
    assert re.search(r"^sweep-mesh:.*\n\t@\$\(PY\) scripts/live/sweep_mesh.py", (REPO / "Makefile").read_text(), re.M)
    times = [900.0, 901.0, 902.0]
    pos = {"veh1": {900.0: (10.0, 10.0), 901.0: (11.0, 10.0), 902.0: (12.0, 10.0)}, "veh2": {901.0: (50.0, 60.0)}, "veh3": {900.0: (0.0, 0.0), 902.0: (1.0, 1.0)}}
    assert sm.rank(pos) == ["veh1", "veh3", "veh2"]
    info = sm.movement(tmp_path / "m.txt", times, pos, ["veh1", "veh2"])
    lines = (tmp_path / "m.txt").read_text().splitlines()
    assert lines[0].startswith("900.0 902.0 0 ") and len(lines) == 1 + 3 * 2
    parked = [l for l in lines[1:] if l.startswith("900.0 1 ") or l.startswith("902.0 1 ")]
    assert len(parked) == 2 and all(l.split()[2] == "50.00" and float(l.split()[3]) > 200 for l in parked)
    assert info["present_full_window"] == 1 and info["presence_s_min"] == 1


def test_sweep_mesh_range_sweep_is_a_flag_with_the_four_ranges():
    """P2 (2026-10-11): --range-sweep, Epidemic, 10/30/50/100 m, evidence/mesh/range/; the default sweep is unchanged."""
    sm = load("sweep_mesh")
    assert sm.RANGES_M == (10.0, 30.0, 50.0, 100.0) and sm.RANGE_OUT == REPO / "evidence/mesh/range"
    src = (REPO / "scripts/live/sweep_mesh.py").read_text()
    assert '"--range-sweep", action="store_true"' in src and 'router = "epidemic"' in src


def test_sweep_sos_pairs_every_warning_run_with_its_no_warning_twin_and_uses_a_censored_mean():
    """`make sweep-sos` (step Q1, 2026-10-11): shares 25-100 %, crash at 600/900 s, one twin per (seed, crash time); the headline is the
    mean over ALL affected cars with a non-arrival at the horizon, so a warning that strands cars cannot look good; the saved live run's
    cell is checked, not a thesis number (none exists)."""
    import json
    import re
    import sys
    assert re.search(r"^sweep-sos:.*\n\t@PYTHONPATH=.:backend \$\(PY\) scripts/live/sweep_sos.py", (REPO / "Makefile").read_text(), re.M)
    sys.path.insert(0, str(REPO / "scripts/live"))
    import sweep_sos as ss
    assert ss.SHARES == (0.25, 0.5, 0.75, 1.0) and ss.CRASH_AT == (600.0, 900.0) and ss.AFTER == 600.0
    assert ss.censored_mean(10, 10, 100.0) == 100.0 and ss.censored_mean(10, 5, 100.0) == 350.0 and ss.censored_mean(0, 0, None) is None
    rows = [{"seed": 11, "share": 0.5, "crash_at": 600.0, "tech": "its_g5", "warn": True, "crashed": "v1", "affected": 10, "affected_arrived": 8, "affected_mean_s_to_arrive": 200.0,
             "censored_mean_s": ss.censored_mean(10, 8, 200.0), "warned": 5, "rerouted": 2, "delivery_in_range": 0.9},
            {"seed": 11, "share": 0.0, "crash_at": 600.0, "tech": "", "warn": False, "crashed": "v1", "affected": 10, "affected_arrived": 6, "affected_mean_s_to_arrive": 150.0,
             "censored_mean_s": ss.censored_mean(10, 6, 150.0), "warned": 0, "rerouted": 0, "delivery_in_range": None}]
    p = ss.pair(rows)
    assert len(p) == 1 and p[0]["arrivals_gained"] == 2 and p[0]["saved_s"] == -50.0 and p[0]["saved_censored_s"] == 50.0 and p[0]["same_crash"] is True
    sm = ss.summary(p)
    assert sm[0]["saved_censored_s_median"] == 50.0 and sm[0]["saved_s_median"] == -50.0 and sm[0]["arrivals_gained_mean"] == 2.0 and sm[0]["censored_slower_runs"] == 0
    out = REPO / "evidence/sos/sweep/sweep.json"
    if out.exists():
        d = json.loads(out.read_text())
        assert d["thesis_number"] is None and d["rule_reproduced"] and d["saved_live_run_check"].startswith("REPRODUCED")
        assert len(d["twins"]) == len(d["seeds"]) * len(d["crash_at"]) and len(d["rows"]) == len(d["twins"]) * len(d["shares"])


def test_present_runs_a_real_collision_and_replays_its_trace_in_the_graph_step():
    """R1 (2026-10-11): present step 2 is the SUMO collision run (--collide) and step 7 replays `sumo_collision`, the trace that run built from
    SUMO's own collision record (collisions.xml colliderSpeed / victimSpeed); the graph script refuses to run without that file."""
    import hashlib
    import json
    import re
    import sys
    sys.path.insert(0, str(REPO / "scripts/live"))
    import present
    steps = {s[0]: s[2] for s in present.STEPS}
    assert "--collide" in steps["sos"] and "--trace=sumo_collision" in steps["graph"]
    src = (REPO / "scripts/live/run_sos_v2v.py").read_text()
    assert "sos.from_collision(float(rec[\"colliderSpeed\"]), float(rec[\"victimSpeed\"])" in src and "sos.write_collision_trace(tr)" in src
    graph = (REPO / "frontend/tests/live/sos_graph.cjs").read_text()
    assert "collision_trace.json" in graph and "process.exit(2)" in graph and "data-trace=" in graph
    assert re.search(r"data-trace=\{k\}", (REPO / "frontend/src/features/emergency/SosCard.tsx").read_text())
    last = REPO / "evidence/live_runs/sos_v2v/last_run.json"
    trace = REPO / "evidence/live_runs/sos_v2v/collision_trace.json"
    if last.exists() and json.loads(last.read_text()).get("collision_trace"):
        from core.safety import sos
        note = json.loads(last.read_text())["collision_trace"]
        assert trace.exists() and hashlib.sha256(trace.read_bytes()).hexdigest() == note["sha256"]
        tr = json.loads(trace.read_text())
        assert tr["kind"] == "sumo_collision" and sos.detect(tr["samples"])["detected"] == note["detected"]
        rec = tr["collision"]["source"]["record"]
        assert tr["collision"]["closing_speed_mps"] == round(abs(float(rec["colliderSpeed"]) - float(rec["victimSpeed"])), 3)


def test_run_v2x_live_inputs_seed_from_the_clock_demand_from_the_data_and_a_route_by_edge_ids():
    """2026-10-12 (live demo input): the Dhaka scale is read from corridor.match's file, the recorded counts are summed from the
    calibration file, a route may be two edge ids or random (drawn by the seed), and a chosen route never lands in a study folder."""
    import json
    from core.simulation.ambulance import service
    v = load("run_v2x")
    match = json.loads((REPO / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())
    assert v.LEVELS["dhaka"] == ("dhaka_density", match["chosen_scale"]) and v.dhaka_scale() == 0.78    # the saved study's level, unchanged
    counts = v.recorded_counts()
    cal = json.loads((REPO / "evidence/ambulance_rq2/dhaka_density/calibration.json").read_text())
    assert {k: c["vehicles_per_hour"] for k, c in counts.items()} == {s["site"]: sum(s["counts"]) for s in cal["sites"]}
    assert v.DEMANDS == ("current", "dhatrax-peak")
    a, b = service.random_route("dhaka", "dhaka_density", 7)
    assert (a, b) == service.random_route("dhaka", "dhaka_density", 7) and a != b             # drawn by the seed
    sc = service.scenario("dhaka", "dhaka_density", (a, b))
    assert sc["edges"][0] == a and sc["edges"][-1] == b and sc["length_m"] >= 1500 and sc["route_given"] == [a, b]
    base = service.scenario("dhaka", "dhaka_density")
    assert base["route_given"] is None and base["edges"] != sc["edges"]                       # the thesis trip is untouched
    import pytest
    with pytest.raises(service.Refused):
        service.scenario("dhaka", "dhaka_density", ("no_such_edge", b))
    tag = v.route_tag((a, b))
    assert tag.startswith("r") and len(tag) == 9 and v.run_dir("alert", "its_g5", 1.0, 5, 1.0, tag) == f"alert_its_g5_p100_s5_{tag}"
    assert v.run_dir("alert_preemption", "its_g5", 1.0, 11, 0.78) == "alert_preemption_its_g5_p100_s11_x0.78"   # no tag: as before
    assert "--seed" in open(REPO / "Makefile").read().split("run-v2x-live:")[1].split("\n")[1] and "--from" in open(REPO / "Makefile").read().split("run-v2x-live:")[1].split("\n")[1]
    assert "rerouted 0" not in (REPO / "scripts/live/run_v2x.py").read_text()                 # no literal shown as a live count


def test_web_v2x_job_accepts_demand_and_route_and_keeps_the_thesis_defaults():
    import pytest
    from core.simulation.live_jobs import jobs
    d = jobs.validate("v2x", {})
    assert "demand" not in d and "from" not in d and d["seed"] == 11                          # defaults: exactly the thesis run's parameters
    p = jobs.validate("v2x", {"demand": "dhatrax-peak", "from": "random", "to": "1478491311#0", "seed": 5})
    assert (p["demand"], p["from"], p["to"]) == ("dhatrax-peak", "random", "1478491311#0")
    for bad in ({"demand": "peak"}, {"from": "random"}, {"from": "a b", "to": "random"}, {"demand": "dhatrax-peak", "level": "x2"}):
        with pytest.raises(ValueError):
            jobs.validate("v2x", bad)
