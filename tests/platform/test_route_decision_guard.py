from __future__ import annotations

import json
from pathlib import Path

from app.routing.decision_guard import compare_arm, main


def _m(total: float, arrived: int, teleports: int) -> dict:
    return {
        "total_vehicle_hours": total,
        "mean_travel_time_all": total,
        "total_waiting_s": total * 10,
        "arrived": arrived,
        "teleports": teleports,
    }


def test_compare_arm_accepts_only_all_seed_network_improvement():
    ref = {str(s): _m(100.0, 90, 5) for s in (11, 12, 13)}
    cand = {str(s): _m(80.0, 95, 2) for s in (11, 12, 13)}

    ev = compare_arm("predictive", cand, ref)

    assert ev["accepted"] is True
    assert ev["mean_benefit_pct"]["total_vehicle_hours"] == 20.0
    assert ev["mean_benefit_pct"]["arrived"] > 0
    assert ev["mean_benefit_pct"]["teleports"] > 0


def test_compare_arm_rejects_one_bad_seed():
    ref = {str(s): _m(100.0, 90, 5) for s in (11, 12, 13)}
    cand = {
        "11": _m(80.0, 95, 2),
        "12": _m(80.0, 95, 2),
        "13": _m(120.0, 95, 2),
    }

    ev = compare_arm("predictive", cand, ref)

    assert ev["accepted"] is False
    bad_seed = [row for row in ev["per_seed"] if row["seed"] == 13][0]
    assert bad_seed["total_vehicle_hours"]["improved"] is False


def test_compare_arm_rejects_less_than_three_paired_seeds():
    ref = {str(s): _m(100.0, 90, 5) for s in (11, 12)}
    cand = {str(s): _m(80.0, 95, 2) for s in (11, 12)}

    assert compare_arm("predictive", cand, ref)["accepted"] is False


def test_main_writes_decision_artifacts(tmp_path: Path, monkeypatch):
    results = tmp_path / "results"
    results.mkdir()
    arms = {
        "reactive": {str(s): {"metrics": _m(100.0, 90, 5)} for s in (11, 12, 13)},
        "predictive_persistence": {str(s): {"metrics": _m(80.0, 95, 2)} for s in (11, 12, 13)},
        "predictive_oracle": {str(s): {"metrics": _m(70.0, 97, 1)} for s in (11, 12, 13)},
        "due": {str(s): {"metrics": _m(60.0, 98, 1)} for s in (11, 12, 13)},
    }
    (results / "arms_h900.json").write_text(json.dumps(arms))
    monkeypatch.setattr(
        "sys.argv",
        ["decision_guard.py", "--horizon", "900", "--reference", "reactive", "--results", str(results)],
    )

    assert main() == 0
    decision = json.loads((results / "decision_guard_h900.json").read_text())
    assert decision["decision"] == "ACT"
    assert decision["selected_arm"] == "predictive_persistence"
    assert (results / "decision_guard.md").exists()
