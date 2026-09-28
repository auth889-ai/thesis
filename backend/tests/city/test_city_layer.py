"""The city layer's job is to let ANY city exist as software while refusing to let a city claim
more than its data supports. Both halves are tested here."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.data.datasets import catalog                       # noqa: E402
from app.data.cities import CityRegistry, slug            # noqa: E402
from app.data.city_spec import Capability, CityCapabilities, CitySpec  # noqa: E402


def test_a_city_with_only_a_live_feed_cannot_claim_a_forecast():
    cap = CityCapabilities(has_live_provider=True)
    assert cap.best is Capability.LIVE_ONLY
    assert Capability.ZERO_SHOT not in cap.granted
    assert Capability.FULL_FORECAST not in cap.granted


def test_a_pretraining_city_can_never_be_zero_shot():
    """METR-LA is inside OpenCity's pre-training corpus. No result may be labelled zero-shot."""
    cap = CityCapabilities(has_historical_dataset=True, in_foundation_pretraining=True,
                           schema_satisfies_foundation=True)
    assert Capability.ZERO_SHOT not in cap.granted


def test_held_out_but_too_small_is_still_refused():
    """Absent from the corpus is necessary for zero-shot, never sufficient — the data must also
    satisfy the model's input schema. This is the check that stops OpenCity being run on 12
    corridors and the number being believed."""
    cap = CityCapabilities(has_historical_dataset=True, in_foundation_pretraining=False,
                           schema_satisfies_foundation=False, dataset_nodes=12)
    assert Capability.ZERO_SHOT not in cap.granted


def test_held_out_and_valid_earns_zero_shot():
    cap = CityCapabilities(has_historical_dataset=True, in_foundation_pretraining=False,
                           schema_satisfies_foundation=True, dataset_nodes=228)
    assert Capability.ZERO_SHOT in cap.granted


def test_catalog_marks_dhaka_unusable_for_the_foundation_model():
    c = catalog()
    assert c["DHAKA-LIVE"]["opencity_schema_ok"] is False
    assert c["DHAKA-LIVE"]["opencity_schema_blocking"], "must say WHY it is unusable"
    assert c["PEMS07M"]["opencity_schema_ok"] is True


def test_catalog_records_pretraining_exposure_for_every_dataset():
    for name, e in catalog().items():
        assert "exposure" in e, f"{name} has no exposure label"
        assert "comparable_protocols" in e, "protocol mismatch must be stated on every entry"


def test_registry_creates_a_city_that_is_in_no_source_file(tmp_path):
    """The whole point of the layer: a city nobody hard-coded."""
    r = CityRegistry(root=tmp_path)
    spec = r.create_from_bbox("Nowhere City", (10.0, 20.0, 10.5, 20.5))
    assert spec.city_id == "nowhere_city"
    assert r.get("nowhere_city") is not None
    assert r.get("nowhere_city").center == (10.25, 20.25)
    assert "nowhere_city" in r.list_ids()


def test_a_new_city_defaults_to_live_only_not_to_a_forecast(tmp_path):
    r = CityRegistry(root=tmp_path)
    r.create_from_bbox("Somewhere", (1.0, 2.0, 1.1, 2.1))
    d = r.describe("somewhere", catalog())
    assert d["forecast_capability"] == "LIVE_ONLY"
    assert d["capabilities"]["blocking"], "a city with no data must say what is missing"


def test_slug_is_stable():
    assert slug("São Paulo, Brazil") == slug("São Paulo, Brazil")
    assert slug("New York City") == "new_york_city"


# --------------------------------------------------------------------------
# Generic SUMO: any instantiated city can become a scenario — labelled honestly.
# --------------------------------------------------------------------------

def test_generated_scenarios_are_labelled_synthetic():
    """A generated scenario has a REAL network and INVENTED demand. Conflating the two is how a
    mechanism demo gets quoted as a measurement of a city's traffic."""
    import json
    from app.twin.scenario_builder import scenario_dir
    m = scenario_dir("nairobi_kenya") / "MANIFEST.json"
    if not m.exists():
        pytest.skip("no generated scenario on this machine")
    d = json.loads(m.read_text())
    assert d["label"] == "SYNTHETIC_WHAT_IF"
    assert d["demand_reality"] == "SYNTHETIC_WHAT_IF"
    assert "REAL" in d["network_reality"], "the network genuinely is OSM geometry"
    assert "never be quoted alongside" in d["warning"]


def test_calibrated_cases_are_not_produced_by_the_generic_path():
    """Dhaka R1 and Athens pNEUMA are separate evidence and must not be regenerated as synthetic."""
    from app.twin.scenario_builder import CALIBRATED
    assert "dhaka_r1" in CALIBRATED and "athens_pneuma" in CALIBRATED
