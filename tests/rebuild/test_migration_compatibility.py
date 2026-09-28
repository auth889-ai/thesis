"""Moved experiment entry points remain import-compatible without copying algorithms."""
from importlib import import_module

import pytest


@pytest.mark.parametrize("old,new", [
    ("experiments.routing.chain_sweep", "experiments.routing.chain_sweep"),
    ("experiments.routing.scale_sweep", "experiments.routing.scale_sweep"),
    ("experiments.routing.predeparture_sensitivity", "experiments.routing.predeparture_sensitivity"),
    ("experiments.routing.online_sensitivity", "experiments.routing.online_sensitivity"),
    ("experiments.networking.channel_sweep", "experiments.networking.channel_sweep"),
    ("experiments.networking.traffic_stress_sweep", "experiments.networking.traffic_stress_sweep"),
])
def test_experiment_compatibility(old, new):
    assert import_module(old) is import_module(new)
