"""Alias of backend.app.routing.trip_analysis — kept for code and tests written against the old flat module name."""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("backend.app.routing.trip_analysis")
