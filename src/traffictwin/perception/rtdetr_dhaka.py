"""Dhaka-fine-tuned RT-DETR inference wrapper — official loading pattern.

Follows tools/infer.py from the pinned official repo verbatim (YAMLConfig with
resume → prefer the EMA weights → model.deploy() + postprocessor.deploy()).
We add nothing algorithmic: a config file in THEIR format describing the arm
(r50, num_classes 16 — the training-time label space), and a thin predict()
that maps 1-based training labels back to Poribohon class names.

Runtime environment: conda env `rtdetr` (python 3.11, torch 2.0.1,
torchvision 0.15.2, numpy<2 — the authors' exact pins; modern torchvision
removed the `datapoints` API their code imports). Validated 2026-08-26:
394 ms/frame CPU, 18/18 sane detections on a live camera frame.

The demo path uses this detector with a minimal IoU track-carrier for overlay
IDs only; benchmark tracking claims come from official ByteTrack at the
tracking gate, never from the demo tracker.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

UPSTREAM = Path.home() / ".dhakaflow" / "upstream" / "RT-DETR" / "rtdetr_pytorch"

# Written into the official configs dir (a scratch clone; adding a config file
# in their own format mirrors exactly what the training job did on the
# instance — their code is never edited).
ARM_CONFIG = """__include__: ['./rtdetr_r50vd_6x_coco.yml', ]
num_classes: 16
remap_mscoco_category: False
"""

from traffictwin.perception.voc_to_yolo import PORIBOHON_CLASSES  # noqa: E402


class DhakaRTDETR:
    def __init__(self, checkpoint: str | Path, device: str = "cpu",
                 conf: float = 0.5):
        import torch
        sys.path.insert(0, str(UPSTREAM))
        from src.core import YAMLConfig  # noqa: PLC0415 — official module

        cfg_path = UPSTREAM / "configs" / "rtdetr" / "poribohon_r50_infer.yml"
        cfg_path.write_text(ARM_CONFIG)
        cfg = YAMLConfig(str(cfg_path), resume=str(checkpoint))
        ckpt = torch.load(str(checkpoint), map_location="cpu",
                          weights_only=False)
        state = ckpt["ema"]["module"] if "ema" in ckpt else ckpt["model"]
        cfg.model.load_state_dict(state)

        class _Deploy(torch.nn.Module):          # official infer.py pattern
            def __init__(self):
                super().__init__()
                self.model = cfg.model.deploy()
                self.postprocessor = cfg.postprocessor.deploy()

            def forward(self, images, orig_sizes):
                return self.postprocessor(self.model(images), orig_sizes)

        self._torch = torch
        self.device = device
        self.model = _Deploy().to(device).eval()
        self.conf = conf

    def predict(self, frame_bgr: np.ndarray) -> list[dict]:
        """BGR frame -> [{'name','label','score','box':[x1,y1,x2,y2]}]."""
        import torchvision.transforms as T
        from PIL import Image
        torch = self._torch

        im = Image.fromarray(frame_bgr[..., ::-1])      # BGR -> RGB
        w, h = im.size
        tensor = T.Compose([T.Resize((640, 640)), T.ToTensor()])(im)[None]
        orig = torch.tensor([w, h])[None].to(self.device)
        with torch.no_grad():
            labels, boxes, scores = self.model(tensor.to(self.device), orig)
        out = []
        for lab, box, sc in zip(labels[0].tolist(), boxes[0].tolist(),
                                scores[0].tolist()):
            if sc < self.conf:
                continue
            lab = int(lab)
            name = (PORIBOHON_CLASSES[lab - 1]
                    if 1 <= lab <= len(PORIBOHON_CLASSES) else f"cls{lab}")
            out.append({"name": name, "label": lab, "score": float(sc),
                        "box": [float(x) for x in box]})
        return out
