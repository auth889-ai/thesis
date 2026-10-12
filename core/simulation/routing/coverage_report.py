"""Compatibility import for the coverage interventions."""
import sys
from core.simulation.routing import coverage as _implementation
sys.modules[__name__] = _implementation
