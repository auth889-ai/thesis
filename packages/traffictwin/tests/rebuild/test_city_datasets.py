"""The city adapter: any city, one interface — and missing readings never become fake zeros."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from traffictwin.data.city_datasets import REGISTRY, CityData, available, load_city  # noqa: E402

PRESENT = [c for c in REGISTRY if available(c)]


def test_registry_is_well_formed():
    for name, e in REGISTRY.items():
        assert {"dir", "loader", "quantity", "paper", "sensors"} <= set(e), name
        assert callable(e["loader"]) and e["sensors"] > 0


def test_unknown_city_fails_loudly():
    with pytest.raises(SystemExit, match="unknown city"):
        load_city("ATLANTIS")


def test_absent_city_tries_the_drive_then_explains_the_failure():
    """A missing city is fetched from the 2 TB Drive; only if that fails does it raise, and the
    message must name the remote it tried so the user can check it."""
    absent = next((c for c in REGISTRY if not available(c)), None)
    if absent is None:
        pytest.skip("every registered city is present")
    with pytest.raises(SystemExit, match="could not be fetched"):
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


# --------------------------------------------------------------------- floors / protocol
@pytest.mark.skipif("METR-LA" not in PRESENT, reason="METR-LA not fetched")
def test_floors_reproduce_the_published_protocol():
    """Our historical-average floor must match DCRNN's published HA, or our evaluation differs."""
    from traffictwin.forecasting.evaluation.benchmark_floors import floors_for_city
    rec = floors_for_city("METR-LA", [3, 6, 12])
    ha = rec["floors"][3]["historical_average"]
    assert abs(ha["mae"] - 4.16) / 4.16 < 0.05, f"HA MAE {ha['mae']} vs published 4.16"
    assert abs(ha["rmse"] - 7.80) / 7.80 < 0.05


@pytest.mark.skipif("METR-LA" not in PRESENT, reason="METR-LA not fetched")
def test_floors_behave_like_forecasters_should():
    from traffictwin.forecasting.evaluation.benchmark_floors import floors_for_city
    f = floors_for_city("METR-LA", [3, 6, 12])["floors"]
    assert f[3]["persistence"]["mae"] < f[6]["persistence"]["mae"] < f[12]["persistence"]["mae"], \
        "persistence must degrade as the horizon grows"
    for h in (3, 6, 12):
        assert f[h]["persistence"]["mae"] < f[h]["global_mean"]["mae"], "any floor must beat the mean"
        assert f[h]["historical_average"]["mae"] < f[h]["global_mean"]["mae"]
    ha = [f[h]["historical_average"]["mae"] for h in (3, 6, 12)]
    assert max(ha) - min(ha) < 0.01, "historical average is horizon-independent by construction"


@pytest.mark.skipif("METR-LA" not in PRESENT, reason="METR-LA not fetched")
def test_no_future_leakage_in_the_historical_average():
    """The HA table must be built from the training region only."""
    import inspect
    from traffictwin.forecasting.evaluation import benchmark_floors as bf
    src = inspect.getsource(bf.floors_for_city)
    assert "[:n_train]" in src, "the slot table must be accumulated over the train split only"
