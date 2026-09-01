#!/usr/bin/env python3
"""Capture a LIVE camera feed (CDOT snapshot stream) into an mp4.

    python scripts/capture_live.py --camera 070E28355CAM1RP2 --seconds 60

The state-DOT snapshot refreshes every few seconds; we poll politely (2 s),
deduplicate identical frames, and stitch to video. Evidence domain:
PROVIDER_INTEGRATION_VALIDATION (real foreign feed — never claimed as Dhaka).
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAP = "https://cocam.carsprogram.org/Snapshots/{cam}.flv.png"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default="070E28355CAM1RP2")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = Path(a.out or REPO / "artifacts" / "uploads"
               / f"live_{a.camera}_{int(time.time())}.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f".live_{a.camera}_frames"
    tmp.mkdir(exist_ok=True)
    url = SNAP.format(cam=a.camera)
    req = urllib.request.Request(url, headers={"User-Agent":
        "DhakaFlow-thesis-research/1.0 (contact: janaeva@iut-dhaka.edu)"})
    last, n, t0 = None, 0, time.time()
    while time.time() - t0 < a.seconds:
        try:
            data = urllib.request.urlopen(req, timeout=10).read()
            h = hashlib.md5(data).hexdigest()
            if h != last:
                (tmp / f"f{n:04d}.png").write_bytes(data)
                n += 1
                last = h
        except Exception as e:                     # noqa: BLE001
            print("fetch retry:", e)
        time.sleep(2.0)
    if n < 3:
        raise SystemExit("live capture failed — too few frames")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "3",
                    "-i", str(tmp / "f%04d.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    print(f"LIVE CAPTURE: {out} ({n} unique frames / {a.seconds}s)")


if __name__ == "__main__":
    main()
