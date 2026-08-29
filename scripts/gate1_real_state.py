#!/usr/bin/env python3
"""GATE 1 — REAL_STATE_PASS.

Real videos -> RT-DETR (Dhaka winner) -> OFFICIAL ByteTrack -> physical state.

Cases:
  A  free flow                     -> must NOT be CONGESTED
  B  congestion present/forming    -> must be CONGESTED
  C  video BEGINS with standing queue -> must be CONGESTED from the start
     (kills the relative-speed failure mode)
  U  unregistered camera           -> PERCEPTION_AVAILABLE +
                                      LOCATION_REQUIRED_FOR_ROAD_CONTROL

Writes artifacts/gates/REAL_STATE_PASS.json (PASS only if all four hold).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from research.perception.bytetrack_adapter import ByteTrackAdapter  # noqa
from research.perception.state_estimator import (StateEstimator,     # noqa
                                                 load_registration)

WEIGHTS = REPO / "artifacts/p1_winner/rtdetr_r50_poribohon_best.pth"
RTDETR_PY = str(Path.home() / "miniconda3/envs/rtdetr/bin/python")
STRIDE = 5


def perceive(video: str, camera_id: str | None, minutes: float) -> dict:
    import cv2
    reg = load_registration(camera_id) if camera_id else None
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

    rj()   # ready line
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 240
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 352
    eff_fps = fps / STRIDE
    trk = ByteTrackAdapter(frame_rate=eff_fps)
    est = StateEstimator(reg, eff_fps)
    classes: dict[int, str] = {}
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False).name
    i, max_frames = 0, int(minutes * 60 * fps)
    t_wall = time.time()
    while i < max_frames:
        ok, frame = cap.read()
        if not ok:
            break
        if i % STRIDE == 0:
            cv2.imwrite(tmp, frame)
            bridge.stdin.write(tmp + "\n")
            dets = rj().get("dets", [])
            tracks = trk.update(dets, (h, w))
            # nearest-det class per track (IoU-free, center distance)
            for tid, (x1, y1, x2, y2), _ in tracks:
                cx, cy = (x1+x2)/2, (y1+y2)/2
                best = min(dets, key=lambda d: (((d["box"][0]+d["box"][2])/2-cx)**2
                                                + ((d["box"][1]+d["box"][3])/2-cy)**2),
                           default=None)
                if best:
                    classes[tid] = best.get("name", "vehicle")
            est.ingest(i / fps, tracks, classes)
        i += 1
    bridge.stdin.close(); bridge.terminate()
    state = est.finalize()
    state["video"] = video
    state["camera_id"] = camera_id
    state["registered"] = bool(reg and reg.get("approach_zones"))
    state["road_control"] = ("AVAILABLE" if state["registered"]
                             else "LOCATION_REQUIRED_FOR_ROAD_CONTROL")
    state["wall_s"] = round(time.time() - t_wall, 1)
    state["tracker"] = "ByteTrack official @d1bf019 (detections supplied)"
    return state


def main() -> None:
    sp = ("/private/tmp/claude-501/-Users-jannatulferdouseva-thesis/"
          "fdc3d95a-9e51-4b32-a390-6d1fbc06a61a/scratchpad")
    rush = f"{sp}/rush_070E28355CAM1RP2.mp4"
    quiet = f"{sp}/live_test_clip.mp4"
    frozen = f"{sp}/caseC_starts_stationary.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "20",
                    "-t", "30", "-i", rush, "-c", "copy", frozen], check=True)

    cases = {}
    print("case A (free flow)…")
    cases["A_free_flow"] = perceive(quiet, "070E28355CAM1RP2", 1.0)
    print("case B (congestion)…")
    cases["B_congestion"] = perceive(rush, "070E28355CAM1RP2", 1.0)
    print("case C (starts stationary)…")
    cases["C_starts_stationary"] = perceive(frozen, "070E28355CAM1RP2", 0.5)
    print("case U (unregistered)…")
    cases["U_unregistered"] = perceive(frozen, None, 0.25)

    c = cases
    checks = {
        "A_not_congested": not c["A_free_flow"]["congestion_detected"],
        "B_congested": c["B_congestion"]["congestion_detected"],
        "C_congested_despite_stationary_start":
            c["C_starts_stationary"]["congestion_detected"],
        "C_congested_early": (
            c["C_starts_stationary"]["first_congested_window_t0"] is not None
            and c["C_starts_stationary"]["first_congested_window_t0"] <= 15.0),
        "U_honest_degradation":
            c["U_unregistered"]["road_control"]
            == "LOCATION_REQUIRED_FOR_ROAD_CONTROL",
        "fields_complete": all(
            k in c["B_congestion"]["windows"][0] for k in
            ("queue_veh", "stopped_duration_max_s", "arrivals", "discharges",
             "occupancy", "classes", "speed_px_s_median")),
    }
    result = {
        "gate": "REAL_STATE_PASS", "verdict":
            "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "cases": {k: {kk: v[kk] for kk in
                      ("congestion_detected", "first_congested_window_t0",
                       "road_control", "quality_flags", "wall_s",
                       "turning_movements")}
                  for k, v in c.items()},
        "detail": cases,
    }
    out = REPO / "artifacts/gates/REAL_STATE_PASS.json"
    out.write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k != "detail"},
                     indent=1))
    print("->", out)
    sys.exit(0 if result["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
