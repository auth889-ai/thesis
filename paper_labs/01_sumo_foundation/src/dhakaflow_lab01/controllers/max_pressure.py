from .base import BaseController
from .helpers import phase_pressure_score, tls_logic, next_green_phase

class MaxPressureController(BaseController):
    name = "max_pressure"

    def step(self, traci, sim_time: float):
        idx, state = self.maybe_update_green_start(traci, sim_time)
        if not self.phase_is_green(state):
            return {"action": "transition"}
        if sim_time - self._last_decision < self.cfg.decision_interval:
            return {"action": "hold_between_decisions"}
        self._last_decision = sim_time
        elapsed = sim_time - (self._green_started or sim_time)
        if elapsed < self.cfg.min_green:
            return {"action": "hold_min_green", "elapsed": elapsed}

        logic = tls_logic(traci, self.cfg.tls_id)
        p_current, _ = phase_pressure_score(traci, self.cfg.tls_id, state)
        next_idx = next_green_phase(traci, self.cfg.tls_id, idx)
        next_state = logic.phases[next_idx].state
        p_next, _ = phase_pressure_score(traci, self.cfg.tls_id, next_state)

        if elapsed >= self.cfg.max_green:
            traci.trafficlight.setPhaseDuration(self.cfg.tls_id, 0.0)
            return {"action": "terminate_max_green", "p_current": p_current, "p_next": p_next}

        if p_current + self.cfg.switch_margin >= p_next:
            traci.trafficlight.setPhaseDuration(self.cfg.tls_id, self.cfg.extension)
            return {"action": "extend_best_pressure", "p_current": p_current, "p_next": p_next}

        traci.trafficlight.setPhaseDuration(self.cfg.tls_id, 0.0)
        return {"action": "terminate_for_next_pressure", "p_current": p_current, "p_next": p_next}
