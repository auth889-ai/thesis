"""Line-protocol server exposing the Dhaka RT-DETR to other environments.

The detector needs the authors' exact pins (conda env `rtdetr`, torch 2.0.1)
while the demo runs on the system python — so the demo spawns THIS script in
the pinned env and speaks a one-line protocol:

    stdin :  <path-to-image-file>\n
    stdout:  {"dets": [...DhakaRTDETR.predict() output...]}\n

First line printed is {"ready": true, "load_s": ...}. EOF on stdin exits.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.perception.rtdetr_dhaka import DhakaRTDETR  # noqa: E402


def main() -> None:
    import cv2
    ckpt = sys.argv[1]
    conf = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
    t0 = time.time()
    det = DhakaRTDETR(ckpt, conf=conf)
    print(json.dumps({"ready": True, "load_s": round(time.time() - t0, 1)}),
          flush=True)
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        frame = cv2.imread(path)
        if frame is None:
            print(json.dumps({"error": f"unreadable: {path}"}), flush=True)
            continue
        print(json.dumps({"dets": det.predict(frame)}), flush=True)


if __name__ == "__main__":
    main()
