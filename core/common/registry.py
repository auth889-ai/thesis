"""Component registry — how official paper implementations plug in.

An adapter registers a factory under a name; benchmarks and services resolve by
name from config. Upstream code is never imported at platform import time, so a
missing optional dependency (torch, a research repo) can never break the core.

    from core.common.registry import register, build

    @register("controller", "max_pressure_baseline")
    def _make(**kw):
        from paper_labs...import MaxPressureController   # local import
        return MaxPressureController(**kw)

    ctrl = build("controller", "max_pressure_baseline", min_green=10)
"""
from __future__ import annotations

from typing import Any, Callable, Iterable

# category -> {name -> factory}
_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {}

CATEGORIES = (
    "simulation", "detector", "tracker", "sensor", "forecaster", "twin",
    "controller", "router", "safety", "priority", "incident_extractor",
    "copilot", "metric", "benchmark",
)


def register(category: str, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator registering a factory under (category, name)."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category!r}; allowed: {CATEGORIES}")

    def _decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        bucket = _REGISTRY.setdefault(category, {})
        if name in bucket and bucket[name] is not factory:
            raise ValueError(
                f"{category}/{name} already registered — refusing to create a "
                "second source of truth for the same component")
        bucket[name] = factory
        return factory

    return _decorator


def build(category: str, name: str, /, **kwargs: Any) -> Any:
    """Instantiate a registered component."""
    try:
        factory = _REGISTRY[category][name]
    except KeyError as exc:
        raise KeyError(
            f"no {category} named {name!r}; registered: {available(category)}") from exc
    return factory(**kwargs)


def available(category: str) -> list[str]:
    return sorted(_REGISTRY.get(category, {}))


def all_registered() -> dict[str, list[str]]:
    return {c: available(c) for c in CATEGORIES if _REGISTRY.get(c)}


def clear(categories: Iterable[str] | None = None) -> None:
    """Test helper — never call from production code."""
    for c in list(categories or _REGISTRY):
        _REGISTRY.pop(c, None)
