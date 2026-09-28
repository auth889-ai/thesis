"""Compatibility import for the coverage interventions."""
import sys
from traffictwin.optimization import coverage as _implementation
sys.modules[__name__] = _implementation
