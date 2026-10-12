"""The baseline: California Algorithm #7 (Payne, H. J. and Tignor, S. C., "Freeway incident-detection algorithms based on decision trees
with states", Transportation Research Record 682, 1978, pp. 30-37). Our own implementation of the published decision tree; no code
exists to reuse. Per detector pair, at each interval, three occupancy measures:
    OCCDF  = occ_up - occ_down                      spatial difference
    OCCRDF = (occ_up - occ_down) / occ_up           relative spatial difference
    DOCCTD = (occ_down(t-2) - occ_down(t)) / occ_down(t-2)   relative temporal change downstream (the compression-wave test)
and four states: 0 incident-free, 1 tentative, 2 incident confirmed (the alarm), 3 incident continuing. Thresholds T1, T2, T3 are
calibrated on the training seeds (train.py); the paper's own values were set for Los Angeles freeways and are not ours."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Thresholds:
    t1: float = 8.0       # OCCDF, occupancy points
    t2: float = 0.3       # OCCRDF
    t3: float = 0.2       # DOCCTD


class California7:
    def __init__(self, th: Thresholds):
        self.th, self.state = th, 0

    def step(self, occdf: float, occrdf: float, docctd: float) -> bool:
        """Advance one interval; True on the interval the alarm is raised (state 1 -> 2)."""
        th = self.th
        if self.state == 0:
            self.state = 1 if (occdf > th.t1 and occrdf > th.t2 and docctd > th.t3) else 0
            return False
        if self.state == 1:
            if occdf > th.t1 and occrdf > th.t2:                 # persistence: still there one interval later
                self.state = 2
                return True
            self.state = 0
            return False
        self.state = 3 if occrdf > th.t2 else 0                    # continuing while the relative difference holds
        return False


def alarms(rows: list[dict], th: Thresholds) -> list[bool]:
    """Run the state machine over one pair's rows in time order; True where the alarm is raised."""
    m = California7(th)
    return [m.step(r["occdf"], r["occrdf"], r["docctd"]) for r in rows]
