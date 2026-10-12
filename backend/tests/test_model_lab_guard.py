"""The Model Lab never lets a research loader's SystemExit reach the server (on 2026-10-10 one hung the hosted app), and the hosted
warm-up runs once in the background without ever failing startup."""
from __future__ import annotations

import threading

from fastapi.testclient import TestClient

from app import main
from app.main import app

client = TestClient(app)


def test_missing_data_is_an_answer_not_an_exit(monkeypatch):
    from core.ml.forecasting.layer import lab

    def gone(*a, **k):
        raise SystemExit("METR-LA not available at /nowhere")
    monkeypatch.setattr(lab, "run", gone)
    r = client.post("/api/model-lab/run", json={"sensor": 0, "at": "2012-06-07T14:30", "model": "D2STGNN"})
    assert r.status_code == 200 and r.json()["ok"] is False and "missing data" in r.json()["error"]
    monkeypatch.setattr(lab, "axis", gone)
    r = client.get("/api/model-lab/sensors")
    assert r.status_code == 200 and r.json()["available"] is False
    assert client.get("/api/health").status_code == 200          # the server still answers


def test_warm_up_only_hosted_and_never_raises(monkeypatch, capsys):
    from core.ml.forecasting.layer import lab
    started = []
    monkeypatch.setattr(threading.Thread, "start", lambda self: started.append(self.name) or self.run())
    monkeypatch.delenv("TRAFFICTWIN_HOSTED", raising=False)
    main._warm_model_lab()
    assert started == []
    monkeypatch.setenv("TRAFFICTWIN_HOSTED", "1")
    monkeypatch.setattr(lab, "sensors", lambda: (_ for _ in ()).throw(SystemExit("no data")))
    main._warm_model_lab()                                       # SystemExit inside the warm-up: logged, not raised
    assert started == ["model-lab-warm-up"] and "warm-up skipped: SystemExit" in capsys.readouterr().out
