from dataclasses import dataclass

@dataclass
class ControllerConfig:
    tls_id: str = "C"
    min_green: float = 10.0
    max_green: float = 45.0
    decision_interval: float = 5.0
    extension: float = 5.0
    switch_margin: float = 1.0

class BaseController:
    name = "base"
    def __init__(self, cfg: ControllerConfig):
        self.cfg = cfg
        self._last_decision = -1e9
        self._green_started = None

    def reset(self, traci):
        self._last_decision = -1e9
        self._green_started = None

    @staticmethod
    def phase_is_green(state: str) -> bool:
        return ("G" in state or "g" in state) and "y" not in state and "Y" not in state

    def maybe_update_green_start(self, traci, sim_time: float):
        tls = self.cfg.tls_id
        idx = traci.trafficlight.getPhase(tls)
        state = traci.trafficlight.getRedYellowGreenState(tls)
        if self.phase_is_green(state):
            if self._green_started is None or getattr(self, "_last_green_phase", None) != idx:
                self._green_started = sim_time
                self._last_green_phase = idx
        return idx, state

    def step(self, traci, sim_time: float):
        raise NotImplementedError
