"""Sprint A integration: expose the Dhaka network through the platform interfaces.

Lab 02's product is a validated network, so it graduates as a `TrafficScenario`
plus a `SimulationBackend` implementation. Both are structural conformances —
nothing here inherits from DhakaFlow, matching the platform's adapter policy.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dhakaflow.common.types import (LaneState, TrafficObservation,  # noqa: E402
                                    TrafficScenario)


def build_scenario(net_file: Path, route_file: Path | None, cfg: dict,
                   scenario_id: str) -> TrafficScenario:
    """Wrap Lab 02 artifacts in the platform scenario type."""
    return TrafficScenario(
        scenario_id=scenario_id,
        network_path=str(net_file),
        route_path=str(route_file) if route_file else None,
        begin_s=0.0,
        end_s=float(cfg["sim_end"]),
        step_length_s=1.0,
        seed=int(cfg["seed"]),
        warmup_s=float(cfg.get("warmup_s", 0.0)),
        metadata={
            "lab": "02_dhaka_osm",
            "region": "central Dhaka (Farmgate–Karwan Bazar–Bangla Motor–Shahbagh)",
            "demand": "SYNTHETIC_VALIDATION_DEMAND",
            "traffic_side": "left_hand",
        },
    )


class SumoDhakaBackend:
    """Minimal TraCI-backed `SimulationBackend` for the Dhaka network.

    Conforms structurally to `dhakaflow.simulation.SimulationBackend`
    (reset/step/close/time_s/is_running) so later labs can drive this network
    through the same contract Lab 01 validated.
    """

    def __init__(self, sumo_binary: str = "sumo", observed_lanes: int = 400):
        self._binary = sumo_binary
        self._observed_lanes = observed_lanes
        self._traci = None
        self._lanes: list[str] = []
        self._running = False

    # ---------------------------------------------------------------- lifecycle
    def reset(self, scenario: TrafficScenario) -> TrafficObservation:
        import traci

        self.close()
        cmd = [self._binary, "-n", scenario.network_path,
               "--begin", str(scenario.begin_s), "--end", str(scenario.end_s),
               "--step-length", str(scenario.step_length_s),
               "--seed", str(scenario.seed), "--no-step-log", "true"]
        if scenario.route_path:
            cmd += ["--route-files", scenario.route_path]
        traci.start(cmd)
        self._traci = traci
        self._running = True
        all_lanes = [l for l in traci.lane.getIDList() if not l.startswith(":")]
        self._lanes = all_lanes[: self._observed_lanes]
        return self._observe()

    def step(self) -> TrafficObservation:
        if not self._running or self._traci is None:
            raise RuntimeError("backend is not running; call reset() first")
        self._traci.simulationStep()
        return self._observe()

    def close(self) -> None:
        if self._traci is not None and self._running:
            try:
                self._traci.close()
            except Exception:
                pass
        self._running = False
        self._traci = None

    # --------------------------------------------------------------- properties
    @property
    def time_s(self) -> float:
        return float(self._traci.simulation.getTime()) if self._running else 0.0

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------ helpers
    def _observe(self) -> TrafficObservation:
        t = self._traci
        lanes = {
            lid: LaneState(
                lane_id=lid,
                queue_length_veh=float(t.lane.getLastStepHaltingNumber(lid)),
                vehicle_count=int(t.lane.getLastStepVehicleNumber(lid)),
                mean_speed_ms=float(t.lane.getLastStepMeanSpeed(lid)),
                occupancy=float(t.lane.getLastStepOccupancy(lid)),
                waiting_time_s=float(t.lane.getWaitingTime(lid)),
            )
            for lid in self._lanes
        }
        signals = {tid: t.trafficlight.getRedYellowGreenState(tid)
                   for tid in t.trafficlight.getIDList()}
        return TrafficObservation(
            time_s=float(t.simulation.getTime()),
            lanes=lanes,
            signal_states=signals,
            vehicles_running=int(t.vehicle.getIDCount()),
            vehicles_arrived=int(t.simulation.getArrivedNumber()),
            source="sumo",
            metadata={"lab": "02_dhaka_osm"},
        )
