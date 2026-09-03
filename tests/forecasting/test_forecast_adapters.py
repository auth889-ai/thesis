"""The forecast interface exists to stop two specific failures: presenting a baseline as the
system's prediction, and running a model on data it cannot honestly serve."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.forecasting.adapters.base import CityData, NotAvailable      # noqa: E402
from pipeline.forecasting.adapters.baselines import PersistenceAdapter     # noqa: E402
from pipeline.forecasting.adapters.checkpoint_models import GraphWaveNetAdapter  # noqa: E402
from pipeline.forecasting.adapters.opencity import OpenCityAdapter          # noqa: E402
from pipeline.forecasting.adapters.registry import available_for, forecast  # noqa: E402


def city(T=30, N=250, city_id="dhaka"):
    return CityData(city_id=city_id, node_ids=[f"n{i}" for i in range(N)],
                    values=np.random.rand(T, N).astype("float32") * 15 + 3)


def test_forecast_returns_numbers_not_classes():
    f = PersistenceAdapter().forecast(city(), [5, 15])
    vals = f.values[15]
    assert len(vals) == 250
    assert all(isinstance(v, float) for v in vals), "a forecast must be numeric, not an ordinal class"


def test_opencity_refuses_a_short_history():
    """Its input window is 288 steps. Thirty is not a forecast, it is a fabrication."""
    chk = OpenCityAdapter().check(city(T=30))
    assert not chk["ok"]
    assert any("288" in r for r in chk["reasons"])


def test_opencity_refuses_a_tiny_graph():
    chk = OpenCityAdapter().check(city(T=400, N=12))
    assert not chk["ok"]
    assert any("nodes" in r for r in chk["reasons"])


def test_opencity_refuses_a_city_inside_its_pretraining_corpus():
    """Even with perfect data, METR_LA cannot yield a zero-shot claim."""
    chk = OpenCityAdapter().check(city(T=400, N=207, city_id="METR_LA"))
    assert not chk["ok"]
    assert any("pre-training" in r for r in chk["reasons"])


def test_city_specific_checkpoint_refuses_a_different_city():
    """GWNet's weights encode METR-LA's 207-sensor graph; pointing it at Dhaka is meaningless."""
    chk = GraphWaveNetAdapter("METR-LA").check(city(city_id="dhaka"))
    assert not chk["ok"]
    assert any("cannot forecast" in r or "trained on" in r for r in chk["reasons"])


def test_baseline_is_labelled_as_a_baseline():
    r = forecast(city(), [5, 15, 30, 60])
    assert r["is_baseline"] is True, "with no real model available the answer must be flagged"
    assert r["forecast"]["is_baseline"] is True


def test_refusals_are_reported_so_the_ui_can_explain_itself():
    r = forecast(city(), [15])
    assert r["refusals"], "a model that declined must say so"
    assert all(x["reasons"] for x in r["refusals"])


def test_every_model_appears_in_the_menu_with_a_verdict():
    menu = available_for(city())
    names = {m["model"] for m in menu}
    assert "OpenCity-plus" in names
    assert any(n.startswith("GWNet") for n in names)
    for m in menu:
        assert "available" in m
        if not m["available"]:
            assert m["reasons"], f"{m['model']} unavailable with no reason"


def test_not_available_carries_reasons():
    with pytest.raises(NotAvailable) as e:
        OpenCityAdapter().forecast(city(T=10), [15])
    assert e.value.reasons
