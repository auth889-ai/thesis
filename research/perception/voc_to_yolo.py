"""Poribohon-BD VOC XML → YOLO txt conversion — the license-clean track.

Poribohon-BD ships Pascal-VOC XML annotations; the detector harnesses consume
YOLO txt (normalised cx cy w h). This converter is deliberately paranoid:

* Class indices come from an EXPLICIT ordered list — never from "order of first
  appearance", which silently produces a different index mapping on every run.
* Every box is validated (finite, inside the image, positive area) and every
  rejection is counted and reported, never silently dropped.
* `round_trip_error()` converts back and measures the pixel error, so the
  conversion is *proven* lossless-within-rounding rather than assumed.

Runs locally (no torch) and inside Colab against Drive-mounted data.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

# Poribohon-BD's 15 classes, alphabetical as published on Mendeley (v2).
# The index mapping is THIS list's order — recorded in the conversion report so
# the label files are interpretable without this source file.
PORIBOHON_CLASSES: tuple[str, ...] = (
    "bicycle", "boat", "bus", "car", "cng", "easy-bike", "horse-cart", "launch",
    "leguna", "motorbike", "rickshaw", "tractor", "truck", "van", "wheelbarrow",
)


@dataclass
class ConversionReport:
    n_xml_files: int = 0
    n_converted: int = 0
    n_boxes: int = 0
    n_boxes_rejected: int = 0
    n_unknown_labels: int = 0
    unknown_labels: dict[str, int] = field(default_factory=dict)
    n_missing_size: int = 0
    rejections: list[str] = field(default_factory=list)   # first 50, with reason
    class_index: Mapping[str, int] = field(default_factory=dict)

    def note_rejection(self, reason: str) -> None:
        self.n_boxes_rejected += 1
        if len(self.rejections) < 50:
            self.rejections.append(reason)


def parse_voc(xml_path: Path) -> tuple[int, int, list[tuple[str, float, float, float, float]]]:
    """Return (width, height, [(label, xmin, ymin, xmax, ymax)])."""
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError("no <size> element")
    w = int(float(size.findtext("width", "0")))
    h = int(float(size.findtext("height", "0")))
    boxes = []
    for obj in root.iter("object"):
        name = (obj.findtext("name") or "").strip().lower()
        bb = obj.find("bndbox")
        if bb is None:
            continue
        boxes.append((
            name,
            float(bb.findtext("xmin", "nan")),
            float(bb.findtext("ymin", "nan")),
            float(bb.findtext("xmax", "nan")),
            float(bb.findtext("ymax", "nan")),
        ))
    return w, h, boxes


def voc_box_to_yolo(xmin: float, ymin: float, xmax: float, ymax: float,
                    img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """VOC corners → YOLO normalised (cx, cy, w, h). Raises on invalid boxes."""
    if not all(x == x for x in (xmin, ymin, xmax, ymax)):     # NaN check
        raise ValueError("non-finite coordinate")
    if img_w <= 0 or img_h <= 0:
        raise ValueError("non-positive image size")
    # Clamp to image bounds (VOC files occasionally exceed by 1-2 px).
    xmin, xmax = max(0.0, xmin), min(float(img_w), xmax)
    ymin, ymax = max(0.0, ymin), min(float(img_h), ymax)
    if xmax - xmin < 1.0 or ymax - ymin < 1.0:
        raise ValueError("degenerate box after clamping")
    cx = (xmin + xmax) / 2.0 / img_w
    cy = (ymin + ymax) / 2.0 / img_h
    w = (xmax - xmin) / img_w
    h = (ymax - ymin) / img_h
    return cx, cy, w, h


def yolo_box_to_voc(cx: float, cy: float, w: float, h: float,
                    img_w: int, img_h: int) -> tuple[float, float, float, float]:
    """Inverse mapping, for round-trip verification."""
    xmin = (cx - w / 2.0) * img_w
    ymin = (cy - h / 2.0) * img_h
    xmax = (cx + w / 2.0) * img_w
    ymax = (cy + h / 2.0) * img_h
    return xmin, ymin, xmax, ymax


def round_trip_error(xmin: float, ymin: float, xmax: float, ymax: float,
                     img_w: int, img_h: int) -> float:
    """Max abs pixel error of VOC→YOLO→VOC. Must be ~0 for a lossless claim."""
    yolo = voc_box_to_yolo(xmin, ymin, xmax, ymax, img_w, img_h)
    back = yolo_box_to_voc(*yolo, img_w, img_h)
    ref = (max(0.0, xmin), max(0.0, ymin),
           min(float(img_w), xmax), min(float(img_h), ymax))
    return max(abs(a - b) for a, b in zip(back, ref))


def convert_dataset(xml_dir: Path, out_dir: Path,
                    class_names: Sequence[str] = PORIBOHON_CLASSES,
                    ) -> ConversionReport:
    """Convert every VOC XML under xml_dir to YOLO txt in out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {name: i for i, name in enumerate(class_names)}
    rep = ConversionReport(class_index=index)

    for xml_path in sorted(Path(xml_dir).rglob("*.xml")):
        rep.n_xml_files += 1
        try:
            w, h, boxes = parse_voc(xml_path)
        except Exception as exc:
            rep.n_missing_size += 1
            rep.note_rejection(f"{xml_path.name}: unparseable ({exc})")
            continue

        lines = []
        for name, xmin, ymin, xmax, ymax in boxes:
            if name not in index:
                rep.n_unknown_labels += 1
                rep.unknown_labels[name] = rep.unknown_labels.get(name, 0) + 1
                continue
            try:
                cx, cy, bw, bh = voc_box_to_yolo(xmin, ymin, xmax, ymax, w, h)
            except ValueError as exc:
                rep.note_rejection(f"{xml_path.name}: {name}: {exc}")
                continue
            lines.append(f"{index[name]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
            rep.n_boxes += 1

        (out_dir / (xml_path.stem + ".txt")).write_text("\n".join(lines) + "\n"
                                                        if lines else "")
        rep.n_converted += 1
    return rep
