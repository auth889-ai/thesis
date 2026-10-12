"""Model registry — metadata only, never weights.

Every model that competes in a DhakaFlow gate gets one YAML entry under
`model_registry/entries/`. The entry records what the model is, where its
official code and checkpoint live, what it was trained and evaluated on, the
numbers we actually obtained, and whether it won or lost.

Two rules the loader enforces mechanically, because they are the ones that decay
first under deadline pressure:

1. **No weights in git.** `checkpoint_uri` must point at Drive/S3/HF — a local
   path inside the repo is rejected.
2. **No unearned winners.** `status: WINNER` requires measured `metrics` and a
   `benchmark` naming the comparison it won. A model cannot be promoted on
   reputation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "model_registry" / "entries"

_REMOTE_PREFIXES = ("s3://", "gs://", "https://", "http://", "drive://", "hf://")


class ModelStatus(str, Enum):
    CANDIDATE = "CANDIDATE"      # declared, not yet run
    REPRODUCED = "REPRODUCED"    # official result reproduced within tolerance
    BENCHMARKED = "BENCHMARKED"  # evaluated on the common Dhaka benchmark
    WINNER = "WINNER"            # selected into the runtime
    CHALLENGER = "CHALLENGER"    # strong but not selected; kept as a baseline
    REJECTED = "REJECTED"        # measured and rejected, with a reason


class EvidenceDomain(str, Enum):
    """Which of the three separated evidence domains a number comes from.

    Mixing these is the single easiest way to make a false real-world claim,
    so every metric block must name its domain.
    """

    OFFICIAL_REAL_BENCHMARK = "OFFICIAL_REAL_BENCHMARK"          # METR-LA, PEMS-BAY, COCO, MOT17
    DHAKA_SIMULATED_SENSOR_GRAPH = "DHAKA_SIMULATED_SENSOR_GRAPH"  # SUMO detectors — SIMULATED
    DHAKA_REAL_VALIDATION_ANCHORS = "DHAKA_REAL_VALIDATION_ANCHORS"  # real BD sites/datasets


@dataclass(frozen=True)
class MetricBlock:
    domain: EvidenceDomain
    dataset: str
    values: Mapping[str, float]
    note: str = ""

    def __post_init__(self) -> None:
        if not self.dataset:
            raise ValueError("every metric block must name its dataset")
        if not self.values:
            raise ValueError(f"{self.dataset}: metric block has no values")


@dataclass(frozen=True)
class ModelEntry:
    key: str
    subsystem: str
    architecture: str
    status: ModelStatus
    paper: str = ""
    official_repo: str = ""
    official_sha: str = ""
    config: str = ""
    trained_on: str = ""
    checkpoint_uri: str = ""
    benchmark: str = ""
    metrics: tuple[MetricBlock, ...] = ()
    decision_rationale: str = ""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.checkpoint_uri and not self.checkpoint_uri.startswith(_REMOTE_PREFIXES):
            raise ValueError(
                f"{self.key}: checkpoint_uri must be remote (Drive/S3/HF), got "
                f"{self.checkpoint_uri!r}. Model weights are never committed to git.")

        if self.status in (ModelStatus.WINNER, ModelStatus.CHALLENGER, ModelStatus.REJECTED):
            if not self.metrics:
                raise ValueError(
                    f"{self.key}: status {self.status.value} requires measured metrics — "
                    "a model may not be promoted or rejected on reputation")
            if not self.decision_rationale:
                raise ValueError(
                    f"{self.key}: status {self.status.value} requires a decision_rationale")

        if self.status is ModelStatus.WINNER and not self.benchmark:
            raise ValueError(
                f"{self.key}: a WINNER must name the benchmark it won")

        if self.status is ModelStatus.REPRODUCED and not self.official_sha:
            raise ValueError(
                f"{self.key}: REPRODUCED requires the exact official_sha reproduced")

    @property
    def real_world_claim_supported(self) -> bool:
        """True only if some metric comes from a real (non-simulated) domain.

        Guards against simulator circularity: a model trained on SUMO output and
        evaluated only on SUMO output supports no real-Dhaka claim.
        """
        return any(m.domain is not EvidenceDomain.DHAKA_SIMULATED_SENSOR_GRAPH
                   for m in self.metrics)


def _parse_entry(raw: Mapping[str, Any]) -> ModelEntry:
    metrics = tuple(
        MetricBlock(
            domain=EvidenceDomain(m["domain"]),
            dataset=m["dataset"],
            values=dict(m.get("values") or {}),
            note=m.get("note", ""),
        )
        for m in (raw.get("metrics") or [])
    )
    return ModelEntry(
        key=raw["key"],
        subsystem=raw["subsystem"],
        architecture=raw["architecture"],
        status=ModelStatus(raw["status"]),
        paper=raw.get("paper", ""),
        official_repo=raw.get("official_repo", ""),
        official_sha=raw.get("official_sha", ""),
        config=raw.get("config", ""),
        trained_on=raw.get("trained_on", ""),
        checkpoint_uri=raw.get("checkpoint_uri", ""),
        benchmark=raw.get("benchmark", ""),
        metrics=metrics,
        decision_rationale=raw.get("decision_rationale", ""),
        extra=raw.get("extra", {}) or {},
    )


def load_entries(directory: Path | None = None) -> tuple[ModelEntry, ...]:
    """Load and validate every registry entry. Raises on the first invalid one."""
    import yaml

    d = directory or REGISTRY_DIR
    if not d.exists():
        return ()
    entries = []
    for path in sorted(d.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        if not raw:
            continue
        try:
            entries.append(_parse_entry(raw))
        except Exception as exc:  # noqa: BLE001 - re-raise with the offending file
            raise ValueError(f"{path.name}: {exc}") from exc
    return tuple(entries)


def winners(subsystem: str | None = None,
            directory: Path | None = None) -> tuple[ModelEntry, ...]:
    return tuple(e for e in load_entries(directory)
                 if e.status is ModelStatus.WINNER
                 and (subsystem is None or e.subsystem == subsystem))
