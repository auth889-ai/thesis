"""Part A (2026-10-12): the ML + V2X loop, core/simulation/ambulance/rl_v2x_loop.py. The pure parts here; the run itself needs sumo-rl's venv."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]
spec = importlib.util.spec_from_file_location("rl_v2x_loop", REPO / "core/simulation/ambulance/rl_v2x_loop.py")
loop = importlib.util.module_from_spec(spec); spec.loader.exec_module(loop)


def test_emvlight_addresses_the_primary_and_secondary_junctions_only_and_the_scale_is_read():
    sig = [{"tls": "A", "route_index": 3}, {"tls": "B", "route_index": 9}, {"tls": "C", "route_index": 20}]
    assert [s["tls"] for s in loop.primary_secondary(sig, 0)] == ["A", "B"]            # entering A next, B after it; C waits
    assert [s["tls"] for s in loop.primary_secondary(sig, 4)] == ["B", "C"]            # A passed
    assert [s["tls"] for s in loop.primary_secondary(sig, 21)] == []
    assert loop.dhaka_scale() == json.loads((REPO / "evidence/ambulance_rq2/dhaka_density/match.json").read_text())["chosen_scale"]
    assert loop.ARMS == ("fixed", "rl", "rl_v2i", "fixed_v2i") and "2109.05429" in loop.EMVLIGHT
    mk = (REPO / "Makefile").read_text()
    assert "run-ambulance-loop:" in mk and "rl_v2x_loop.py" in mk.split("run-ambulance-loop:")[1].split("\n")[1]
    assert "rl_v2x_loop" not in (REPO / "scripts/live/present.py").read_text()        # make present is untouched


def test_the_loop_counts_messages_per_junction_and_records_the_override_events(monkeypatch):
    """LoopRun's bookkeeping on top of the parent's counters, with a stand-in parent send and no SUMO."""
    class Stub(loop.LoopRun):
        def __init__(self):                                    # no SUMO: only the fields the overridden methods touch
            self.msgs = {"sent": 0, "delivered": 0, "lost": 0, "out_of_range": 0}
            self.per_junction = {"J1": {"sent": 0, "delivered": 0, "lost": 0, "out_of_range": 0}}
            self.on_junction_delivered = None; self.got = []
            self.events, self._held, self.informed, self.preemption = [], set(), {}, None
        def _parent_send(self, ok, why):
            self.msgs["sent"] += 1; self.msgs[why] += 1; return ok
    from types import SimpleNamespace
    s = Stub(); s.on_junction_delivered = s.got.append
    monkeypatch.setattr(loop.service.AmbulanceRun, "_send", lambda self, a, b, t: self._parent_send(b.id == "J1" and t > 1, "delivered" if (b.id == "J1" and t > 1) else "lost"))
    assert s._send(SimpleNamespace(id="amb"), SimpleNamespace(id="J1"), 1.0) is False and s.per_junction["J1"] == {"sent": 1, "delivered": 0, "lost": 1, "out_of_range": 0}
    assert s._send(SimpleNamespace(id="amb"), SimpleNamespace(id="J1"), 2.0) is True and s.per_junction["J1"]["delivered"] == 1 and s.got == ["J1"]
    s._send(SimpleNamespace(id="amb"), SimpleNamespace(id="car7"), 2.0)              # a car: counted by the parent only
    assert s.msgs["sent"] == 3 and s.per_junction["J1"]["sent"] == 2


def test_saved_loop_evidence_hashes_when_present():
    d = REPO / "evidence/ambulance_loop"
    if not (d / "SHA256SUMS").exists():
        import pytest
        pytest.skip("no loop evidence yet")
    for line in (d / "SHA256SUMS").read_text().splitlines():
        h, name = line.split(maxsplit=1)
        assert hashlib.sha256((d / name).read_bytes()).hexdigest() == h, name
    s = json.loads((d / "summary.json").read_text())
    assert s["seeds_completed"] and all(r["fixed"]["ambulance_s"] for r in s["rows"]) and "2109.05429" in s["design"]
