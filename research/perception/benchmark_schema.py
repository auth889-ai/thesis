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

# Fair training-budget policy (configs/perception/training_budget.yaml).
BUDGET_CLASSES = (
    "OFFICIAL_REPRODUCTION_BUDGET",   # author's schedule verbatim; reproduction only
    "DHAKA_COMMON_BENCHMARK_BUDGET",  # predeclared fair budget; the ONLY class
                                      # winner selection may use
    "TUNED_BUDGET",                   # candidate-specific tuning; reported separately
)

# Training provenance every row must carry (user mandate 2026-08-16).
REQUIRED_TRAINING_FIELDS = (
    "image_size", "batch_size", "epochs", "optimizer", "learning_rate",
    "augmentation", "inference_precision", "fps_protocol",
)

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
    budget_class: str = "DHAKA_COMMON_BENCHMARK_BUDGET"
    training: dict = field(default_factory=dict)       # REQUIRED_TRAINING_FIELDS
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
        if self.budget_class not in BUDGET_CLASSES:
            raise ValueError(
                f"unknown budget_class {self.budget_class!r}; valid: {BUDGET_CLASSES}")
        if not self.gpu:
            raise ValueError("gpu is required — results are GPU-conditional")
        missing_t = [f for f in REQUIRED_TRAINING_FIELDS if not self.training.get(f)]
        if missing_t:
            raise ValueError(
                f"training provenance missing: {missing_t} — every row records the "
                "full training configuration (fair-budget policy)")
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


def assert_fair_common_budget(rows: list["BenchmarkRow"]) -> None:
    """Common-budget rows must share the predeclared equal-budget parameters.

    Equalised: epochs, image_size, augmentation, inference_precision,
    fps_protocol. Deliberately NOT equalised (each architecture's official
    default, recorded per row): optimizer, learning_rate. Batch size may vary
    with VRAM; effective epochs are what fairness fixes.
    """
    common = [r for r in rows if r.budget_class == "DHAKA_COMMON_BENCHMARK_BUDGET"]
    if len(common) < 2:
        return
    equalised = ("epochs", "image_size", "augmentation",
                 "inference_precision", "fps_protocol")
    ref = {k: common[0].training.get(k) for k in equalised}
    for r in common[1:]:
        diff = {k: (ref[k], r.training.get(k)) for k in equalised
                if r.training.get(k) != ref[k]}
        if diff:
            raise ValueError(
                f"UNFAIR BUDGET: {r.label} differs from {common[0].label} on "
                f"{diff} — common-budget rows must be trained under the "
                "predeclared equal budget (configs/perception/training_budget.yaml)")


def select_winner(rows: list[BenchmarkRow],
                  expected_candidates: list[tuple[str, str]] | None = None) -> dict:
    """Per-track winner by measured Bangladesh performance; domain shift reported.

    Only DHAKA_COMMON_BENCHMARK_BUDGET rows participate — official-reproduction
    and tuned rows are informative, never selective. If `expected_candidates`
    [(architecture, recipe), ...] is given and any is missing from a track, the
    verdict is INCOMPLETE: no winner is declared until every directly comparable
    candidate has completed its intended benchmark.

    Rule (approved protocol): decisive-class mean AP is primary, overall mAP50
    secondary, latency the tiebreak. COCO reputation plays no role. If the two
    dataset tracks disagree, the output says DOMAIN_SHIFT — no model is forced
    to win both.
    """
    rows = [r for r in rows if r.budget_class == "DHAKA_COMMON_BENCHMARK_BUDGET"]
    assert_fair_common_budget(rows)

    by_track: dict[str, list[BenchmarkRow]] = {}
    for r in rows:
        by_track.setdefault(r.dataset_track, []).append(r)

    if expected_candidates:
        missing = {
            track: sorted(set(expected_candidates)
                          - {(r.architecture, r.recipe) for r in trows})
            for track, trows in by_track.items()
        }
        missing = {t: m for t, m in missing.items() if m}
        if missing or not by_track:
            return {"verdict": "INCOMPLETE",
                    "missing": missing or {"all_tracks": sorted(expected_candidates)},
                    "note": "no winner until every directly comparable candidate "
                            "has completed its intended benchmark"}

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
