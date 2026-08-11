from .base import BaseController

class FixedTimeController(BaseController):
    """Observation-only baseline: SUMO executes the declared static TLS program."""
    name = "fixed_time"
    def step(self, traci, sim_time: float):
        self.maybe_update_green_start(traci, sim_time)
        return {"action": "observe"}
