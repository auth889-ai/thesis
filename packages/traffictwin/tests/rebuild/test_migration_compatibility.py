"""Moved experiment entry points remain import-compatible without copying algorithms."""
from importlib import import_module

import pytest


@pytest.mark.parametrize("old,new", [
    ("research.routing.chain_sweep", "research.routing.chain_sweep"),
    ("research.routing.scale_sweep", "research.routing.scale_sweep"),
    ("research.routing.predeparture_sensitivity", "research.routing.predeparture_sensitivity"),
    ("research.routing.online_sensitivity", "research.routing.online_sensitivity"),
    ("research.networking.channel_sweep", "research.networking.channel_sweep"),
    ("research.networking.traffic_stress_sweep", "research.networking.traffic_stress_sweep"),
])
def test_experiment_compatibility(old, new):
    assert import_module(old) is import_module(new)
