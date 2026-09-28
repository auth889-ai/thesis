from __future__ import annotations

import json
from pathlib import Path

from research.reports.evidence_audit import build_report


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_evidence_audit_fails_failed_twin_manifest(tmp_path: Path):
    _write(
        tmp_path / "data/forecasting/dhaka_twin/MANIFEST.json",
        {
            "label": "DHAKA_SIMULATED_SENSOR_GRAPH",
            "seeds": [11, 12, 13],
            "acceptance": {"verdict": "FAIL"},
            "data_npz": {"data_shape": [288, 250, 5]},
        },
    )

    report = build_report(tmp_path)
    twin = [r for r in report["rows"] if r["name"] == "Dhaka twin prediction data"][0]

    assert twin["status"] == "FAIL"
    assert report["overall_status"] == "FAIL"


def test_evidence_audit_passes_core_local_evidence_with_colab_pending(tmp_path: Path):
    _write(
        tmp_path / "data/forecasting/dhaka_twin/MANIFEST.json",
        {
            "label": "DHAKA_SIMULATED_SENSOR_GRAPH",
            "seeds": [11, 12, 13],
            "acceptance": {"verdict": "PASS"},
            "data_npz": {"data_shape": [288, 250, 5]},
        },
    )
    _write(
        tmp_path / "results/forecasting/twin_floors.json",
        {"models": {"persistence": {}, "historical_average": {}}, "horizons_min": [5, 15, 30, 60]},
    )
    _write(
        tmp_path / "results/routing/decision_guard.json",
        {
            "decision": "ACT",
            "selected_arm": "predictive_persistence",
            "selected_mean_total_vehicle_hours_benefit_pct": 10.0,
            "deployable_evaluations": [{"accepted": True}],
        },
    )
    _write(
        tmp_path / "results/artifacts/p_live/live_reference_summary.json",
        {
            "honesty_label": "EXTERNAL_LIVE_REFERENCE_NOT_TRAINING_DATA",
            "latest_corridors": 1,
            "state_counts": {"SLOW": 1},
            "latest": [{"route_content_persisted": False}],
        },
    )
    (tmp_path / "results/networking").mkdir(parents=True)
    (tmp_path / "results/networking/penetration.csv").write_text("p,seed\n0.5,11\n")
    _write(tmp_path / "results/nlp/classifier.json", {"accuracy": 0.9})

    report = build_report(tmp_path)
    statuses = {r["name"]: r["status"] for r in report["rows"]}

    assert statuses["Dhaka twin prediction data"] == "PASS"
    assert statuses["Colab BasicTS benchmark"] == "PENDING"
    assert report["overall_status"] == "PASS_WITH_PENDING_ITEMS"
