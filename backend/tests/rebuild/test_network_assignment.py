"""The network-level assigner: diverse candidates really are diverse, background load raises the
marginal cost, route-capacity admission stops assignments, and the opportunity gate refuses vehicles
without a real alternative."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from core.simulation.routing import edge_costs as ec                   # noqa: E402
from core.simulation.routing import route_optimizer as ro              # noqa: E402
from core.simulation.routing import network_assignment as na               # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("netgenerate") is None or shutil.which("duarouter") is None, reason="SUMO binaries not installed")


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    d = tmp_path_factory.mktemp("na"); net = d / "g.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", "5", "--grid.length", "400", "--default.speed", "13.89", "--default.lanenumber", "1", "--no-turnarounds", "-o", str(net)], check=True, capture_output=True)
    return net


def _cc(**over):
    cc = {"candidates": {"diverse": True, "max_overlap": 0.6, "penalty_factor": 1.5, "penalty_rounds": 4}, "assignment": {"background_load": True, "route_capacity": True, "max_route_utilisation": 0.9}}
    for k, v in over.items():
        sect, key = k.split("__"); cc[sect][key] = v
    return cc


@needs_sumo
def test_diverse_candidates_respect_the_overlap_bound(grid, tmp_path):
    info = ro.NetInfo(grid); cfg = ec.load_config()
    trips = [{"id": "v1", "from": "A0B0", "to": "D4E4", "depart": 0.0, "current_route": None}]
    # the current route: duarouter's free-flow path
    trips[0]["current_route"] = ro.duarouter_routes(grid, ro.write_trips(trips, tmp_path / "t.xml"), tmp_path / "s.rou.xml", None, 1)["v1"]
    table = {"edge_travel_times": {}, "model": "t", "horizon_min": 15, "coverage_hops": 0, "analysis_run_id": None, "future_cost_hash": "x"}
    cands, gen = na.diverse_candidates(grid, trips, table, tmp_path / "div", cfg, _cc(), 1, info)
    routes = cands["v1"]
    assert len(routes) >= 3, gen
    for i, a in enumerate(routes):
        for b in routes[:i]:
            assert not (na.overlap(a, b, info.length) > 0.6 and na.overlap(b, a, info.length) > 0.6)     # no pair is a cosmetic variant
    assert all(r[0] == "A0B0" and r[-1] == "D4E4" for r in routes)


@needs_sumo
def test_background_load_raises_marginal_cost_and_capacity_admission_stops_assignment(grid):
    info = ro.NetInfo(grid); cfg = ec.load_config()
    cur = ["A0B0", "B0C0", "C0D0", "D0E0"]; alt = ["A0B0", "B0B1", "B1C1", "C1D1", "D1E1", "E1E0"] if "E1E0" in info.length else ["A0B0", "B0B1", "B1C1", "C1D1", "D1D0", "D0E0"]
    slow = {e: 200.0 for e in ("B0C0", "C0D0")}                                # the current route is predicted to crawl
    empty = na.NetworkAssigner(cfg, _cc(), info, 900.0, None, slow)
    loaded = na.NetworkAssigner(cfg, _cc(), info, 900.0, {f"bg{i}": alt for i in range(420)}, slow)   # 420 vehicles already heading down the alternative (capacity 450 per 15-min window per lane)
    assert loaded.marginal(alt) > empty.marginal(alt) * 1.3                      # marginal cost sees the background load
    d = empty.assign("v1", cur, [alt], None, 0.0, 300.0)
    assert d["decision"] == "REROUTE" and d["utilisation_after"] <= 0.9
    d2 = loaded.assign("v1", cur, [alt], None, 0.0, 300.0)
    assert d2["decision"] in ("REJECTED_ROUTE_CAPACITY", "NO_REAL_ALTERNATIVE") and d2["selected"] == "v1_c0"   # saturated alternative: not assigned
    assert loaded.diagnostics()["rejected"]


@needs_sumo
def test_vehicle_without_a_real_alternative_is_never_rerouted(grid):
    info = ro.NetInfo(grid); cfg = ec.load_config()
    cur = ["A0B0", "B0C0", "C0D0", "D0E0"]; near = ["A0B0", "B0C0", "C0D0", "D0D1", "D1E1", "E1E0"] if "E1E0" in info.length else ["A0B0", "B0C0", "C0D0", "D0E0"]
    asg = na.NetworkAssigner(cfg, _cc(candidates__max_overlap=0.4), info, 900.0, None, {"D0E0": 500.0})   # the detour shares half its length with the current route
    d = asg.assign("v1", cur, [near], None, 0.0, 300.0)
    assert d["decision"] in ("NO_REAL_ALTERNATIVE", "KEEP_CURRENT_BELOW_THRESHOLD")                 # overlap with the current route is above the bound
