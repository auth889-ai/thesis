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
from research.perception.pipeline import perceive  # noqa

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
