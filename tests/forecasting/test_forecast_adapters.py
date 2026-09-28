"""The forecast interface exists to stop two specific failures: presenting a baseline as the
system's prediction, and running a model on data it cannot honestly serve."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from traffictwin.forecasting.adapters.base import CityData, NotAvailable      # noqa: E402
from traffictwin.forecasting.adapters.baselines import PersistenceAdapter     # noqa: E402
from traffictwin.forecasting.adapters.checkpoint_models import GraphWaveNetAdapter  # noqa: E402
from traffictwin.forecasting.adapters.opencity import OpenCityAdapter          # noqa: E402
from traffictwin.forecasting.adapters.registry import available_for, forecast  # noqa: E402


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
    """Its Laplacian positional encoding takes 8 eigenvectors: 6 corridors cannot feed it, 12 can."""
    chk = OpenCityAdapter().check(city(T=400, N=6))
    assert not chk["ok"]
    assert any("eigenvectors" in r for r in chk["reasons"])
    ok12 = OpenCityAdapter().check(city(T=400, N=12))
    assert not any("nodes" in r for r in ok12["reasons"])


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
    """When only a floor can run, the answer must say so.

    A 4-step history is below every real model's minimum context, so persistence is genuinely all
    that is left — and that is exactly when mislabelling would be most misleading.
    """
    r = forecast(city(T=4, N=12), [5, 15])
    assert r["model_used"] is not None
    assert r["is_baseline"] is True, "with no real model available the answer must be flagged"
    assert r["forecast"]["is_baseline"] is True


def test_a_real_model_is_preferred_over_a_baseline_when_one_can_run():
    """The complement: with enough history, a pretrained model must win over the floor."""
    pytest.importorskip("chronos", reason="chronos-forecasting not installed")
    r = forecast(city(T=40, N=12), [15])
    assert r["is_baseline"] is False
    assert r["model_used"] == "Chronos-Bolt"


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


# --------------------------------------------------------------------------
# Chronos: the model that serves the cities the graph models must refuse.
# --------------------------------------------------------------------------

def _chronos():
    pytest.importorskip("chronos", reason="chronos-forecasting not installed")
    from traffictwin.forecasting.adapters.chronos_adapter import ChronosAdapter
    return ChronosAdapter()


def test_chronos_accepts_a_twelve_node_city_that_opencity_refuses():
    """The point of including it: a small city is not a deficient graph to a univariate model."""
    small = city(T=40, N=12)
    assert _chronos().check(small)["ok"] is True
    assert OpenCityAdapter().check(small)["ok"] is False


def test_chronos_still_refuses_too_short_a_context():
    """Serving small cities is not the same as serving no data."""
    chk = _chronos().check(city(T=3, N=12))
    assert not chk["ok"]
    assert any("observations" in r for r in chk["reasons"])


def test_chronos_is_not_labelled_a_baseline():
    ad = _chronos()
    assert ad.is_baseline is False
    f = ad.forecast(city(T=40, N=12), [15])
    assert f.is_baseline is False
    assert f.checkpoint, "a foundation model must report the checkpoint it used"


def test_chronos_returns_uncertainty_and_declares_its_blind_spot():
    f = _chronos().forecast(city(T=40, N=12), [15, 60])
    p = f.provenance
    assert p["lower_q10"] and p["upper_q90"], "quantiles are the point of using it"
    assert p["uses_road_graph"] is False, "it cannot see the network and must say so"
    assert p["pretraining_exposure"] == "UNVERIFIED", (
        "no zero-shot claim may be made without verifying the pre-training corpus")


# --------------------------------------------------------------------------
# Model selection must be explainable, and must never silently substitute.
# --------------------------------------------------------------------------

def test_selection_states_which_model_and_why():
    from traffictwin.forecasting.adapters.registry import select
    d = select(city(T=40, N=12))
    assert d["selected_model"], "something must be selected"
    assert d["reason"], "the choice must be explained"
    assert "candidates" in d and d["candidates"]


def test_a_requested_model_that_cannot_serve_is_refused_not_swapped():
    """The failure this prevents: asking for OpenCity and being handed persistence's answer
    under OpenCity's name."""
    from traffictwin.forecasting.adapters.registry import select
    d = select(city(T=40, N=12), requested="OpenCity-plus")
    assert d["selected_model"] is None
    assert "cannot serve" in d["reason"]
    assert d["requested_model"] == "OpenCity-plus"


def test_fallback_is_declared_and_names_what_was_skipped():
    from traffictwin.forecasting.adapters.registry import select
    pytest.importorskip("chronos", reason="chronos-forecasting not installed")
    d = select(city(T=40, N=12))
    assert d["fallback"] is True
    assert d["fallback_from"], "a fallback must name the models that could not serve"


def test_a_graph_capable_city_is_not_sent_to_the_univariate_model():
    """Ordering matters: where a spatio-temporal model can run, it should win."""
    from traffictwin.forecasting.adapters.registry import select
    d = select(city(T=40, N=12))
    assert d["selected_model"] != "persistence", "a real model must beat the floor when available"
