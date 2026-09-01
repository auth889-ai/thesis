"""The city adapter: any city, one interface — and missing readings never become fake zeros."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from predict.city_datasets import REGISTRY, CityData, available, load_city  # noqa: E402

PRESENT = [c for c in REGISTRY if available(c)]


def test_registry_is_well_formed():
    for name, e in REGISTRY.items():
        assert {"dir", "loader", "quantity", "paper", "sensors"} <= set(e), name
        assert callable(e["loader"]) and e["sensors"] > 0


def test_unknown_city_fails_loudly():
    with pytest.raises(SystemExit, match="unknown city"):
        load_city("ATLANTIS")


def test_absent_city_explains_how_to_fetch_it():
    absent = next((c for c in REGISTRY if not available(c)), None)
    if absent is None:
        pytest.skip("every registered city is present")
    with pytest.raises(SystemExit, match="not present"):
        load_city(absent)


@pytest.mark.parametrize("city", PRESENT)
def test_every_present_city_loads_and_validates(city):
    cd = load_city(city)
    assert isinstance(cd, CityData)
    assert cd.values.ndim == 2 and cd.values.shape == cd.mask.shape
    assert cd.values.dtype == np.float32 and cd.mask.dtype == bool
    assert cd.reality in ("REAL", "SIMULATED")
    assert cd.bin_seconds > 0 and cd.quantity
    # Known, documented limitations. Anything NOT on this list is a regression and fails.
    KNOWN = {"DHAKA-TWIN": ["sensors never observed"],      # 39/250 edges carry no traffic in the twin demand
             "DHAKA-LIVE": ["too short", "coverage", "sensors never observed"]}
    for problem in cd.validate():
        assert any(k in problem for k in KNOWN.get(city, [])), f"{city}: unexpected problem: {problem}"
    assert cd.summary()["sensors"] == cd.values.shape[1]


@pytest.mark.parametrize("city", [c for c in PRESENT if c in ("METR-LA", "PEMS-BAY")])
def test_real_sensor_counts_match_the_published_papers(city):
    cd = load_city(city)
    assert cd.values.shape[1] == REGISTRY[city]["sensors"], "sensor count must match the paper"
    assert cd.bin_seconds == 300, "these datasets are 5-minute bins"
    assert cd.reality == "REAL"


@pytest.mark.skipif("METR-LA" not in PRESENT, reason="METR-LA not fetched")
def test_missing_readings_are_masked_not_treated_as_zero_speed():
    """METR-LA encodes an outage as 0.0 mph. Treating that as a real speed poisons training."""
    cd = load_city("METR-LA")
    zeros = cd.values == 0.0
    assert zeros.any(), "METR-LA is expected to contain zero-coded gaps"
    assert not cd.mask[zeros].any(), "a zero-coded gap must be masked out"
    observed = cd.values[cd.mask]
    assert observed.min() > 0, "no observed entry may be zero"
    assert 30 < observed.mean() < 70, "observed speeds must look like mph"


@pytest.mark.skipif("METR-LA" not in PRESENT, reason="METR-LA not fetched")
def test_adjacency_is_square_and_matches_sensor_count():
    cd = load_city("METR-LA")
    assert cd.adjacency is not None and cd.adjacency.shape == (207, 207)
    assert np.isfinite(cd.adjacency).all()


@pytest.mark.skipif("DHAKA-TWIN" not in PRESENT, reason="twin not built")
def test_simulated_city_is_labelled_and_cannot_pass_as_real():
    cd = load_city("DHAKA-TWIN")
    assert cd.reality == "SIMULATED"
    assert "DHAKA_SIMULATED_SENSOR_GRAPH" in str(cd.meta.values())
