from src.common import GREEN_PHASE, IN_LANES, lane_queue


class QueueActuated:
    name = "actuated"
    def __init__(self, min_green=10, extension=3, switch_margin=2):
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
        q_axis = lane_queue(traci, IN_LANES[axis])
        q_other = lane_queue(traci, IN_LANES[other])
        if elapsed >= self.min_green and q_other > q_axis + self.switch_margin:
            # Let the configured green expire; SUMO then executes yellow -> all-red -> other green.
            traci.trafficlight.setPhaseDuration("J0", 1)
            self.green_started = now + 4  # 3 s yellow + 1 s all-red in configured program
        else:
            # Extend only the current green, never skip safety transitions.
            if traci.trafficlight.getNextSwitch("J0") - now < 1.5:
                traci.trafficlight.setPhaseDuration("J0", self.extension)
