"""P1 benchmark result schema — every candidate reports the same fields.

The comparison is two-axis, per the approved protocol:

* ARCHITECTURE axis: RT-DETR/RT-DETRv2, D-FINE, RT-DETRv4 (CURRENT_CHALLENGER).
* RECIPE axis:       native official recipe, DEIM (where officially supported).

DEIM is a training framework, never an architecture — a result row is always
(architecture, recipe), so "DEIM vs D-FINE" cannot be expressed at all.

A `BenchmarkRow` refuses to validate unless every mandated metric is present or
explicitly marked NOT_MEASURED with a reason — absent must never look like zero.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping

ARCHITECTURES = ("rtdetr_v2", "dfine", "rtdetrv4")
RECIPES = ("native", "deim")

# Per the mandate: these classes' AP is decisive, not overall mAP.
DECISIVE_CLASSES = ("rickshaw", "cng", "easybike", "motorcycle", "bus")

MANDATED_METRICS = (
    "map50", "map50_95", "precision", "recall",
    "ap_rickshaw", "ap_cng", "ap_easybike", "ap_motorcycle", "ap_bus",
    "fps", "latency_ms", "peak_vram_mb", "training_time_h",
)

NOT_MEASURED = "NOT_MEASURED"


@dataclass
class BenchmarkRow:
    """One (architecture, recipe, dataset_track) result."""

    architecture: str
    recipe: str
    dataset_track: str                  # "BNVD" | "PORIBOHON_BD"
    split_id: str                       # hash of the exact split file list
    checkpoint_origin: str              # official pretrained checkpoint used
    official_repo_sha: str
    metrics: dict = field(default_factory=dict)
    not_measured: dict = field(default_factory=dict)   # metric -> reason
    gpu: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.architecture not in ARCHITECTURES:
            raise ValueError(
                f"unknown architecture {self.architecture!r}; valid: {ARCHITECTURES}. "
                "DEIM is a recipe, not an architecture — if you tried to pass it "
                "here, put it in `recipe` instead.")
        if self.recipe not in RECIPES:
            raise ValueError(f"unknown recipe {self.recipe!r}; valid: {RECIPES}")
        if not self.official_repo_sha:
            raise ValueError("official_repo_sha is required — no SHA, no result")
        missing = [m for m in MANDATED_METRICS
                   if m not in self.metrics and m not in self.not_measured]
        if missing:
            raise ValueError(
                f"mandated metrics missing without a NOT_MEASURED reason: {missing}")
        overlap = set(self.metrics) & set(self.not_measured)
        if overlap:
            raise ValueError(f"metrics both measured and NOT_MEASURED: {sorted(overlap)}")
        for m, v in self.metrics.items():
            if not isinstance(v, (int, float)):
                raise ValueError(f"{m}: measured value must be numeric, got {v!r}")

    @property
    def label(self) -> str:
        return f"{self.architecture}+{self.recipe}@{self.dataset_track}"

    def decisive_mean_ap(self) -> float | None:
        vals = [self.metrics.get(f"ap_{c}") for c in DECISIVE_CLASSES]
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else None


def select_winner(rows: list[BenchmarkRow]) -> dict:
    """Per-track winner by measured Bangladesh performance; domain shift reported.

    Rule (approved protocol): decisive-class mean AP is primary, overall mAP50
    secondary, latency the tiebreak. COCO reputation plays no role. If the two
    dataset tracks disagree, the output says DOMAIN_SHIFT — no model is forced
    to win both.
    """
    by_track: dict[str, list[BenchmarkRow]] = {}
    for r in rows:
        by_track.setdefault(r.dataset_track, []).append(r)

    winners: dict[str, dict] = {}
    for track, trows in by_track.items():
        ranked = sorted(
            trows,
            key=lambda r: (
                -(r.decisive_mean_ap() or -1.0),
                -(r.metrics.get("map50") or -1.0),
                r.metrics.get("latency_ms") or float("inf"),
            ))
        winners[track] = {
            "winner": ranked[0].label,
            "decisive_mean_ap": ranked[0].decisive_mean_ap(),
            "ranking": [r.label for r in ranked],
        }

    winner_models = {v["winner"].split("@")[0] for v in winners.values()}
    return {
        "per_track": winners,
        "domain_shift": len(winner_models) > 1,
        "verdict": (
            "DOMAIN_SHIFT: dataset tracks select different winners — reported "
            "as a finding, no model forced to win both"
            if len(winner_models) > 1 else
            (next(iter(winner_models)) if winner_models else "NO_RESULTS")),
    }


def save_rows(rows: list[BenchmarkRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(r) for r in rows], indent=2))


def load_rows(path: Path) -> list[BenchmarkRow]:
    return [BenchmarkRow(**d) for d in json.loads(path.read_text())]
