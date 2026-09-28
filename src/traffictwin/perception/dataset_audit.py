"""Real dataset audit — measured from files, never quoted from the paper.

Every number this module returns is computed by walking the actual dataset. Where
our measurement disagrees with the paper's claim, the measurement wins and the
disagreement is reported: a dataset that ships 17,000 images but claims 17,326 is
a finding, not a rounding error.

Designed to run in Colab against Drive-mounted data. No torch dependency — this
is I/O and statistics, so it also runs locally against a small sample.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class BBoxStats:
    """Bounding-box geometry in normalised YOLO units."""

    count: int = 0
    width_mean: float = 0.0
    height_mean: float = 0.0
    area_mean: float = 0.0
    area_p05: float = 0.0
    area_p50: float = 0.0
    area_p95: float = 0.0
    tiny_boxes: int = 0          # area < 0.1% of the image — hardest for detectors
    out_of_range: int = 0        # coordinates outside [0,1]: annotation errors


@dataclass
class DatasetAudit:
    """Complete measured description of one dataset split."""

    dataset_key: str
    root: str
    n_images: int = 0
    n_label_files: int = 0
    n_instances: int = 0
    images_without_labels: int = 0
    labels_without_images: int = 0
    empty_label_files: int = 0
    corrupt_images: int = 0
    duplicate_image_groups: int = 0
    duplicate_images: int = 0
    class_counts: Mapping[str, int] = field(default_factory=dict)
    class_index_counts: Mapping[int, int] = field(default_factory=dict)
    unknown_class_indices: Sequence[int] = ()
    resolutions: Mapping[str, int] = field(default_factory=dict)
    bbox: BBoxStats = field(default_factory=BBoxStats)
    instances_per_image_mean: float = 0.0
    claimed: Mapping[str, object] = field(default_factory=dict)
    discrepancies: Sequence[str] = ()

    def to_json(self, path: Path | None = None) -> str:
        payload = asdict(self)
        text = json.dumps(payload, indent=2, default=str)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        return text

    @property
    def class_imbalance_ratio(self) -> float | None:
        """Most frequent class count / least frequent. >100 means severe imbalance."""
        vals = [v for v in self.class_counts.values() if v > 0]
        if len(vals) < 2:
            return None
        return max(vals) / min(vals)


def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(int(q * len(sorted_vals)), len(sorted_vals) - 1)
    return sorted_vals[idx]


def _iter_files(root: Path, suffixes: set[str]) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in suffixes:
            yield p


def audit_yolo_dataset(root: Path, class_names: Sequence[str],
                       dataset_key: str = "unknown",
                       images_dirname: str = "images",
                       labels_dirname: str = "labels",
                       hash_images: bool = True,
                       claimed: Mapping[str, object] | None = None,
                       max_images: int | None = None) -> DatasetAudit:
    """Walk a YOLO-format dataset and measure it.

    Label format is `class cx cy w h`, normalised — the format BNVD ships (its
    authors' own `annotation_counter.py` reads exactly this).
    """
    root = Path(root)
    img_root = root / images_dirname if (root / images_dirname).exists() else root
    lbl_root = root / labels_dirname if (root / labels_dirname).exists() else root

    images = sorted(_iter_files(img_root, IMAGE_SUFFIXES))
    if max_images:
        images = images[:max_images]
    labels = sorted(_iter_files(lbl_root, {".txt"}))

    audit = DatasetAudit(dataset_key=dataset_key, root=str(root),
                         n_images=len(images), n_label_files=len(labels),
                         claimed=dict(claimed or {}))

    label_by_stem = {p.stem: p for p in labels}
    image_stems = {p.stem for p in images}

    audit.images_without_labels = sum(1 for s in image_stems if s not in label_by_stem)
    audit.labels_without_images = sum(1 for s in label_by_stem if s not in image_stems)

    # ---- images: resolution, corruption, duplicates ----------------------
    res_counter: Counter[str] = Counter()
    hashes: defaultdict[str, list[str]] = defaultdict(list)
    try:
        from PIL import Image
        have_pil = True
    except ImportError:
        have_pil = False

    for p in images:
        if have_pil:
            try:
                with Image.open(p) as im:
                    res_counter[f"{im.width}x{im.height}"] += 1
            except Exception:
                audit.corrupt_images += 1
                continue
        if hash_images:
            try:
                h = hashlib.md5(p.read_bytes()).hexdigest()
                hashes[h].append(p.name)
            except Exception:
                audit.corrupt_images += 1

    audit.resolutions = dict(res_counter.most_common(25))
    dup_groups = {h: names for h, names in hashes.items() if len(names) > 1}
    audit.duplicate_image_groups = len(dup_groups)
    audit.duplicate_images = sum(len(v) - 1 for v in dup_groups.values())

    # ---- labels: class counts and bbox geometry --------------------------
    idx_counts: Counter[int] = Counter()
    widths: list[float] = []
    heights: list[float] = []
    areas: list[float] = []
    tiny = out_of_range = 0
    per_image: list[int] = []

    for p in labels:
        n_here = 0
        try:
            lines = [l for l in p.read_text().splitlines() if l.strip()]
        except Exception:
            continue
        if not lines:
            audit.empty_label_files += 1
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 5:
                continue
            try:
                ci = int(float(parts[0]))
                cx, cy, w, h = (float(x) for x in parts[1:5])
            except ValueError:
                continue
            idx_counts[ci] += 1
            n_here += 1
            widths.append(w)
            heights.append(h)
            a = w * h
            areas.append(a)
            if a < 0.001:
                tiny += 1
            if not (0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0
                    and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
                out_of_range += 1
        per_image.append(n_here)

    areas_sorted = sorted(areas)
    audit.n_instances = sum(idx_counts.values())
    audit.class_index_counts = dict(sorted(idx_counts.items()))
    audit.class_counts = {
        (class_names[i] if 0 <= i < len(class_names) else f"UNKNOWN_INDEX_{i}"): n
        for i, n in sorted(idx_counts.items())
    }
    audit.unknown_class_indices = tuple(i for i in idx_counts
                                        if not (0 <= i < len(class_names)))
    audit.instances_per_image_mean = (
        sum(per_image) / len(per_image) if per_image else 0.0)
    audit.bbox = BBoxStats(
        count=len(areas),
        width_mean=sum(widths) / len(widths) if widths else 0.0,
        height_mean=sum(heights) / len(heights) if heights else 0.0,
        area_mean=sum(areas) / len(areas) if areas else 0.0,
        area_p05=_percentile(areas_sorted, 0.05),
        area_p50=_percentile(areas_sorted, 0.50),
        area_p95=_percentile(areas_sorted, 0.95),
        tiny_boxes=tiny,
        out_of_range=out_of_range,
    )

    audit.discrepancies = tuple(_discrepancies(audit))
    return audit


def _discrepancies(audit: DatasetAudit) -> list[str]:
    """Compare measured values against the paper's claims."""
    out: list[str] = []
    c = audit.claimed
    if not c:
        return out

    def cmp(name: str, measured: float, tol: float = 0.02) -> None:
        want = c.get(name)
        if want in (None, ""):
            return
        want = float(want)
        if want <= 0:
            return
        if abs(measured - want) / want > tol:
            out.append(f"{name}: paper claims {want:g}, measured {measured:g}")

    cmp("n_images", audit.n_images)
    cmp("n_instances", audit.n_instances)
    if c.get("n_classes"):
        measured_classes = len([k for k, v in audit.class_counts.items() if v > 0])
        if measured_classes != int(c["n_classes"]):
            out.append(f"n_classes: paper claims {c['n_classes']}, "
                       f"{measured_classes} classes actually populated")
    if c.get("mean_bbox_per_image"):
        cmp("mean_bbox_per_image", audit.instances_per_image_mean, tol=0.05)
    if audit.unknown_class_indices:
        out.append(f"label files contain class indices outside the declared list: "
                   f"{list(audit.unknown_class_indices)}")
    return out


def audit_to_markdown(audit: DatasetAudit) -> str:
    """Human-readable summary for the experiment log."""
    lines = [
        f"### {audit.dataset_key}",
        "",
        f"- images: **{audit.n_images:,}** · label files: {audit.n_label_files:,} "
        f"· instances: **{audit.n_instances:,}**",
        f"- instances/image: {audit.instances_per_image_mean:.3f}",
        f"- images without labels: {audit.images_without_labels:,} · "
        f"labels without images: {audit.labels_without_images:,} · "
        f"empty label files: {audit.empty_label_files:,}",
        f"- corrupt images: {audit.corrupt_images:,} · "
        f"duplicate images: {audit.duplicate_images:,} "
        f"({audit.duplicate_image_groups:,} groups)",
        f"- bbox area p05/p50/p95: {audit.bbox.area_p05:.5f} / "
        f"{audit.bbox.area_p50:.5f} / {audit.bbox.area_p95:.5f} · "
        f"tiny (<0.1%): {audit.bbox.tiny_boxes:,} · "
        f"out-of-range: {audit.bbox.out_of_range:,}",
    ]
    ratio = audit.class_imbalance_ratio
    if ratio:
        lines.append(f"- class imbalance (max/min): **{ratio:.1f}×**")
    if audit.class_counts:
        lines.append("")
        lines.append("| class | instances |")
        lines.append("|---|---|")
        for k, v in sorted(audit.class_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {k} | {v:,} |")
    if audit.discrepancies:
        lines.append("")
        lines.append("**Discrepancies vs published claims:**")
        for d in audit.discrepancies:
            lines.append(f"- {d}")
    return "\n".join(lines)
