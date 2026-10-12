"""Signal preemption for an emergency vehicle on a SUMO network, built around two files reused unchanged from
adaptive-traffic-signal-rl (MIT): its emergency override (emergency.py) and its signal safety state machine (phases.py).

This file is ours. It gives those two files what they expect and nothing more:
  - a junction's green phases, read from that junction's own SUMO signal program (which approaches each serves);
  - `emergency_present(junction, approach)`;
  - a place to apply the state machine's answer, through TraCI, always as a phase of the junction's OWN program
    (setting a signal state directly made SUMO 1.27.1 exit a minute later in our runs, so that call is not used).

One change of meaning against upstream, on purpose: upstream sees the emergency vehicle only at the stop line. Here a
junction knows of it from the moment an alert message is DELIVERED to that junction (`request`), until the vehicle has
passed (`passed`); then the junction's own program resumes.

Kept as upstream wrote them, and so inherited: a requested change can be cancelled while amber is showing, a green
runs one second longer than its minimum, and a green that reaches the maximum is taken away even from the emergency
vehicle. Amber time is the junction's own; minimum and maximum green come from the safety profile passed in.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

from core.common.interfaces.priority import PriorityKind, PriorityRequest
from core.common.interfaces.safety import SafetyConstraints
from core.simulation.signals.preemption.emergency import EmergencyController
from core.simulation.signals.preemption.phases import SignalFSM, SignalState
from core.simulation.signals.preemption.upstream_types import APPROACHES, PhaseDef

BEARING = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}


def approach_of(travel_bearing_deg: float) -> str:
    """The side of the junction a vehicle arrives FROM, given the compass direction it travels in."""
    arrives_from = (travel_bearing_deg + 180.0) % 360.0
    return min(APPROACHES, key=lambda a: abs((arrives_from - BEARING[a] + 180.0) % 360.0 - 180.0))


def lane_bearing(shape) -> float:
    (x0, y0), (x1, y1) = shape[-2][:2], shape[-1][:2]
    return math.degrees(math.atan2(x1 - x0, y1 - y0)) % 360.0


class Junction:
    """One signalised junction as the reused files see it, built from its SUMO program."""

    def __init__(self, tls_id: str, states: list[str], durations: list[float], link_approach: list[str], program: str):
        self.id, self.program = tls_id, program
        green = [i for i, s in enumerate(states) if any(c in "Gg" for c in s) and not any(c in "yY" for c in s)]
        self.sumo_index = green                                   # our phase k is the program's phase green[k]
        self.states = [states[i] for i in green]
        self.phases = [PhaseDef(k, f"program phase {i}", tuple(sorted({link_approach[j] for j, c in enumerate(states[i]) if c in "Gg"})))
                       for k, i in enumerate(green)]
        yellow = [d for s, d in zip(states, durations) if any(c in "yY" for c in s)]
        self.yellow_s = int(round(yellow[0])) if yellow else 0       # the junction's own amber time
        self.all_states = states
        self.hold_s = 1_000_000.0                                    # a phase we set stays until we set another

    @property
    def preemptable(self) -> bool:
        """Two green phases, each followed in the junction's own program by its amber: the only shape this adapter
        drives. Then every state shown is a phase of the junction's own program, and the amber after a green is the one
        the program itself uses before the other green. Any other junction is left to its program and reported."""
        return len(self.sumo_index) == 2 and all(i + 1 < len(self.all_states) and any(c in "yY" for c in self.all_states[i + 1]) for i in self.sumo_index)

    def program_phase(self, fsm: SignalFSM, leaving: int) -> int:
        """The phase of the junction's own program that shows what the state machine asks for: a green is its own
        phase; amber, and the state machine's all-red second after it, are the program's amber after the ending green."""
        return self.sumo_index[fsm.current] if fsm.state == SignalState.GREEN else self.sumo_index[leaving] + 1


class SumoPreemption:
    def __init__(self, conn, constraints: SafetyConstraints):
        self.conn, self.constraints = conn, constraints
        self.junctions: dict[str, Junction] = {}
        self.fsms: dict[str, SignalFSM] = {}
        self.present: dict[str, str] = {}                         # junction -> the approach the emergency vehicle is on
        self.leaving: dict[str, int] = {}                         # the green that is ending, while amber or all-red shows
        self.requests: list[PriorityRequest] = []
        self.not_preemptable: set[str] = set()                    # junctions whose program this adapter does not drive
        self.applied: list[tuple[float, str, str]] = []           # (time, junction, state shown): the record a test reads
        self.topo = SimpleNamespace(order=[], get=lambda iid: self.junctions[iid])
        self.backend = SimpleNamespace(emergency_present=lambda iid, a: self.present.get(iid) == a)
        self.controller = EmergencyController(SimpleNamespace(emergency=SimpleNamespace(preemption=True)), self.topo)

    def junction(self, tls_id: str) -> Junction:
        if tls_id not in self.junctions:
            t = self.conn.trafficlight
            program = t.getProgram(tls_id)
            logic = next(l for l in t.getAllProgramLogics(tls_id) if l.programID == program)
            links = t.getControlledLinks(tls_id)
            approach = [approach_of(lane_bearing(self.conn.lane.getShape(l[0][0]))) if l else "" for l in links]
            self.junctions[tls_id] = Junction(tls_id, [p.state for p in logic.phases], [p.duration for p in logic.phases], approach, program)
        return self.junctions[tls_id]

    def request(self, tls_id: str, in_lane: str, time_s: float, eta_s: float | None = None) -> PriorityRequest:
        """An alert reached this junction: the emergency vehicle will arrive on `in_lane`."""
        j = self.junction(tls_id)
        self.present[tls_id] = approach_of(lane_bearing(self.conn.lane.getShape(in_lane)))
        if not j.preemptable:
            self.not_preemptable.add(tls_id)
        elif tls_id not in self.topo.order:
            self.topo.order.append(tls_id)
        req = PriorityRequest(PriorityKind.EMERGENCY, tls_id, approach_lane=in_lane, eta_s=eta_s, metadata={"received_s": f"{time_s:.1f}"})
        self.requests.append(req)
        return req

    def passed(self, tls_id: str) -> None:
        """The emergency vehicle is through: the junction's own program takes over again, from the green now showing."""
        self.present.pop(tls_id, None)
        if tls_id in self.topo.order:
            self.topo.order.remove(tls_id)
        fsm = self.fsms.pop(tls_id, None)
        if fsm is not None:
            j = self.junctions[tls_id]
            self.conn.trafficlight.setPhase(tls_id, self.conn.trafficlight.getPhase(tls_id))      # restarts that green with its own duration; the cycle goes on from there

    def step(self, time_s: float) -> None:
        """Once per simulated second."""
        for tls_id in list(self.topo.order):
            if tls_id in self.fsms:
                continue
            j = self.junctions[tls_id]
            now = self.conn.trafficlight.getPhase(tls_id)
            if now not in j.sumo_index:
                continue                                           # the program is in amber: take over at its next green
            c = self.constraints
            self.fsms[tls_id] = SignalFSM(j.phases, int(c.min_green_s), int(c.max_green_s), j.yellow_s, int(c.all_red_s), start_phase=j.sumo_index.index(now))
        active = [i for i in self.topo.order if i in self.fsms]
        self.controller.apply(self._env(active))
        for tls_id in active:
            fsm, j = self.fsms[tls_id], self.junctions[tls_id]
            before = fsm.current
            fsm.tick()
            if fsm.state != SignalState.GREEN and tls_id not in self.leaving:
                self.leaving[tls_id] = before
            if fsm.state == SignalState.GREEN:
                self.leaving.pop(tls_id, None)
            phase = j.program_phase(fsm, self.leaving.get(tls_id, fsm.current))
            if self.conn.trafficlight.getPhase(tls_id) != phase:
                self.conn.trafficlight.setPhase(tls_id, phase)
            self.conn.trafficlight.setPhaseDuration(tls_id, j.hold_s)
            shown = j.all_states[phase]
            self.applied.append((time_s, tls_id, shown))

    def _env(self, active: list[str]):
        self.controller.topo = SimpleNamespace(order=active, get=self.topo.get)
        return SimpleNamespace(backend=self.backend, fsms=self.fsms)

    def preempted(self) -> list[str]:
        return self.controller.preempted_intersections()
