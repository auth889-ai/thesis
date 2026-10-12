"""The network model: sourced parameters only, deterministic, and honest about range."""
import random

import pytest
import yaml

from core.networking.v2x import model
from core.networking.v2x.model import Station, deliver

A, NEAR, FAR = Station("a", 0, 0), Station("b", 100, 0), Station("c", 5000, 0)


def test_same_seed_same_answers():
    run = lambda: [deliver(A, NEAR, t, "its_g5", random.Random(7)).delivered for t in range(50)]
    assert run() == run()
    many = random.Random(3)
    got = [deliver(A, NEAR, 0, "its_g5", many).delivered for _ in range(2000)]
    assert 0.87 < sum(got) / len(got) < 0.93                       # the stated delivery ratio, 0.90


def test_nothing_is_delivered_beyond_range():
    for tech in ("its_g5", "c_v2x"):
        d = deliver(A, FAR, 0, tech, random.Random(1))
        assert not d.delivered and d.reason == model.OUT_OF_RANGE and d.delay_s is None


def test_ideal_delivers_everything_at_once_and_none_delivers_nothing():
    rng = random.Random(0)
    assert all(deliver(A, s, 0, "ideal", rng) == model.Delivery(True, 0.0, model.IN_RANGE) for s in (NEAR, FAR))
    assert not any(deliver(A, s, 0, "none", rng).delivered for s in (A, NEAR, FAR))


def test_a_parameter_without_a_source_refuses_the_technology_by_name(tmp_path):
    cfg = yaml.safe_load(model.CONFIG.read_text())
    cfg["technologies"]["its_g5"]["range_m"] = {"value": 425.0, "source": None}
    cfg["technologies"]["c_v2x"]["delay_s"]["value"] = None
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(cfg))
    with pytest.raises(model.Refused, match="its_g5.*range_m"):
        deliver(A, NEAR, 0, "its_g5", random.Random(0), p)
    with pytest.raises(model.Refused, match="c_v2x.*delay_s"):
        deliver(A, NEAR, 0, "c_v2x", random.Random(0), p)
    with pytest.raises(model.Refused, match="unknown technology"):
        deliver(A, NEAR, 0, "smoke_signals", random.Random(0))


def test_every_value_in_the_config_has_a_source_or_is_null():
    cfg = yaml.safe_load(model.CONFIG.read_text())
    entries = [e for t in cfg["technologies"].values() for k, e in t.items() if k != "provenance"] + list(cfg["message"].values())
    assert all(e["value"] is None or e["source"] for e in entries)
    assert all(t.get("provenance") for n, t in cfg["technologies"].items() if n not in ("ideal", "none")), "every real technology says where its figures come from"
    assert model.usable()["its_g5"] == [] and model.usable()["c_v2x"] == []
    assert model.usable()["cellular_4g"] == []                               # since 2026-10-06: the delivery ratio is read from Xu et al. 2017
    assert "Xu" in cfg["technologies"]["cellular_4g"]["delivery_ratio_in_range"]["source"]


def test_delay_counts_every_radio_leg():
    cfg = yaml.safe_load(model.CONFIG.read_text())["technologies"]
    rng = random.Random(2)
    d = next(x for x in (deliver(A, NEAR, 0, "c_v2x", rng) for _ in range(50)) if x.delivered)
    assert d.delay_s == cfg["c_v2x"]["delay_s"]["value"] * cfg["c_v2x"]["hops"]["value"]
