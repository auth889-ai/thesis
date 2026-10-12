# Reused from adaptive-traffic-signal-rl, https://github.com/Adityakumar1805/adaptive-traffic-signal-rl
# commit b62436b5d5fb1e5d07008d6f486f1a06a09ff64a, file src/atsc/sim/backend.py (these definitions only, copied as written)
# MIT License, Copyright (c) 2026 Aditya Kumar. Recorded in third_party/SOURCES.md.
"""The two definitions the reused files import from the upstream simulation module; the rest of that module (its
grid, its own simulator's metrics) is not used here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

NORTH, EAST, SOUTH, WEST = "N", "E", "S", "W"
APPROACHES: Tuple[str, ...] = (NORTH, EAST, SOUTH, WEST)


@dataclass(frozen=True)
class PhaseDef:
    """A controllable green phase: which incoming approaches receive green."""

    index: int
    name: str
    green_approaches: Tuple[str, ...]
