"""A user's CSV — wide or long — becomes a dataset the prediction lab serves."""
import io

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    from core.common.data import uploads as user_datasets
    monkeypatch.setattr(user_datasets, "ROOT", tmp_path / "user_datasets")
    return user_datasets


def _wide(n_nodes=10, steps=300, freq="5min"):
    t = pd.date_range("2026-09-01", periods=steps, freq=freq, tz="UTC")
    x = 40 + 10 * np.sin(np.arange(steps) / 20)[:, None] + np.random.default_rng(0).normal(0, 2, (steps, n_nodes))
    df = pd.DataFrame(x, columns=[f"Road {i}" for i in range(n_nodes)]); df.insert(0, "time", t.strftime("%Y-%m-%d %H:%M"))
    return df.to_csv(index=False).encode()


def test_wide_csv_is_saved_and_listed(isolated_root):
    m = isolated_root.save("Some City", _wide())
    assert m["steps"] == 300 and len(m["nodes"]) == 10 and m["interval_s"] == 300
    assert "correlation" in m["graph_from"]
    ds = isolated_root.datasets()
    assert ds[0]["id"] == "user:some_city" and ds[0]["models"] == ["OpenCity-plus", "Chronos-Bolt", "persistence"]
    vals, nodes, A, meta = isolated_root.series("some_city", 3)
    assert nodes[0] == "Road 3" and vals.shape == (300, 10) and A.shape == (10, 10)
    assert (A.sum(axis=1) > 1).all(), "no road may be isolated in the graph"


def test_long_csv_with_coarse_clock(isolated_root):
    rows = [{"time": ts, "road": r, "speed": 30 + i} for i, ts in enumerate(pd.date_range("2026-09-01", periods=40, freq="15min"))
            for r in ("A", "B", "C")]
    m = isolated_root.save("Town", pd.DataFrame(rows).to_csv(index=False).encode(), quantity="speed_kmh")
    assert len(m["nodes"]) == 3 and m["steps"] == 40 and m["interval_s"] == 900
    assert isolated_root.models_for(m) == ["Chronos-Bolt", "persistence"]      # too small / coarse for OpenCity


def test_coordinates_build_a_distance_graph(isolated_root):
    coords = "road,lat,lon\n" + "\n".join(f"Road {i},{23.7 + i * 0.01},{90.4}" for i in range(10))
    m = isolated_root.save("Geo", _wide(), coords_bytes=coords.encode())
    assert "distance kernel" in m["graph_from"]


def test_bad_csv_is_refused(isolated_root):
    with pytest.raises(ValueError):
        isolated_root.save("x", b"time\n2026-01-01\n")


def test_upload_endpoint_then_predict(client, isolated_root):
    r = client.post("/api/predict-lab/upload", data={"name": "Api City", "quantity": "speed_kmh"},
                    files={"csv": ("c.csv", _wide(4, 60), "text/csv")}).json()
    assert r["ok"] and r["dataset"] == "user:api_city" and "persistence" in r["models"]
    assert any(d["id"] == "user:api_city" for d in client.get("/api/predict-lab/datasets").json()["datasets"])
    job = client.post("/api/predict-lab/run", json={"dataset": "user:api_city", "model": "persistence", "region": 2, "as_of": 50}).json()["job"]
    import time
    for _ in range(100):
        s = client.get(f"/api/predict-lab/{job}").json()
        if s["status"] != "running":
            break
        time.sleep(0.2)
    assert s["status"] == "done", s.get("error")
    res = s["result"]
    assert res["quantity"] == "speed km/h" and res["metrics"]["15"]["predicted"] == res["history"][-1]
