"""YOLO-layout dataset → COCO detection JSON (adapter, format-only).

The official RT-DETR/D-FINE pipelines consume `CocoDetection` (img_folder +
COCO instances JSON). Our P1 package produces the YOLO layout
(`images/{split}/*.jpg` + `labels_split/{split}/*.txt`). This adapter
translates the *format* and nothing else — boxes are denormalised back to
absolute pixels using each image's actual size, class ids map 1:1 in the
order of the packaged class list (category_id = yolo_id + 1; COCO ids are
1-based by convention).

No filtering, no resizing, no augmentation — a translation layer per the
official-implementation policy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence


def _image_size(path: Path) -> tuple[int, int]:
    """(width, height) via PIL if present, else pure-stdlib JPEG/PNG probe."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        pass
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return (int.from_bytes(data[16:20], "big"),
                int.from_bytes(data[20:24], "big"))
    # Minimal JPEG SOF scan
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h = int.from_bytes(data[i + 5:i + 7], "big")
            w = int.from_bytes(data[i + 7:i + 9], "big")
            return w, h
        seg_len = int.from_bytes(data[i + 2:i + 4], "big")
        i += 2 + seg_len
    raise ValueError(f"cannot determine image size: {path}")


def convert_split(images_dir: Path, labels_dir: Path, class_names: Sequence[str],
                  out_json: Path) -> dict:
    """One split → one COCO instances JSON. Returns summary counts."""
    images, annotations = [], []
    ann_id = 1
    img_paths = sorted(p for p in Path(images_dir).iterdir()
                       if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    for img_id, img_path in enumerate(img_paths, start=1):
        w, h = _image_size(img_path)
        images.append({"id": img_id, "file_name": img_path.name,
                       "width": w, "height": h})
        label = Path(labels_dir) / (img_path.stem + ".txt")
        if not label.exists():
            continue
        for line in label.read_text().splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            cid = int(parts[0])
            cx, cy, bw, bh = (float(x) for x in parts[1:])
            x = (cx - bw / 2.0) * w
            y = (cy - bh / 2.0) * h
            annotations.append({
                "id": ann_id, "image_id": img_id, "category_id": cid + 1,
                "bbox": [round(x, 2), round(y, 2),
                         round(bw * w, 2), round(bh * h, 2)],
                "area": round(bw * w * bh * h, 2), "iscrowd": 0,
            })
            ann_id += 1
    coco = {
        "info": {"description": "DhakaFlow P1 adapter export (format-only)"},
        "images": images,
        "annotations": annotations,
        "categories": [{"id": i + 1, "name": n}
                       for i, n in enumerate(class_names)],
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(coco))
    return {"images": len(images), "annotations": len(annotations),
            "categories": len(class_names)}


def main() -> None:
    import argparse
    from .voc_to_yolo import PORIBOHON_CLASSES
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True,
                    help="pori_yolo root (images/ + labels_split/)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    for split in ("train", "val", "test"):
        s = convert_split(args.root / "images" / split,
                          args.root / "labels_split" / split,
                          PORIBOHON_CLASSES,
                          args.out / f"instances_{split}.json")
        print(split, s)


if __name__ == "__main__":
    main()
