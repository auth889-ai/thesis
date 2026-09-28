"""The backend under test: no live sampling, no scheduler, a throw-away forecast ledger."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
os.environ["DHAKAFLOW_NO_OBSERVATORY"] = "1"
for p in (str(REPO), str(REPO / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def app():
    from app.main import app as application
    return application


@pytest.fixture
def client(app, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from traffictwin.protocols.evidence import forecast_ledger as forecast_log
    monkeypatch.setattr(forecast_log, "DB", tmp_path / "ledger.sqlite")
    with TestClient(app) as c:
        yield c
