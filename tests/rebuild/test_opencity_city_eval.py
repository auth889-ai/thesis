"""OpenCity through its own harness on a city of ours: the gates are the model's, measured."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from pipeline.forecasting import opencity_city_eval as oce      # noqa: E402
from pipeline.forecasting import _opencity_boot as boot          # noqa: E402

needs_recorded = pytest.mark.skipif(not (REPO / "results/artifacts/live_dhaka/normalized/google_routes_runtime_reference.jsonl").exists(), reason="recorded live series is git-ignored; absent on CI")


def test_gates_are_the_models_own():
    assert oce.MIN_NODES == 9                       # 8 Laplacian eigenvectors + 1
    assert oce.MIN_STEPS == 288 + 288 + (288 + 288 + 24)


def test_too_few_nodes_is_refused_with_the_reason():
    with pytest.raises(SystemExit, match="9 nodes"):
        oce.run("DF_X", np.zeros((2000, 6)), np.eye(6), 8, 10)


def test_too_short_history_is_refused_with_hours_to_go():
    with pytest.raises(SystemExit, match="h more of observation"):
        oce.run("DF_X", np.zeros((300, 12)), np.eye(12), 8, 10)


def test_persistence_reference_masks_missing_and_uses_test_windows_only():
    x = np.full((oce.HIS + oce.PRED + 10, 3), 2.0)
    x[-1, 0] = np.nan                               # a gap must not be scored
    ref = oce.persistence_reference(x, test_ratio=1.0)
    assert ref["windows"] == 11 and ref["mae"] == 0.0


@needs_recorded
def test_recorded_classes_are_recoded_so_zero_means_missing():
    vals, nodes, meta = oce.from_recorded()
    finite = vals[np.isfinite(vals)]
    assert finite.min() >= 1.0 and finite.max() <= 4.0 and len(nodes) == vals.shape[1]


def test_geo_adjacency_leaves_no_node_isolated():
    sys.path.insert(0, str(REPO / "src/dashboard/backend"))
    import corridors as cz
    A = oce.geo_adjacency([c["id"] for c in cz.CORRIDORS])
    assert A.shape == (12, 12) and np.allclose(A, A.T)
    assert ((A > 0).sum(axis=1) >= 2).all()          # self plus at least one neighbour


def test_boot_shim_routes_only_df_names(monkeypatch):
    """The DF_* branch loads whole and uses THEIR time_add; other names go to their loader."""
    import types
    calls = []
    fake = types.SimpleNamespace(
        load_st_dataset=lambda d, a: calls.append(d) or "theirs",
        time_add=lambda data, ws, interval, weekday_only, holiday_list, day_start: (
            np.zeros_like(data), np.zeros_like(data), np.zeros_like(data)))
    monkeypatch.setitem(sys.modules, "lib", types.SimpleNamespace(data_process=fake))
    monkeypatch.setitem(sys.modules, "lib.data_process", fake)
    assert boot.install_generic_dataset().startswith("lib.data_process.load_st_dataset")
    assert fake.load_st_dataset("PEMS07M", None) == "theirs" and calls == ["PEMS07M"]


# ------------------------------------------------------------------ predictions through their stack

def test_prediction_scoring_masks_missing_and_reports_skill():
    from pipeline.forecasting import opencity_predict as op
    pred = np.full((288, 3), 2.0); actual = np.full((288, 3), 2.0); last = np.array([1.0, 1.0, 1.0])
    actual[2, 1] = 0.0                                   # missing under the model's convention
    s = op.score(pred, actual, last, [15])
    assert s[15]["n"] == 2 and s[15]["opencity_mae"] == 0.0 and s[15]["skill_vs_persistence"] == 1.0


def test_csv_contract_matches_the_authors_demo(tmp_path):
    from pipeline.forecasting import opencity_predict as op
    import pandas as pd
    t = pd.date_range("2026-01-01", periods=20, freq="5min")
    df = pd.DataFrame({"time": t, **{f"region_{i}": np.arange(20) + i for i in range(3)}})
    df.to_csv(tmp_path / "c.csv", index=False); np.save(tmp_path / "a.npy", np.eye(3))
    vals, nodes, A, meta = op.load_csv(tmp_path / "c.csv", tmp_path / "a.npy")
    assert vals.shape == (20, 3) and nodes == ["region_0", "region_1", "region_2"] and A.shape == (3, 3)
    with pytest.raises(SystemExit, match="9 nodes"):
        op.forward("DF_T", np.zeros((300, 3)), np.eye(3), None)


def test_subgraph_centres_on_the_region_and_has_enough_nodes():
    from pipeline.forecasting import opencity_predict as op
    A = np.zeros((20, 20)); A[0, 1] = A[1, 0] = 0.9; A[0, 2] = A[2, 0] = 0.5; A[2, 3] = A[3, 2] = 0.7
    idx = op.subgraph(A, 0, 12)
    assert idx[0] == 0 and idx[1] == 1 and idx[2] == 2 and len(idx) == 12 and len(set(idx)) == 12
