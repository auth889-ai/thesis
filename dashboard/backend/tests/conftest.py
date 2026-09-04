"""The backend under test: no live sampling, no scheduler, a throw-away forecast ledger."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parents[1]
os.environ["DHAKAFLOW_NO_OBSERVATORY"] = "1"
for p in (str(BACKEND), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def app():
    # the repo root also has a main.py (the CLI); when the whole tree runs in one session it may
    # already sit in sys.modules, so the backend's must be loaded by name from its own directory
    import importlib
    if str(BACKEND) != sys.path[0]:
        sys.path.remove(str(BACKEND))
        sys.path.insert(0, str(BACKEND))
    m = sys.modules.get("main")
    if m is None or not hasattr(m, "app"):
        sys.modules.pop("main", None)
        m = importlib.import_module("main")
    assert hasattr(m, "app"), f"loaded the wrong main: {getattr(m, '__file__', m)}"
    return m.app


@pytest.fixture
def client(app, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import forecast_log
    monkeypatch.setattr(forecast_log, "DB", tmp_path / "ledger.sqlite")
    with TestClient(app) as c:
        yield c
