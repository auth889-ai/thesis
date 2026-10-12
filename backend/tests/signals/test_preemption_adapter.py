"""Preemption: the reused state machine drives a junction only through phases of the junction's own program."""
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.common.interfaces.priority import PriorityKind
from core.common.interfaces.safety import LAB01_VALIDATED_REFERENCE_PROFILE as PROFILE
from core.simulation.signals.preemption import sumo_adapter as sa

STATES = ["GGrr", "yyrr", "rrGG", "rryy"]           # links 0-1 arrive from the north, links 2-3 from the east
UPSTREAM = Path.home() / ".dhakaflow/upstream/adaptive-traffic-signal-rl/src/atsc"


class FakeConn:
    def __init__(self, states=STATES):
        self.phase, self.sets, self.states = 0, [], states
        shapes = {"n_0": [(0, 100), (0, 10)], "e_0": [(100, 0), (10, 0)]}           # n_0 travels south, e_0 travels west
        self.lane = SimpleNamespace(getShape=lambda l: shapes[l])
        self.trafficlight = SimpleNamespace(
            getProgram=lambda t: "0", getPhase=lambda t: self.phase, setPhase=self._set, setPhaseDuration=lambda t, d: None,
            getAllProgramLogics=lambda t: [SimpleNamespace(programID="0", phases=[SimpleNamespace(state=s, duration=6.0 if "y" in s else 30.0) for s in self.states])],
            getControlledLinks=lambda t: [[("n_0", "x", "")], [("n_0", "x", "")], [("e_0", "x", "")], [("e_0", "x", "")]])

    def _set(self, tls, phase):
        self.phase = phase
        self.sets.append(phase)


def test_approach_is_the_side_a_vehicle_arrives_from():
    assert [sa.approach_of(b) for b in (180, 270, 0, 90)] == ["N", "E", "S", "W"]


def test_a_request_gives_the_ambulance_green_through_amber_and_only_with_program_phases():
    conn = FakeConn()
    p = sa.SumoPreemption(conn, PROFILE)
    req = p.request("J", "e_0", 100.0)
    assert req.kind == PriorityKind.EMERGENCY and p.present["J"] == "E"
    for t in range(101, 160):
        p.step(float(t))
    shown = [s for _, _, s in p.applied]
    assert set(shown) <= set(STATES)                                   # nothing but the junction's own phases: no conflicting greens can be composed
    first_green_e = shown.index("rrGG")
    assert shown[:first_green_e].count("GGrr") >= int(PROFILE.min_green_s)      # the running green keeps its minimum
    assert shown[first_green_e - 1] == "yyrr" and shown[first_green_e - 6:first_green_e].count("yyrr") == 6   # the junction's own 6 s amber comes first
    assert p.preempted() == ["J"]


def test_after_the_ambulance_has_passed_the_program_resumes_and_no_request_changes_nothing():
    conn = FakeConn()
    p = sa.SumoPreemption(conn, PROFILE)
    for t in range(10):
        p.step(float(t))
    assert conn.sets == [] and p.applied == []                         # no request: the junction is never touched
    p.request("J", "e_0", 10.0)
    for t in range(10, 60):
        p.step(float(t))
    n = len(p.applied)
    p.passed("J")
    for t in range(60, 80):
        p.step(float(t))
    assert len(p.applied) == n and "J" not in p.fsms and "J" not in p.present


def test_a_junction_of_another_shape_is_left_alone_and_reported():
    conn = FakeConn(["GGrr", "rrGG"])                                  # no amber phases in its program
    p = sa.SumoPreemption(conn, PROFILE)
    p.request("J", "e_0", 0.0)
    for t in range(40):
        p.step(float(t))
    assert p.not_preemptable == {"J"} and conn.sets == []


@pytest.mark.skipif(not UPSTREAM.exists(), reason="the upstream clone is not on this machine")
def test_the_reused_files_differ_from_upstream_only_in_the_header_and_one_import_line():
    here = Path(sa.__file__).parent
    for ours, theirs, old in (("emergency.py", "control/emergency.py", "from atsc.sim.backend import APPROACHES"), ("phases.py", "envs/phases.py", "from atsc.sim.backend import PhaseDef")):
        mine = [l for l in (here / ours).read_text().splitlines()[4:]]
        up = (UPSTREAM / theirs).read_text().splitlines()
        diff = [(a, b) for a, b in zip(mine, up) if a != b]
        assert len(mine) == len(up) and len(diff) == 1 and diff[0][1] == old
