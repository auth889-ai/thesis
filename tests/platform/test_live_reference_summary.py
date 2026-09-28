from __future__ import annotations

import json
from pathlib import Path

from app.forecasting.live.summarize_live_reference import main


def test_live_reference_summary_uses_latest_unique_corridors(tmp_path: Path, monkeypatch):
    src = tmp_path / "google_routes_runtime_reference.jsonl"
    src.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "corridor_id": "a",
                    "captured_utc": "2026-09-01T00:00:00+00:00",
                    "request_latency_ms": 1.0,
                    "congestion_state": "SLOW",
                    "google_data_mode": "RUNTIME_REFERENCE",
                    "route_content_persisted": False,
                },
                {
                    "corridor_id": "a",
                    "captured_utc": "2026-09-01T01:00:00+00:00",
                    "request_latency_ms": 2.0,
                    "congestion_state": "CONGESTED",
                    "google_data_mode": "RUNTIME_REFERENCE",
                    "route_content_persisted": False,
                },
                {
                    "corridor_id": "b",
                    "captured_utc": "2026-09-01T01:00:01+00:00",
                    "request_latency_ms": 3.0,
                    "congestion_state": "FREE_FLOW",
                    "google_data_mode": "RUNTIME_REFERENCE",
                    "route_content_persisted": False,
                },
            ]
        )
        + "\n"
    )
    out_json = tmp_path / "summary.json"
    out_md = tmp_path / "summary.md"
    monkeypatch.setattr(
        "sys.argv",
        [
            "summarize_live_reference.py",
            "--source",
            str(src),
            "--out-json",
            str(out_json),
            "--out-md",
            str(out_md),
        ],
    )

    assert main() == 0
    summary = json.loads(out_json.read_text())
    assert summary["latest_corridors"] == 2
    assert summary["latest_congested_or_severe"] == 1
    assert summary["state_counts"] == {"CONGESTED": 1, "FREE_FLOW": 1}
    assert "route durations" in out_md.read_text()
