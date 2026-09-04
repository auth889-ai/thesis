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


def test_recorded_classes_are_recoded_so_zero_means_missing():
    vals, nodes, meta = oce.from_recorded()
    finite = vals[np.isfinite(vals)]
    assert finite.min() >= 1.0 and finite.max() <= 4.0 and len(nodes) == vals.shape[1]


def test_geo_adjacency_leaves_no_node_isolated():
    sys.path.insert(0, str(REPO / "dashboard/backend"))
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
