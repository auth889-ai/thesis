"""The operational model registry: grouped, gated, Automatic never picks by name."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _card(arch, dataset, val_mae, per_val, skill, verified=True, quality=True, family=None):
    return {"dataset": dataset, "bts_name": "DF_x", "arch": arch, "checkpoint": f"/tmp/{arch}_best.pt", "trained_utc": "2026-09-05T00:00:00+00:00",
            "quality": {"passed": quality}, "verification": {"passed": verified},
            "evaluation": {"validation": {arch: {"overall": {"MAE": val_mae}}, "persistence": {"overall": {"MAE": per_val}},
                                          "Chronos-Bolt": {"overall": {"MAE": 4.1}}, "historical_average": {"overall": {"MAE": 8.0}}},
                           "test": {arch: {"overall": {"MAE": val_mae, "skill_vs_persistence": skill}}, "persistence": {"overall": {"MAE": 7.0}},
                                    "Chronos-Bolt": {"overall": {"MAE": 6.5, "skill_vs_persistence": 0.13}}},
                           "validation_MAE": {arch: val_mae, "persistence": per_val, "Chronos-Bolt": 4.1}},
            "trust": {"eligible": skill >= 0.03 and verified and quality, "label": "ROUTING_ELIGIBLE" if skill >= 0.03 and verified and quality else "NOT_BETTER_THAN_BASELINE", "skill": skill},
            **({"family": family} if family else {})}


@pytest.fixture
def cards(monkeypatch):
    import model_registry as mr
    from pipeline.forecasting import basicts_train as bt
    store = []
    monkeypatch.setattr(bt, "cards", lambda: store)
    return store


def test_groups_and_automatic_pick_by_validation_among_fully_gated(cards):
    import model_registry as mr
    cards += [_card("GWNet", "user:x", 3.5, 6.4, 0.27),          # famous, lowest val MAE, passes everything
              _card("STID", "user:x", 3.9, 6.4, 0.26),
              _card("DCRNN", "user:x", 3.2, 6.4, 0.30, verified=False)]   # best val MAE but its checkpoint did not reproduce
    r = mr.registry("user:x")
    assert [g["key"] for g in r["groups"]] == ["recommended", "trained", "pretrained", "research"]
    assert r["automatic"]["model"] == "GWNet" and "validation" in r["automatic"]["why"]
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["DCRNN"]["eligible"] is False and by["DCRNN"]["gates"]["verified"] is False
    assert by["STAEformer"]["trained"] is False
    assert by["Chronos-Bolt"]["eligible"] is True and by["Chronos-Bolt"]["family"] == "pretrained"
    assert by["persistence"]["family"] == "research" and by["persistence"]["eligible"] is False


def test_automatic_falls_back_when_nothing_passes(cards):
    import model_registry as mr
    c = _card("STID", "user:y", 8.0, 6.4, -0.4)               # trained, but worse than persistence
    r = mr.registry("user:y") if not cards.append(c) else None
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert by["STID"]["trust"] == "NOT_BETTER_THAN_BASELINE" and by["STID"]["eligible"] is False
    assert r["automatic"]["model"] == "Chronos-Bolt"          # the pretrained model still passed its gates
    for split in ("validation", "test"):                      # without a passing pretrained score: the floor, and it says so
        c["evaluation"][split].pop("Chronos-Bolt", None)
    r = mr.registry("user:y")
    assert r["automatic"]["model"] == "persistence" and "fallback" in r["automatic"]["why"]


def test_resolve_maps_auto_and_names(cards):
    import model_registry as mr
    cards += [_card("STID", "user:z", 3.9, 6.4, 0.2)]
    assert mr.resolve("user:z", "auto")["model"] == "STID"
    assert mr.resolve("user:z", "STID")["checkpoint"] == "STID_best.pt"
    assert mr.resolve("user:z", "nonsense")["eligible"] is False


def test_live_city_scope_offers_no_trained_models(cards):
    import model_registry as mr
    r = mr.registry("dhaka")
    by = {e["model"]: e for g in r["groups"] for e in g["items"]}
    assert all(by[m]["trained"] is False for m in ("STID", "GWNet", "STAEformer", "DCRNN"))
    assert r["n_trained"] == 0


def test_registry_endpoint(client):
    r = client.get("/api/registry?scope=user:does_not_exist").json()
    assert r["scope"] == "user:does_not_exist" and r["automatic"]["model"] == "persistence"
    assert [g["title"] for g in r["groups"]] == ["Recommended", "Trained on your city", "Pretrained", "Compare models / Research"]


def test_dataset_moment_matches_weekday_and_time():
    import dataset_ops
    meta = {"steps": 288 * 14, "interval_s": 300, "first_utc": "2012-03-01T00:00:00+00:00"}   # Thu 1 Mar 2012
    idx, when = dataset_ops.moment_for(meta, "2026-09-05T17:30:00+00:00")                   # a Saturday 17:30
    from datetime import datetime
    d = datetime.fromisoformat(when)
    assert d.weekday() == 5 and d.hour == 17 and d.minute == 30 and idx < 288 * 14 - 12
