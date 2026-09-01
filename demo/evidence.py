"""Artifact loading helpers for the Streamlit demo."""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path
from typing import Any


def horizon_from_arms_file(path: Path) -> int:
    m = re.search(r"arms_h(\d+)\.json$", path.name)
    return int(m.group(1)) if m else -1


def latest_arms_file(repo: Path) -> Path | None:
    files = [Path(p) for p in glob.glob(str(repo / "route/results/arms_h*.json"))]
    return max(files, key=horizon_from_arms_file) if files else None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
