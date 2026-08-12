"""Platform conformance tests.

Two things are proven here:
 1. the shared types enforce their own invariants (units, provenance, fairness);
 2. a FOREIGN implementation that never imports our base classes still satisfies
    the protocols — which is the whole point of using structural typing, since
    official paper repos (RT-DETR, ByteTrack, PressLight, CoLight, MAPPO, DCRNN…)
    will be wrapped by adapters, not rewritten.

No algorithm is implemented or tested here; these are contract tests.
"""
from __future__ import annotations

import pytest

from dhakaflow.common.registry import available, build, clear, register
from dhakaflow.common.provenance import RunProvenance
from dhakaflow.common.types import (LaneState, TrafficMetrics, TrafficObservation,
                                    TrafficScenario, VehicleClass)
from dhakaflow.common.units import (flow_per_interval_to_vph, kmh_to_ms,
                                    percent_to_fraction, speed_from_flow_density)
from dhakaflow.control.interfaces import (SignalAction, SignalActionType, TrafficController)
from dhakaflow.evaluation.interfaces import ArmSetup, BenchmarkSpec
from dhakaflow.evaluation.traffic_science import (CriticalPoint, MFDPoint,
                                                  distance_to_critical, network_speed)
from dhakaflow.genai.interfaces import CopilotAnswer, Evidence
from dhakaflow.perception.interfaces import BoundingBox, Detection, Detector
from dhakaflow.routing.interfaces import RouteDecision
from dhakaflow.safety.interfaces import SafetyConstraints
from dhakaflow.simulation.interfaces import SimulationBackend
from dhakaflow.visualization.interfaces import FigureSpec


# --------------------------------------------------------------------- units
def test_units_roundtrip_and_conversions():
    assert kmh_to_ms(36.0) == pytest.approx(10.0)
    assert percent_to_fraction(42.0) == pytest.approx(0.42)
    assert flow_per_interval_to_vph(25, 300) == pytest.approx(300.0)
    assert speed_from_flow_density(1000.0, 50.0) == pytest.approx(20.0)


def test_speed_undefined_at_zero_density_raises_not_returns_zero():
    with pytest.raises(ValueError):
        speed_from_flow_density(1000.0, 0.0)


# ------------------------------------------------------------- core datatypes
def test_scenario_validates_and_exposes_evaluation_window():
    s = TrafficScenario(scenario_id="dhaka_smoke", network_path="n.net.xml",
                        begin_s=0, end_s=3600, warmup_s=600)
    assert s.evaluation_window_s == (600.0, 3600.0)
    with pytest.raises(ValueError):
        TrafficScenario(scenario_id="bad", network_path="n", begin_s=100, end_s=50)
    with pytest.raises(ValueError):
        TrafficScenario(scenario_id="bad", network_path="n", end_s=100, warmup_s=100)


def test_observation_aggregates_queues():
    obs = TrafficObservation(
        time_s=10.0,
        lanes={"a_0": LaneState("a_0", queue_length_veh=3),
               "b_0": LaneState("b_0", queue_length_veh=4.5)},
        source="sumo")
    assert obs.queue_total() == pytest.approx(7.5)
    assert [l.lane_id for l in obs.lanes_of(["b_0", "missing"])] == ["b_0"]


def test_metrics_missing_values_stay_none_and_cleanliness_is_explicit():
    m = TrafficMetrics(scenario_id="s", seed=1, throughput_veh=100)
    assert m.avg_travel_time_s is None      # never silently 0
    assert m.is_clean()
    assert not TrafficMetrics(scenario_id="s", seed=1, collisions=1).is_clean()


# ------------------------------------------------------ Lab 00 traffic science
def test_critical_point_speed_and_congestion_state():
    cp = CriticalPoint(critical_density=31.9, critical_flow=1104.0, interior_maximum=False)
    assert cp.critical_speed == pytest.approx(34.6, abs=0.1)   # cf. Lab 00 torino
    assert cp.congestion_state(20.0) == "free_flow"
    assert cp.congestion_state(40.0) == "congested"
    assert distance_to_critical(40.0, cp) == pytest.approx(8.1)


def test_jam_ratio_check_and_unknown_jam_is_not_a_failure():
    assert CriticalPoint(30.0, 1000.0, jam_density=600.0).sanity_check_vs_jam()
    assert not CriticalPoint(300.0, 1000.0, jam_density=600.0).sanity_check_vs_jam()
    assert CriticalPoint(30.0, 1000.0, jam_density=None).sanity_check_vs_jam()


def test_mfd_point_speed_and_network_speed():
    assert MFDPoint(density=20.0, flow=800.0).speed() == pytest.approx(40.0)
    assert network_speed(production=12236.0, accumulation=653.0) == pytest.approx(18.7, abs=0.1)
    with pytest.raises(ValueError):
        MFDPoint(density=0.0, flow=0.0).speed()


# ------------------------------------------------------------- control/safety
def test_signal_action_validation():
    with pytest.raises(ValueError):
        SignalAction(junction_id="C", action_type=SignalActionType.SWITCH_TO_PHASE)
    ok = SignalAction(junction_id="C", action_type=SignalActionType.EXTEND, duration_s=5)
    assert ok.duration_s == 5


def test_safety_constraints_reject_impossible_values():
    SafetyConstraints(min_green_s=10, max_green_s=45)          # Lab 01 values
    with pytest.raises(ValueError):
        SafetyConstraints(min_green_s=50, max_green_s=45)


# ------------------------------------------------------------ grounded genai
def test_copilot_answer_must_cite_evidence_unless_refusing():
    with pytest.raises(ValueError):
        CopilotAnswer(text="traffic is fine")                  # ungrounded
    CopilotAnswer(text="queue 12 veh at C", evidence=[Evidence("metrics", "mean_queue_veh", "12")])
    CopilotAnswer(text="", refused=True, refusal_reason="no data")


# ------------------------------------------------------------ routing/figures
def test_route_decision_requires_a_path():
    with pytest.raises(ValueError):
        RouteDecision(edges=[], estimated_travel_time_s=10)
    RouteDecision(edges=["e1", "e2"], estimated_travel_time_s=10, strategy="shortest")


def test_figure_spec_demands_real_sources_unless_pure_diagram():
    with pytest.raises(ValueError):
        FigureSpec(filename="05_results_summary.png", title="results")
    FigureSpec(filename="05_results_summary.png", title="results",
               source_artifacts=["outputs/metrics/run.json"])
    FigureSpec(filename="01_lab_architecture.png", title="arch",
               metadata={"synthetic_ok": "1"})


# --------------------------------------------------------- fairness contract
def test_benchmark_spec_rejects_unfair_arms():
    spec = BenchmarkSpec(benchmark_id="tsc_v1", scenario_ids=["dhaka_a"],
                         seeds=[1, 2, 3], warmup_s=300, duration_s=3600)
    fair = ArmSetup(name="fixed", component_category="controller", component_name="fixed_time",
                    scenario_ids=["dhaka_a"], seeds=[1, 2, 3], warmup_s=300, duration_s=3600)
    spec.assert_fair({"fixed": fair})
    cheating = ArmSetup(name="ours", component_category="controller", component_name="ours",
                        scenario_ids=["dhaka_a"], seeds=[1, 2, 3, 4], warmup_s=300,
                        duration_s=3600)
    with pytest.raises(ValueError, match="different seeds"):
        spec.assert_fair({"fixed": fair, "ours": cheating})


# --------------------------------------------------------------- provenance
def test_provenance_refuses_to_publish_incomplete_records(tmp_path):
    with pytest.raises(ValueError):
        RunProvenance(lab="02", experiment="x").require_complete()   # no sha/seeds
    p = RunProvenance(lab="02_dhaka_osm", experiment="full", git_sha="abc123", seeds=(42,))
    p.require_complete()
    out = tmp_path / "prov.json"
    p.to_json(out)
    assert "02_dhaka_osm" in out.read_text()


# ------------------------------------- FOREIGN implementations satisfy protocols
class ForeignController:
    """Mimics a third-party repo: knows nothing about DhakaFlow base classes."""

    name = "foreign_fixed"
    controlled_junctions = ("C",)

    def reset(self):
        pass

    def act(self, observation, time_s, forecast=None):
        return [SignalAction(junction_id="C", action_type=SignalActionType.HOLD)]


class ForeignBackend:
    time_s = 0.0
    is_running = False

    def reset(self, scenario):
        return TrafficObservation(time_s=0.0)

    def step(self):
        return TrafficObservation(time_s=1.0)

    def close(self):
        pass


class ForeignDetector:
    class_names = ("car", "bus")

    def detect(self, frame, frame_index, timestamp_s):
        return [Detection(BoundingBox(0, 0, 10, 10), VehicleClass.CAR, 0.9,
                          frame_index, timestamp_s)]


@pytest.mark.parametrize("obj,proto", [
    (ForeignController(), TrafficController),
    (ForeignBackend(), SimulationBackend),
    (ForeignDetector(), Detector),
])
def test_foreign_implementations_conform_without_inheritance(obj, proto):
    assert isinstance(obj, proto)
    assert type(obj).__mro__[1] is object      # really does not inherit from us


# ------------------------------------------------------------------ registry
def test_registry_builds_and_forbids_duplicate_sources_of_truth():
    clear(["controller"])
    register("controller", "foreign_fixed")(lambda **kw: ForeignController())
    assert "foreign_fixed" in available("controller")
    assert isinstance(build("controller", "foreign_fixed"), TrafficController)
    with pytest.raises(ValueError, match="already registered"):
        register("controller", "foreign_fixed")(lambda **kw: ForeignController())
    with pytest.raises(KeyError):
        build("controller", "does_not_exist")
    clear(["controller"])


def test_registry_rejects_unknown_category():
    with pytest.raises(ValueError):
        register("quantum_teleporter", "x")(lambda **kw: None)
