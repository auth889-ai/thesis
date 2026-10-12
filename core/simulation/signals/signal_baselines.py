"""Correct-semantics signal baselines (Gate 6).

FIXED     : the network's own static programs (SUMO default) — A0.
ACTUATED  : SUMO's built-in gap-based actuated control (Eclipse SUMO docs,
            "Traffic Lights that respond to traffic") — generated from each
            static program with declared minDur/maxDur; the actuation logic
            is stock SUMO, not ours.
MAX_PRESSURE: Varaiya 2013 (10.1016/j.trc.2013.08.014): per junction, serve
            the phase with max pressure = sum over its green movements of
            (upstream queue - downstream queue). Downstream term included —
            spillback awareness is part of the definition. Phase changes go
            THROUGH the program (setPhase to the target green after letting
            the program's own yellow/all-red play), so yellow transitions are
            always the network's own; min/max green enforced here.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

MIN_GREEN = 10.0
MAX_GREEN = 60.0


def build_actuated_additional(net_xml: str, out_file: Path) -> Path:
    """Copy every static tlLogic as type=actuated (stock SUMO actuation)."""
    root = ET.parse(net_xml).getroot()
    add = ET.Element("additional")
    for tl in root.iter("tlLogic"):
        n = ET.SubElement(add, "tlLogic", id=tl.get("id"), type="actuated",
                          programID="actuated", offset=tl.get("offset", "0"))
        for ph in tl.iter("phase"):
            d = float(ph.get("duration"))
            state = ph.get("state")
            attrs = {"duration": ph.get("duration"), "state": state}
            if any(c in "Gg" for c in state) and d > 5:
                attrs["minDur"] = str(max(5.0, d * 0.2))
                attrs["maxDur"] = str(d * 2.0)
            ET.SubElement(n, "phase", **attrs)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(add).write(out_file)
    return out_file


class MaxPressureController:
    """Varaiya max-pressure over all given junctions, program-safe."""

    def __init__(self, t, tls_ids):
        self.t = t
        self.tls = {}
        for tls in tls_ids:
            logics = t.trafficlight.getAllProgramLogics(tls)
            phases = logics[0].phases if logics else []
            greens = [i for i, p in enumerate(phases)
                      if any(c in "Gg" for c in p.state)]
            links = t.trafficlight.getControlledLinks(tls)
            self.tls[tls] = {"phases": phases, "greens": greens,
                             "links": links, "since": 0.0, "want": None}

    def _pressure(self, tls, phase_idx) -> float:
        d = self.tls[tls]
        state = d["phases"][phase_idx].state
        pr = 0.0
        for i, lk in enumerate(d["links"]):
            if lk and i < len(state) and state[i] in "Gg":
                lin, lout = lk[0][0], lk[0][1]
                pr += (self.t.lane.getLastStepHaltingNumber(lin)
                       - self.t.lane.getLastStepHaltingNumber(lout))
        return pr

    def choose(self, tls) -> int:
        """The green phase to serve next: the one with the largest pressure (subclasses may override, e.g. EV priority)."""
        return max(self.tls[tls]["greens"], key=lambda i: self._pressure(tls, i))

    def step(self, now: float):
        t = self.t
        for tls, d in self.tls.items():
            if not d["greens"]:
                continue
            cur = t.trafficlight.getPhase(tls)
            elapsed = now - d["since"]
            in_green = cur in d["greens"]
            if in_green and elapsed < MIN_GREEN:
                continue
            best = self.choose(tls)
            if in_green and best == cur and elapsed < MAX_GREEN:
                t.trafficlight.setPhaseDuration(tls, MIN_GREEN)  # keep serving
                continue
            if in_green and (best != cur or elapsed >= MAX_GREEN):
                t.trafficlight.setPhaseDuration(tls, 0.0)  # let yellow play
                d["want"] = best
            elif not in_green and d["want"] is not None:
                nxt = (cur + 1) % len(d["phases"])
                if nxt in d["greens"] and nxt != d["want"]:
                    t.trafficlight.setPhase(tls, d["want"])  # after yellow/red
                    d["since"] = now
                    d["want"] = None
                elif nxt in d["greens"]:
                    d["since"] = now
                    d["want"] = None
