from __future__ import annotations

import json
from pathlib import Path

from demo.evidence import horizon_from_arms_file, latest_arms_file, read_jsonl


def test_horizon_from_arms_file():
    assert horizon_from_arms_file(Path("arms_h7200.json")) == 7200
    assert horizon_from_arms_file(Path("arms_h900.json")) == 900
    assert horizon_from_arms_file(Path("arms_latest.json")) == -1


def test_latest_arms_file_uses_numeric_horizon(tmp_path: Path):
    results = tmp_path / "results/routing"
    results.mkdir(parents=True)
    for name in ("arms_h900.json", "arms_h1800.json", "arms_h7200.json"):
        (results / name).write_text("{}")

    assert latest_arms_file(tmp_path) == results / "arms_h7200.json"


def test_read_jsonl_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"a": 1}) + "\n\n" + json.dumps({"b": 2}) + "\n")

    assert read_jsonl(path) == [{"a": 1}, {"b": 2}]
