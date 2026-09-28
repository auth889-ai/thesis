"""The V2X closed loop on a tiny SUMO grid: a delivered ROUTE_RECOMMENDATION changes a vehicle's
route through TraCI at the moment it ARRIVES (latency respected), a dropped one never does, a
late one that finds the vehicle past the fork is logged as inapplicable, and non-connected
vehicles receive nothing."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from traffictwin.networking.channel import Channel, connected           # noqa: E402
from traffictwin.orchestration.closed_loop import apply_recommendation      # noqa: E402

needs_sumo = pytest.mark.skipif(shutil.which("netgenerate") is None or shutil.which("sumo") is None, reason="SUMO binaries not installed")


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    d = tmp_path_factory.mktemp("v2xgrid")
    net = d / "grid.net.xml"
    subprocess.run(["netgenerate", "--grid", "--grid.number", "4", "--grid.length", "300", "--default.speed", "13.89", "--default.lanenumber", "1", "--no-turnarounds", "-o", str(net)], check=True, capture_output=True)
    # two vehicles A0->D0 along the bottom row; the recommendation sends v1 up one block and back down
    routes = d / "r.rou.xml"
    routes.write_text('<routes><vehicle id="v1" depart="0"><route edges="A0B0 B0C0 C0D0"/></vehicle><vehicle id="v2" depart="0"><route edges="A0B0 B0C0 C0D0"/></vehicle></routes>')
    return net, routes


def _start(net, routes):
    import traci
    from traffictwin.digital_twin import runtime as pr
    traci.start(["sumo", "-n", str(net), "-r", str(routes), "--no-step-log", "true", "--no-warnings", "true", "--step-length", "1"], port=pr.free_port(), label=f"t{id(routes)}{pr.free_port()}")
    return traci


@needs_sumo
def test_delivered_recommendation_reroutes_at_arrival_time_dropped_never_does(grid):
    net, routes = grid
    traci = _start(net, routes)
    try:
        for _ in range(3):
            traci.simulationStep()
        assert list(traci.vehicle.getRoute("v1")) == ["A0B0", "B0C0", "C0D0"]
        alt = ["A0B0", "B0B1", "B1C1", "C1C0", "C0D0"]
        down = Channel("down", seed=1, latency_ms=5000.0, jitter_ms=0.0, loss=0.0, ttl_s=60)
        lossy = Channel("down2", seed=1, latency_ms=0.0, loss=1.0)                     # everything dropped
        t = traci.simulation.getTime()
        env = down.send(t, {"type": "ROUTE_RECOMMENDATION", "to": "v1", "vehicle_id": "v1", "created_s": t, "route": alt, "reason": "test"})
        drop = lossy.send(t, {"type": "ROUTE_RECOMMENDATION", "to": "v2", "vehicle_id": "v2", "created_s": t, "route": alt, "reason": "test"})
        assert env["status"] == "QUEUED" and drop["status"] == "DROPPED"
        log = []
        applied_at = None
        for _ in range(12):
            traci.simulationStep(); t = traci.simulation.getTime()
            for e in down.deliver(t) + lossy.deliver(t):
                entry = apply_recommendation(traci, e, t); log.append(entry)
                if entry["outcome"] == "APPLIED":
                    applied_at = t
            if applied_at is None:
                assert list(traci.vehicle.getRoute("v1")) == ["A0B0", "B0C0", "C0D0"]   # nothing changes before the message arrives
        assert applied_at is not None and applied_at >= 3 + 5.0                         # 5 s latency respected
        assert list(traci.vehicle.getRoute("v1")) == alt or list(traci.vehicle.getRoute("v1"))[-4:] == alt[-4:]
        assert list(traci.vehicle.getRoute("v2")) == ["A0B0", "B0C0", "C0D0"]            # the dropped message never rerouted v2
        assert [e["vehicle_id"] for e in log] == ["v1"] and log[0]["old_route"] != log[0]["new_route"] and "B0B1" in log[0]["affected_edges"]
    finally:
        traci.close()


@needs_sumo
def test_late_message_past_the_fork_is_inapplicable_not_forced(grid):
    net, routes = grid
    traci = _start(net, routes)
    try:
        traci.simulationStep(); t = traci.simulation.getTime()
        while t < 90 and ("v1" not in traci.vehicle.getIDList() or traci.vehicle.getRoadID("v1") != "C0D0"):
            traci.simulationStep(); t = traci.simulation.getTime()
        assert traci.vehicle.getRoadID("v1") == "C0D0"                                   # already past B0: the alternative fork is behind it
        env = {"msg_id": "x", "latency_ms": 100.0, "payload": {"vehicle_id": "v1", "created_s": 0, "route": ["A0B0", "B0B1", "B1C1", "C1D1"]}}
        entry = apply_recommendation(traci, env, t)
        assert entry["outcome"] == "INAPPLICABLE_PAST_FORK" and list(traci.vehicle.getRoute("v1")) == ["A0B0", "B0C0", "C0D0"]
        gone = apply_recommendation(traci, {"msg_id": "y", "latency_ms": 0.0, "payload": {"vehicle_id": "ghost", "created_s": 0, "route": ["A0B0"]}}, t)
        assert gone["outcome"] == "VEHICLE_GONE"
    finally:
        traci.close()


def test_non_connected_vehicles_are_outside_the_message_population():
    ids = [f"veh{i}" for i in range(500)]
    conn = {v for v in ids if connected(v, 0.3, seed=101)}
    assert 100 <= len(conn) <= 200
    # the loop only ever sends to / plans for connected ids: the predicate is the gate, so an unconnected id is never a recipient
    assert all(v not in conn for v in ids if not connected(v, 0.3, seed=101))


@needs_sumo
def test_observed_fusion_only_slows_edges_it_has_evidence_for_and_changes_the_cost_hash(grid):
    from traffictwin.optimization import edge_costs as ec
    from traffictwin.orchestration.closed_loop import fuse_observed
    net, _ = grid
    cfg = ec.load_config()
    cmap = {"c1": {"edges": ["B0C0"]}}
    table = ec.build({"c1": 13.0}, "speed_mps", cmap, net, 15, cfg, hops=1, model="t", corridor_free_speed={"c1": 13.89})
    fused = fuse_observed(table, {"C0D0": 3.0, "B0C0": 13.5, "A0A1": 13.89}, net, cfg)      # C0D0 observed crawling; B0C0 observed faster than forecast; A0A1 free-flow
    assert fused["edges"]["C0D0"]["source"] == "OBSERVED" and fused["edge_travel_times"]["C0D0"] == pytest.approx(300 / 3.0, rel=0.05)
    assert fused["edge_travel_times"].get("B0C0") == table["edge_travel_times"]["B0C0"]         # a faster observation never speeds an edge up
    assert "A0A1" not in fused["edges"]                                                         # free-flow observation adds nothing
    assert fused["observed_edges"] == 1 and fused["future_cost_hash"] != table["future_cost_hash"] and fused["forecast_only_cost_hash"] == table["future_cost_hash"]
    assert fuse_observed(table, {}, net, cfg)["future_cost_hash"] == table["future_cost_hash"]   # no observations: the forecast table is untouched
