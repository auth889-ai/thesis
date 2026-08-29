class FixedTime:
    name = "fixed_time"
    def reset(self, traci):
        traci.trafficlight.setProgram("J0", "fixed")
    def step(self, traci):
        # SUMO's static program controls the signal; we only observe.
        return None
