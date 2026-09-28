"""Perception pipeline: video -> RT-DETR -> official ByteTrack -> TrafficState.

Single source of truth for both Gate 1 and the runtime chain. Optional overlay
rendering (boxes, track ids, zone, verdict) for the examiner demo.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WEIGHTS = REPO / "results/artifacts/p1_winner/rtdetr_r50_poribohon_best.pth"
RTDETR_PY = str(Path.home() / "miniconda3/envs/rtdetr/bin/python")
STRIDE = 5


def perceive(video: str, camera_id: str | None, minutes: float,
             render_dir: Path | None = None) -> dict:
    import cv2
    from pipeline.adapters.perception.bytetrack_adapter import ByteTrackAdapter
    from pipeline.adapters.perception.state_estimator import (StateEstimator,
                                                     load_registration)
    reg = load_registration(camera_id) if camera_id else None
    if reg and not reg.get("approach_zones"):
        reg = None
    bridge = subprocess.Popen(
        [RTDETR_PY, "research/perception/rtdetr_bridge.py",
         str(WEIGHTS), "0.4"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
        bufsize=1, cwd=REPO)

    def rj():
        for _ in range(200):
            line = bridge.stdout.readline()
            if not line:
                raise SystemExit("bridge died")
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        raise SystemExit("no JSON from bridge")

    rj()
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 240
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 352
    eff = fps / STRIDE
    trk = ByteTrackAdapter(frame_rate=eff)
    est = StateEstimator(reg, eff)
    classes: dict[int, str] = {}
    writer = None
    if render_dir is not None:
        render_dir.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(render_dir / "annotated.mp4"),
                                 cv2.VideoWriter_fourcc(*"mp4v"),
                                 max(eff, 1), (w, h))
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
    i, max_frames, t_wall = 0, int(minutes * 60 * fps), time.time()
    import numpy as np
    while i < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if i % STRIDE == 0:
            cv2.imwrite(tmp, frame)
            bridge.stdin.write(tmp + "\n")
            dets = rj().get("dets", [])
            tracks = trk.update(dets, (h, w))
            for tid, (x1, y1, x2, y2), _ in tracks:
                cx, cy = (x1+x2)/2, (y1+y2)/2
                best = min(dets, key=lambda d: (
                    ((d["box"][0]+d["box"][2])/2-cx)**2
                    + ((d["box"][1]+d["box"][3])/2-cy)**2), default=None)
                if best:
                    classes[tid] = best.get("name", "vehicle")
            t_s = i / fps
            est.ingest(t_s, tracks, classes)
            if writer is not None:
                fr = frame.copy()
                if reg:
                    for z in reg["approach_zones"].values():
                        pts = np.array(z["polygon"], dtype=int)
                        cv2.polylines(fr, [pts], True, (200, 170, 40), 1)
                queued = set(est.queued_since)
                for tid, (x1, y1, x2, y2), _ in tracks:
                    col = (60, 60, 230) if tid in queued else (90, 200, 90)
                    cv2.rectangle(fr, (int(x1), int(y1)),
                                  (int(x2), int(y2)), col, 1)
                    cv2.putText(fr, str(tid), (int(x1), int(y1) - 2),
                                cv2.FONT_HERSHEY_PLAIN, 0.8, col, 1)
                win = est.windows[-1] if est.windows else None
                if win:
                    cv2.putText(fr, f"{win['state']} q={win['queue_veh']}",
                                (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (255, 255, 255), 1)
                writer.write(fr)
        i += 1
    bridge.stdin.close(); bridge.terminate()
    if writer is not None:
        writer.release()
    state = est.finalize()
    state.update({"video": video, "camera_id": camera_id,
                  "registered": bool(reg),
                  "road_control": ("AVAILABLE" if reg else
                                   "LOCATION_REQUIRED_FOR_ROAD_CONTROL"),
                  "wall_s": round(time.time() - t_wall, 1),
                  "tracker": "ByteTrack official @d1bf019 "
                             "(detections supplied)"})
    return state
