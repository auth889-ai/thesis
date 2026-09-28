from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PY = sys.executable
BANNED = {
    "duration_s",
    "static_duration_s",
    "distance_m",
    "distanceMeters",
    "polyline",
    "encodedPolyline",
    "speedReadingIntervals",
}


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([PY, *args], cwd=REPO, capture_output=True, text=True)


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def assert_no_google_content(row: dict) -> None:
    text = json.dumps(row)
    assert row["google_data_mode"] == "RUNTIME_REFERENCE"
    assert row["route_content_persisted"] is False
    assert not (set(row) & BANNED)
    assert not any(key in text for key in BANNED)


def test_route_advisor_dry_run_persists_only_compliant_metadata(tmp_path):
    out = tmp_path / "advice.jsonl"
    result = run("-m", "traffictwin.optimization.route_advisor", "--dry-run", "--corridor", "farmgate_to_shahbagh", "--out", str(out))
    assert result.returncode == 0, result.stderr + result.stdout[-800:]
    rows = read_jsonl(out)
    assert len(rows) == 1
    row = rows[0]
    assert row["reality"] == "FIXTURE"
    assert row["route_count"] >= 2
    assert row["recommended_congestion_state"] in {"FREE_FLOW", "SLOW", "CONGESTED", "SEVERE", "UNKNOWN"}
    assert row["advice_id"]
    assert_no_google_content(row)


def test_route_advisor_live_requires_yes(tmp_path):
    out = tmp_path / "advice.jsonl"
    result = run("-m", "traffictwin.optimization.route_advisor", "--live", "--corridor", "farmgate_to_shahbagh", "--out", str(out))
    assert result.returncode == 2
    assert not out.exists()


def test_pilot_trip_start_complete_and_summary(tmp_path):
    log = tmp_path / "pilot.jsonl"
    result = run(
        "-m", "traffictwin.data.user_trips", "start",
        "--participant", "person-a",
        "--advice-id", "adv123",
        "--corridor", "farmgate_to_shahbagh",
        "--started-utc", "2026-09-01T10:00:00+00:00",
        "--log", str(log),
    )
    assert result.returncode == 0, result.stderr
    trip_id = json.loads(result.stdout)["trip_id"]
    result = run(
        "-m", "traffictwin.data.user_trips", "complete",
        "--trip-id", trip_id,
        "--arrived-utc", "2026-09-01T10:18:30+00:00",
        "--log", str(log),
        "--out-json", str(tmp_path / "metrics.json"),
        "--out-md", str(tmp_path / "metrics.md"),
    )
    assert result.returncode == 0, result.stderr
    rows = read_jsonl(log)
    assert [r["event"] for r in rows] == ["start", "complete"]
    for row in rows:
        assert_no_google_content(row)
    metrics = json.loads((tmp_path / "metrics.json").read_text())
    assert metrics["completed_trips"] == 1
    assert metrics["participants"] == 1
    assert metrics["mean_actual_elapsed_s"] == 1110.0
    assert_no_google_content(metrics)
