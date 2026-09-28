"""Canonical forecasting and research-status contracts are evidence-derived, never hard-coded."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def test_gwnet_contract_is_tied_to_held_out_metr_la_evidence():
    from traffictwin.forecasting import ModelRegistry

    spec = ModelRegistry.metr_la_gwnet().public()
    assert spec["model"] == "GWNet" and spec["dataset"] == "METR-LA"
    assert spec["graph_size"] == 207 and spec["input_shape"] == [1, 12, 207, 1]
    assert spec["validation_status"] == "FORECAST_VALIDATED"
    assert all(v > 0 for v in spec["skill_vs_persistence"].values())


def test_research_status_keeps_negative_and_dhaka_not_ready_states():
    from traffictwin.research_status import compute_research_status

    gates = compute_research_status()["gates"]
    assert gates["FORECAST_VALIDATED"]["status"] == "PASSED"
    assert gates["VALID_TRAFFIC_STRESS_CASE"]["status"] == "PASSED"
    assert gates["FUTURE_INFORMATION_VALUE"]["status"] == "ESTABLISHED"
    assert gates["PREDICTIVE_CONTROL_VS_REACTIVE"]["status"] == "ESTABLISHED"
    assert gates["LEARNED_FORECAST_ADVANTAGE_VS_PERSISTENCE"]["status"] == "NOT_ESTABLISHED"
    assert gates["DHAKA_DEPLOYMENT_READY"]["status"] == "NOT_READY"
    assert gates["PREDICTIVE_TRAFFIC_BENEFIT"]["status"] == "NOT_ESTABLISHED"


def test_control_gates_fail_closed_with_incomplete_or_invalid_pairs(monkeypatch):
    import copy
    import traffictwin.research_status as status

    original_read = status._read
    for corruption in ("missing_seed", "duplicate_seed", "nan"):
        def read(path):
            result = copy.deepcopy(original_read(path))
            if path.name == "report.json" and result and "per_seed" in result:
                if corruption == "missing_seed":
                    result["per_seed"].pop()
                elif corruption == "duplicate_seed":
                    result["per_seed"].append(result["per_seed"][0])
                else:
                    result["per_seed"][0]["arms"]["predictive_v2x"]["metrics"]["total_vehicle_hours_incl_never_inserted"] = float("nan")
            return result
        monkeypatch.setattr(status, "_read", read)
        assert status.compute_research_status()["gates"]["PREDICTIVE_CONTROL_VS_REACTIVE"]["status"] == "NOT_ESTABLISHED"
