"""Alias of backend.app.forecasting.training_jobs — kept for code and tests written against the old flat module name."""
import importlib as _importlib
import sys as _sys

_sys.modules[__name__] = _importlib.import_module("backend.app.forecasting.training_jobs")
