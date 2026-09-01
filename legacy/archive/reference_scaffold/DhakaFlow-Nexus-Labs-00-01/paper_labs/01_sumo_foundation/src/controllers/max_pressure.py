from src.common import GREEN_PHASE, pressure


class MaxPressure:
    name = "max_pressure"
    def __init__(self, min_green=10, extension=3, switch_margin=0):
        self.min_green = min_green
        self.extension = extension
        self.switch_margin = switch_margin
        self.green_started = 0.0

    def reset(self, traci):
        traci.trafficlight.setProgram("J0", "fixed")
        traci.trafficlight.setPhase("J0", GREEN_PHASE["NS"])
        self.green_started = traci.simulation.getTime()

    def step(self, traci):
        phase = traci.trafficlight.getPhase("J0")
        now = traci.simulation.getTime()
        if phase not in (GREEN_PHASE["NS"], GREEN_PHASE["EW"]):
            return
        axis = "NS" if phase == GREEN_PHASE["NS"] else "EW"
        other = "EW" if axis == "NS" else "NS"
        elapsed = now - self.green_started
        p_axis = pressure(traci, axis)
        p_other = pressure(traci, other)
        if elapsed >= self.min_green and p_other > p_axis + self.switch_margin:
            traci.trafficlight.setPhaseDuration("J0", 1)
            self.green_started = now + 4
        elif traci.trafficlight.getNextSwitch("J0") - now < 1.5:
            traci.trafficlight.setPhaseDuration("J0", self.extension)
