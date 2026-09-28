"""The live Dhaka recorder: schema, compliance, resilience. No network, no cost."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from traffictwin.forecasting.live import record_live as rec  # noqa: E402
from traffictwin.data.live_providers.google_providers import GoogleDataPolicy  # noqa: E402
from traffictwin.data.live_providers.providers import DHAKA_R1_CORRIDORS, ObservationStore  # noqa: E402

PY = sys.executable
ALLOWED = {"corridor_id", "captured_utc", "request_latency_ms", "congestion_state",
           "google_data_mode", "route_content_persisted"}
GOOGLE_CONTENT = {"duration", "staticDuration", "distanceMeters", "speedReadingIntervals",
                  "polyline", "duration_s", "static_duration_s", "distance_m", "route_ref"}


def run(tmp: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([PY, "-m", "traffictwin.forecasting.live.record_live", "--out", str(tmp), *args],
                          capture_output=True, text=True)


def series(tmp: Path) -> list[dict]:
    f = tmp / "normalized/google_routes_runtime_reference.jsonl"
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


def test_dry_run_writes_one_row_per_corridor_per_tick(tmp_path):
    r = run(tmp_path, "--dry-run", "--interval", "1", "--ticks", "3")
    assert r.returncode == 0, r.stderr[-600:]
    rows = series(tmp_path)
    assert len(rows) == 3 * len(DHAKA_R1_CORRIDORS)
    man = json.loads((tmp_path / "RECORDER_MANIFEST.json").read_text())
    assert man["ticks"] == 3 and man["rows_ok"] == len(rows) and man["rows_failed"] == 0
    assert man["reality"] == "FIXTURE" and man["google_data_mode"] == "RUNTIME_REFERENCE"


def test_no_google_content_is_ever_persisted(tmp_path):
    """The compliance guarantee: only derived verdicts + metadata reach disk."""
    assert run(tmp_path, "--dry-run", "--interval", "1", "--ticks", "2").returncode == 0
    rows = series(tmp_path)
    for row in rows:
        assert set(row) <= ALLOWED, f"unexpected field persisted: {set(row) - ALLOWED}"
        assert not (set(row) & GOOGLE_CONTENT)
        assert row["route_content_persisted"] is False
        assert row["congestion_state"] in {"FREE_FLOW", "SLOW", "CONGESTED", "SEVERE", "UNKNOWN"}
    assert not (tmp_path / "raw").exists() or not any((tmp_path / "raw").iterdir())


def test_live_requires_explicit_confirmation(tmp_path):
    """--live must never start silently: it costs money."""
    r = run(tmp_path, "--live", "--ticks", "1")
    assert r.returncode == 2 and "--yes" in r.stdout
    assert not (tmp_path / "normalized/google_routes_runtime_reference.jsonl").exists()
    r = run(tmp_path)                                  # neither flag -> argparse error
    assert r.returncode != 0 and "--live" in r.stderr


def test_a_failing_corridor_is_logged_not_fabricated(tmp_path):
    class Boom:
        def edge_state(self, *a, **k):
            raise RuntimeError("quota exceeded")
    store = ObservationStore(tmp_path)
    rows = rec.tick(Boom(), list(DHAKA_R1_CORRIDORS)[:2], store, "FIXTURE")
    assert len(rows) == 2 and all(r["ok"] is False for r in rows)
    errs = [json.loads(l) for l in (tmp_path / "normalized/recorder_errors_runtime_reference.jsonl").read_text().splitlines()]
    assert len(errs) == 2 and "quota exceeded" in errs[0]["error"]
    assert not (tmp_path / "normalized/google_routes_runtime_reference.jsonl").exists()


def test_congestion_bucket_boundaries():
    p = GoogleDataPolicy()
    assert p.congestion_bucket(100, 100) == "FREE_FLOW"
    assert p.congestion_bucket(120, 100) == "SLOW"
    assert p.congestion_bucket(160, 100) == "CONGESTED"
    assert p.congestion_bucket(250, 100) == "SEVERE"
    assert p.congestion_bucket(100, 0) == "UNKNOWN"
