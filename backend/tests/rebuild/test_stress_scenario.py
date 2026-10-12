"""Congested-scenario machinery: the phased demand profile really shapes departures, the selection rule is
applied as written, and the oracle-first gate cannot pass without a BETTER label."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from core.simulation.closed_loop.control import closed_loop as cl            # noqa: E402
from research.networking import traffic_stress_sweep as ss           # noqa: E402
from core.simulation.closed_loop.protocols import stress_experiment as se      # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("netgenerate") is None, reason="SUMO binaries not installed")


@needs_sumo
def test_peak_profile_shapes_departures_and_scale_multiplies_them(tmp_path, monkeypatch):
    net = tmp_path / "g.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", "6", "--grid.length", "300", "--default.speed", "13.89", "--no-turnarounds", "-o", str(net)], check=True, capture_output=True)
    scen = tmp_path / "scen"; scen.mkdir()
    (scen / "MANIFEST.json").write_text(json.dumps({"process": {"randomtrips_options": ["-n", "x", "-o", "x", "-r", "x", "-b", "0", "-e", "1800", "-p", "2.0", "--seed", "1", "--prefix", "veh", "--min-distance", "300", "--vehicle-class", "passenger", "--vclass", "passenger", "--validate"]}}))
    monkeypatch.setattr(cl, "scenario_dir", lambda city: scen)
    P = {"city_id": "grid", "network": str(net.relative_to(REPO)) if str(net).startswith(str(REPO)) else str(net)}
    monkeypatch.setattr(cl, "REPO", Path("/") if not str(net).startswith(str(REPO)) else REPO)
    r1, d1 = cl.demand_for_seed({**P, "demand_scale": 1.0, "demand_profile": "uniform"}, 7, tmp_path / "u1")
    r2, d2 = cl.demand_for_seed({**P, "demand_scale": 2.0, "demand_profile": "uniform"}, 7, tmp_path / "u2")
    rp, dp = cl.demand_for_seed({**P, "demand_scale": 1.0, "demand_profile": "peak"}, 7, tmp_path / "pk")
    assert 1.8 * d1["vehicles"] <= d2["vehicles"] <= 2.2 * d1["vehicles"]                       # the multiplier multiplies
    deps = [float(x) for x in re.findall(r'<vehicle [^>]*depart="([0-9.]+)"', rp.read_text())]
    assert deps == sorted(deps) and deps[-1] > 2400                                            # merged file sorted, phases cover the hour
    rate = lambda a, b: sum(1 for d in deps if a <= d < b) / (b - a)
    assert rate(0, 600) < rate(600, 1500) < rate(1500, 2400)                                    # normal < rising < bottleneck phase
    assert abs(rate(2400, 3600) - rate(1500, 2400)) / rate(1500, 2400) < 0.25                   # peak phase at the calibrated level
    assert dp["demand_profile"] == "peak" and dp["profile_phases"] == cl.PROFILES_DEMAND["peak"]
    txt = rp.read_text(); types = set(re.findall(r'<vType id="([^"]+)"', txt)); used = set(re.findall(r'<vehicle [^>]*type="([^"]+)"', txt))
    assert used and used <= types                                                            # every segment's vType is merged (SUMO refuses unknown types)


def _rep(**over):
    c = {"busiest_interval_utilisation": {"p50": 0.2, "p90": 0.6, "max": 1.1, "share_ge_0.5": 0.3, "share_ge_0.7": 0.15, "share_ge_0.9": 0.05}, "mean_occupancy_pct_major": 12.0, "spillback_major_edges_occ_ge_80": 3, "max_halting_vehicles": 400, "max_running_vehicles": 2000,
         "mean_speed_mps": 6.0, "loaded_mean_speed_mps": 6.0, "loaded_min_speed_mps": 4.0, "loaded_mean_halting_share": 0.4, "loaded_max_halting_share": 0.6, "teleport_reasons": {"total": 2, "jam": 2, "yield": 0, "wrongLane": 0}}
    m = {"inserted": 1000, "arrived": 950, "teleports": 2, "mean_travel_time_all": 900.0, "p95_travel_time_s": 1800.0, "total_waiting_s": 5e4, "mean_queue_veh": 50.0, "total_vehicle_hours_incl_never_inserted": 300.0, "congestion": c}
    for k, v in over.items():
        (c if k in c else m)[k] = v
    return {"per_seed": [{"seed": 101, "demand": {"vehicles": 1000}, "arms": {"baseline": {"metrics": m}}}]}


def test_selection_rule_is_applied_as_written():
    ev = ss.evaluate(_rep(), speed_1x=10.0, tt_1x=600.0)
    assert ev["STABLE"] and ev["CONGESTED"] and ev["CONGESTED_v1"] and ev["mean"]["tti"] == 1.5 and ev["mean"]["loaded_speed_ratio_to_1x"] == 0.6
    assert not ss.evaluate(_rep(teleports=50), speed_1x=10.0, tt_1x=600.0)["STABLE"]                    # 5 % teleports: unstable
    assert not ss.evaluate(_rep(arrived=700), speed_1x=10.0, tt_1x=600.0)["STABLE"]                     # 70 % arrive: unstable
    assert not ss.evaluate(_rep(loaded_min_speed_mps=1.0), speed_1x=10.0, tt_1x=600.0)["STABLE"]        # gridlock
    assert not ss.evaluate(_rep(), speed_1x=10.0, tt_1x=750.0)["CONGESTED"]                             # TTI 1.2 < 1.3: not congested
    assert not ss.evaluate(_rep(teleport_reasons={"total": 1, "jam": 0, "yield": 1}), speed_1x=10.0, tt_1x=600.0)["CONGESTED"]   # no standing jam anywhere
    assert not ss.evaluate(_rep(), speed_1x=None, tt_1x=None)["CONGESTED"]                              # no 1x reference → cannot be declared congested
    assert not ss.evaluate(_rep(), speed_1x=7.0, tt_1x=600.0)["CONGESTED_v1"]                           # v1 kept for the record


def test_oracle_gate_needs_a_helped_label_not_a_negative_mean():
    key = se.KEY
    passed = se.oracle_gate({"paired": {"oracle_v2x_vs_reactive": {key: {"mean_pct": -3.1, "ci95": [-5.0, -1.2], "label": "HELPED"}}}})
    inconclusive = se.oracle_gate({"paired": {"oracle_v2x_vs_reactive": {key: {"mean_pct": -3.1, "ci95": [-7.0, 0.8], "label": "INCONCLUSIVE"}}}})
    worse = se.oracle_gate({"paired": {"oracle_v2x_vs_reactive": {key: {"mean_pct": 0.4, "ci95": [0.1, 0.7], "label": "HURT"}}}})
    assert passed["status"] == "PASSED" and inconclusive["status"] == "FAILED" and worse["status"] == "FAILED"
    assert se.oracle_gate({"paired": {}})["status"] == "FAILED"


def test_learned_stage_is_refused_without_a_passed_development_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(se, "REPO", tmp_path)
    (tmp_path / "core/simulation/closed_loop/protocols").mkdir(parents=True)
    (tmp_path / "core/simulation/closed_loop/protocols/controller_config.json").write_text(json.dumps({"stress_scenario": {"c:uniform:arterial": {"chosen_scale": 4.0, "gate": "VALID_TRAFFIC_STRESS_CASE"}}}))
    monkeypatch.setattr(sys, "argv", ["x", "--scenario", "A", "--stage", "learned", "--city", "c", "--od-rule", "arterial"])
    with pytest.raises(SystemExit) as e:
        se.main()
    assert "refused" in str(e.value)
    (tmp_path / "core/simulation/closed_loop/protocols/controller_config.json").write_text(json.dumps({"stress_scenario": {"c:uniform:arterial": {"chosen_scale": 2.0, "gate": "STRESS_GATE_FAILED"}}}))
    monkeypatch.setattr(sys, "argv", ["x", "--scenario", "A", "--stage", "oracle", "--city", "c", "--od-rule", "arterial"])
    with pytest.raises(SystemExit) as e:
        se.main()
    assert "REJECTED" in str(e.value)                                                             # a rejected stress scenario is not run
