"""Thin adapter to the OFFICIAL ByteTrack (FoundationVision @d1bf019).

Policy: we supply detections, consume tracks. The association algorithm is the
published one, unmodified — this file only converts formats.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

# NumPy>=1.24 removed the deprecated aliases the 2021 upstream uses. This is an
# environment shim, not an algorithm change — upstream code stays unmodified.
for _alias, _t in (("float", float), ("int", int), ("bool", bool)):
    if not hasattr(np, _alias):
        setattr(np, _alias, _t)

_WS = Path(os.environ.get("DHAKAFLOW_WORKSPACE",
                          Path.home() / ".dhakaflow" / "upstream"))
sys.path.insert(0, str(_WS / "ByteTrack"))
from yolox.tracker.byte_tracker import BYTETracker  # noqa: E402


class _Args:                       # defaults from the official demo (track.py)
    track_thresh = 0.5
    track_buffer = 30
    match_thresh = 0.8
    mot20 = False


class ByteTrackAdapter:
    def __init__(self, frame_rate: float = 6.0, track_thresh: float = 0.4):
        a = _Args()
        a.track_thresh = track_thresh
        self.tracker = BYTETracker(a, frame_rate=max(int(round(frame_rate)), 1))

    def update(self, dets: list[dict], img_hw: tuple[int, int]):
        """dets: [{'box':[x1,y1,x2,y2],'score':s,...}] -> [(tid, (x1,y1,x2,y2), score)]"""
        if dets:
            arr = np.array([[*d["box"], d["score"]] for d in dets],
                           dtype=np.float32)
        else:
            arr = np.zeros((0, 5), dtype=np.float32)
        online = self.tracker.update(arr, img_hw, img_hw)
        out = []
        for t in online:
            x1, y1, w, h = t.tlwh
            out.append((int(t.track_id), (float(x1), float(y1),
                                          float(x1 + w), float(y1 + h)),
                        float(t.score)))
        return out
