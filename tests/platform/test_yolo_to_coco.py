"""yolo_to_coco adapter tests — format translation only, on synthetic files."""
from pathlib import Path

from pipeline.adapters.perception.yolo_to_coco import convert_split, _image_size


def _tiny_png(path: Path, w=32, h=16):
    import struct, zlib
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"".join(b"\x00" + b"\x00\x00\x00" * w for _ in range(h)))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", raw) + chunk(b"IEND", b""))


def test_size_probe_and_roundtrip(tmp_path):
    img = tmp_path / "images" / "a.png"
    img.parent.mkdir(parents=True)
    _tiny_png(img, 32, 16)
    assert _image_size(img) == (32, 16)
    lab = tmp_path / "labels" / "a.txt"
    lab.parent.mkdir()
    # centered box, half width/height -> pixels x=8,y=4,w=16,h=8
    lab.write_text("2 0.5 0.5 0.5 0.5\n")
    out = tmp_path / "coco.json"
    s = convert_split(img.parent, lab.parent, ("x", "y", "z"), out)
    import json
    d = json.loads(out.read_text())
    assert s == {"images": 1, "annotations": 1, "categories": 3}
    ann = d["annotations"][0]
    assert ann["category_id"] == 3            # yolo id 2 -> coco id 3
    assert ann["bbox"] == [8.0, 4.0, 16.0, 8.0]
    assert d["images"][0]["width"] == 32


def test_image_without_label_is_kept_as_negative(tmp_path):
    img = tmp_path / "images" / "b.png"
    img.parent.mkdir(parents=True)
    _tiny_png(img)
    (tmp_path / "labels").mkdir()
    s = convert_split(img.parent, tmp_path / "labels", ("x",), tmp_path / "c.json")
    assert s["images"] == 1 and s["annotations"] == 0
