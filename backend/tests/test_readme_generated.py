"""README.md and docs/PAPER_MAP.md are generated from the summary files (scripts/readme/build.py, scripts/paper_map/build.py): a hand
edit, or a summary that changed without a rebuild, fails here."""
from __future__ import annotations

import subprocess
import sys

from core.common.paths import REPO


def _check(script: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPO / script), "--check"], capture_output=True, text=True, cwd=REPO)


def test_readme_matches_its_generator():
    r = _check("scripts/readme/build.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_paper_map_and_protocol_table_match_their_generator():
    r = _check("scripts/paper_map/build.py")
    assert r.returncode == 0, r.stdout + r.stderr


def test_readme_puts_the_research_before_the_app():
    text = (REPO / "README.md").read_text()
    order = ["## Why", "## Research questions", "## ML", "## Networking and safety", "## Limitations", "## Repository layout", "## Quick start",
             "## The system that applies the research"]
    assert [text.index(h) for h in order] == sorted(text.index(h) for h in order)
    for rq in ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6"):
        assert f"### {rq} ·" in text
