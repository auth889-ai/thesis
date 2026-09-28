"""Moved experiment entry points remain import-compatible without copying algorithms."""
from importlib import import_module

import pytest


@pytest.mark.parametrize("old,new", [
    ("pipeline.routing.chain_sweep", "experiments.routing.chain_sweep"),
    ("pipeline.routing.scale_sweep", "experiments.routing.scale_sweep"),
    ("pipeline.routing.r1_sensitivity", "experiments.routing.predeparture_sensitivity"),
    ("pipeline.routing.r2_sensitivity", "experiments.routing.online_sensitivity"),
    ("pipeline.v2x.sweep", "experiments.networking.channel_sweep"),
    ("pipeline.v2x.stress_sweep", "experiments.networking.traffic_stress_sweep"),
])
def test_experiment_compatibility(old, new):
    assert import_module(old) is import_module(new)
