"""The operational model registry: grouped, gated, Automatic never picks by name."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _card(arch, dataset, val_mae, per_val, skill, verified=True, quality=True, family=None):
    return {"dataset": dataset, "bts_name": "DF_x", "arch": arch, "checkpoint": f"/tmp/{arch}_best.pt", "trained_utc": "2026-09-05T00:00:00+00:00",
            "quality": {"passed": quality}, "verification": {"passed": verified},
            "evaluation": {"validation": {arch: {"overall": {"MAE": val_mae}}, "persistence": {"overall": {"MAE": per_val}},
                                          "Chronos-Bolt": {"overall": {"MAE": 4.1}, "full_split": True}, "historical_average": {"overall": {"MAE": 8.0}}},
                           "test": {arch: {"overall": {"MAE": val_mae, "skill_vs_persistence": skill}}, "persistence": {"overall": {"MAE": 7.0}},
                                    "Chronos-Bolt": {"overall": {"MAE": 6.5, "skill_vs_persistence": 0.13}}},
                           "validation_MAE": {arch: val_mae, "persistence": per_val, "Chronos-Bolt": 4.1}},
            "trust": {"eligible": skill >= 0.03 and verified and quality, "label": "ROUTING_ELIGIBLE" if skill >= 0.03 and verified and quality else "NOT_BETTER_THAN_BASELINE", "skill": skill},
            **({"family": family} if family else {})}


@pytest.fixture
def cards(monkeypatch):
    from app.forecasting.operations import model_registry as mr
    from app.forecasting.training import basicts_train as bt
    store = []
    monkeypatch.setattr(bt, "cards", lambda: store)
    return store


def test_groups_and_automatic_pick_by_validation_among_fully_gated(cards):
    from app.forecasting.operations import model_registry as mr
    cards += [_card("GWNet", "user:x", 3.5, 6.4, 0.27),          # famous, lowest val MAE, passes everything
              _card("STID", "user:x", 3.9, 6.4, 0.26),
              _card("DCRNN", "user:x", 3.2, 6.4, 0.30, verified=False)]   # best val MAE but its checkpoint did not reproduce
    r = mr.registry("user:x")
    assert [g["key"] for g in r["groups"]] == ["recommended", "available", "validated", "pretrained", "baselines", "unavailable"]
    assert r["automatic"]["model"] == "GWNet" and r["forecast"]["status"] == "VALIDATED" and r["routing"]["policy"] == "PREDICTION_AWARE"
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["DCRNN"]["eligible"] is False and by["DCRNN"]["gates"]["verified"] is False
    assert by["STAEformer"]["trained"] is False
    assert by["Chronos-Bolt"]["eligible"] is True and by["Chronos-Bolt"]["family"] == "pretrained"
    assert by["persistence"]["family"] == "research" and by["persistence"]["eligible"] is False


def test_automatic_falls_back_when_nothing_passes(cards):
    from app.forecasting.operations import model_registry as mr
    c = _card("STID", "user:y", 8.0, 6.4, -0.4)               # trained, but worse than persistence
    cards.append(c)
    r = mr.registry("user:y")
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["STID"]["trust"] == "NOT_BETTER_THAN_BASELINE" and by["STID"]["eligible"] is False
    assert r["forecast"]["model"] == "Chronos-Bolt" and r["forecast"]["status"] == "VALIDATED"   # the pretrained model passed its gates here
    for split in ("validation", "test"):                      # without a validated pretrained score:
        c["evaluation"][split].pop("Chronos-Bolt", None)
    r = mr.registry("user:y")
    # priority: an available pretrained forecast-only model outranks a trained model that failed its gate;
    # routing falls back; persistence is never presented as the AI forecast
    assert r["forecast"]["model"] in ("Chronos-2", "Chronos-Bolt") and r["forecast"]["status"] == "FORECAST_ONLY"   # unscored zero-shot models tie; the newest is first
    assert r["routing"]["policy"] == "REACTIVE_FALLBACK" and r["automatic"]["model"] == r["forecast"]["model"]
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["STID"]["status"] == "AVAILABLE" and by["STID"]["can_forecast"] is True     # still selectable manually, forecast-only

def test_resolve_maps_auto_and_names(cards):
    from app.forecasting.operations import model_registry as mr
    cards += [_card("STID", "user:z", 3.9, 6.4, 0.2)]
    assert mr.resolve("user:z", "auto")["model"] == "STID"
    assert mr.resolve("user:z", "STID")["checkpoint"] == "STID_best.pt"
    assert mr.resolve("user:z", "nonsense")["eligible"] is False


def test_live_city_scope_offers_no_trained_models(cards):
    from app.forecasting.operations import model_registry as mr
    r = mr.registry("dhaka")
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert all(by[m]["trained"] is False for m in ("STID", "GWNet", "STAEformer", "DCRNN"))
    assert r["n_trained"] == 0


def test_registry_endpoint(client):
    r = client.get("/api/registry?scope=user:does_not_exist").json()
    assert r["scope"] == "user:does_not_exist" and r["forecast"]["model"] in ("Chronos-2", "Chronos-Bolt", "persistence")   # the newest released zero-shot model is the default
    assert [g["title"] for g in r["groups"]] == ["Recommended", "Available", "Validated on this city", "Pretrained", "Baselines", "Unavailable"]
    assert r["routing"]["policy"] == "REACTIVE_FALLBACK"


def test_live_city_forecast_is_chronos_not_persistence(cards, monkeypatch):
    """A city with corridor history but no permitted local validation set: the AI forecast is the
    pretrained model (forecast-only), persistence is never presented as the AI forecast, and
    routing stays reactive."""
    from app.forecasting.operations import model_registry as mr
    monkeypatch.setattr(mr, "_live_availability", lambda scope: {"Chronos-Bolt": (True, []), "OpenCity-plus": (False, ["graph has 6 nodes; needs 9"])})
    r = mr.registry("dhaka")
    assert r["forecast"]["model"] == "Chronos-Bolt" and r["forecast"]["status"] == "FORECAST_ONLY" and r["forecast"]["local_validation"] == "UNAVAILABLE"
    assert r["routing"]["policy"] == "REACTIVE_FALLBACK" and r["routing"]["trusted_model"] is None
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["OpenCity-plus"]["status"] == "UNAVAILABLE" and by["Chronos-Bolt"]["status"] == "AVAILABLE"
    assert mr.resolve("dhaka", "auto")["model"] == "Chronos-Bolt"


def test_validated_upload_flips_automatic_without_restart(cards):
    """Registry reads the cards on every call: once a validated card exists, Automatic changes."""
    from app.forecasting.operations import model_registry as mr
    r0 = mr.registry("user:flip")
    assert r0["routing"]["policy"] == "REACTIVE_FALLBACK"
    cards.append(_card("GWNet", "user:flip", 3.5, 6.4, 0.27))
    r1 = mr.registry("user:flip")
    assert r1["forecast"]["model"] == "GWNet" and r1["forecast"]["status"] == "VALIDATED" and r1["routing"]["policy"] == "PREDICTION_AWARE"


def test_dataset_moment_matches_weekday_and_time():
    from app.data import forecast_inputs as dataset_ops
    meta = {"steps": 288 * 14, "interval_s": 300, "first_utc": "2012-03-01T00:00:00+00:00"}   # Thu 1 Mar 2012
    idx, when = dataset_ops.moment_for(meta, "2026-09-05T17:30:00+00:00")                   # a Saturday 17:30
    from datetime import datetime
    d = datetime.fromisoformat(when)
    assert d.weekday() == 5 and d.hour == 17 and d.minute == 30 and idx < 288 * 14 - 12
