"""Canonical TrafficTwin research contracts.

Legacy ``pipeline`` and ``dashboard`` modules remain supported while new orchestration, APIs and
documentation depend on this small, evidence-first surface.
"""

from .forecasting import ForecastService, ModelRegistry
from .research_status import compute_research_status

__all__ = ["ForecastService", "ModelRegistry", "compute_research_status"]
