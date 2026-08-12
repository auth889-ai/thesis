"""Visualization contract — every lab's figures obey the same rules.

Rules (from the artifact standard):
  * figures are produced by version-controlled scripts, never by hand;
  * they are rendered from real artifacts, never from typed-in numbers;
  * the filename encodes order and meaning: NN_snake_case.png;
  * each figure carries a provenance stamp (lab, versions, commit).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence, runtime_checkable

# Figure slots common to every lab (domain-specific ones are added per lab).
STANDARD_FIGURES: tuple[str, ...] = (
    "01_lab_architecture.png",
    "02_paper_to_dhakaflow_pipeline.png",
    "03_data_flow.png",
    "04_experiment_design.png",
    "05_results_summary.png",
    "06_final_dhakaflow_connection.png",
)


@dataclass(frozen=True)
class FigureSpec:
    """Declares a figure and the real artifacts it must be built from."""

    filename: str
    title: str
    source_artifacts: Sequence[str] = ()      # paths that must exist before drawing
    caption: str = ""
    provenance_stamp: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.filename.endswith(".png"):
            raise ValueError("figures are PNG; got " + self.filename)
        if not self.source_artifacts and not self.metadata.get("synthetic_ok"):
            raise ValueError(
                f"{self.filename}: no source artifacts declared — figures must be "
                "rendered from real data (set metadata['synthetic_ok'] for pure "
                "architecture diagrams)")


@runtime_checkable
class FigureRenderer(Protocol):
    """Renders a declared figure to disk and returns the written path."""

    def render(self, spec: FigureSpec, output_dir: str) -> str: ...
