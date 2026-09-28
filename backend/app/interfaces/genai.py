"""GenAI copilot interfaces — Lab 25.

Hard boundary: the LLM is NOT the low-level signal controller. It explains,
diagnoses, retrieves, answers what-if questions and calls tools. Every answer
must be grounded in real system state, and the grounding is part of the type —
an ungrounded answer is invalid by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


@dataclass(frozen=True)
class Evidence:
    """One grounded fact backing an answer."""

    source: str                 # "metrics" | "twin_whatif" | "forecast" | "incident" | "artifact"
    reference: str              # artifact path, metric name, run id, incident id
    value: str = ""
    retrieved_at_s: float = 0.0


@dataclass(frozen=True)
class CopilotQuery:
    question: str
    time_s: float = 0.0
    scope: Mapping[str, str] = field(default_factory=dict)   # junction/corridor/time window
    language: str = "en"


@dataclass(frozen=True)
class CopilotAnswer:
    """Answer + the evidence it stands on + the tools it invoked."""

    text: str
    evidence: Sequence[Evidence] = ()
    tools_called: Sequence[str] = ()
    confidence: float | None = None
    refused: bool = False
    refusal_reason: str = ""

    def __post_init__(self) -> None:
        if not self.refused and not self.evidence:
            raise ValueError(
                "ungrounded answer: a non-refusal CopilotAnswer must cite at "
                "least one Evidence item")


@runtime_checkable
class TrafficCopilot(Protocol):
    """Operator-facing assistant over the live system and the experiment record."""

    def answer(self, query: CopilotQuery) -> CopilotAnswer: ...

    def register_tool(self, name: str, fn: Any, description: str) -> None: ...

    @property
    def tools(self) -> Sequence[str]: ...
