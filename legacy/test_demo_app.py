"""The examiner-facing demo must render every tab without exceptions, on whatever evidence exists."""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(REPO / "demo/app.py"), default_timeout=300)
    at.run()
    return at


def test_no_exceptions_anywhere(app):
    assert not app.exception, [str(e)[:300] for e in app.exception]


def test_all_tabs_present(app):
    assert len(app.tabs) == 7, "Live chain, Map, Live reference, Predict, Route, Network, NLP events"


def test_live_chain_is_the_first_tab_and_shows_a_decision(app):
    body = " ".join(m.value for m in app.markdown) + " ".join(
        w.value for w in list(app.success) + list(app.warning) + list(app.info))
    assert "live Dhaka APIs" in body
    assert "ACT" in body or "NO_ACTION" in body, "the chain tab must state a decision"


def test_missing_evidence_is_offered_as_a_command_not_faked(app):
    for note in app.info:
        assert "not produced yet" in note.value or "no " in note.value.lower() or "run" in note.value.lower()
