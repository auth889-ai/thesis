"""BasicTS export tests — split identity, NaN policy, format contract."""
from __future__ import annotations

import json

import numpy as np
import pytest

from research.forecasting.baselines import ChronoSplit
from research.forecasting.basicts_adapter import (
    LEGACY_RATIOS, export_basicts_dataset, export_basicts_legacy_dataset)


@pytest.fixture()
def p2_dir(tmp_path):
    t, n, c = 3 * 288, 12, 4
    rng = np.random.default_rng(1)
    data = rng.uniform(1, 20, size=(t, n, c))
    mask = rng.random((t, n)) > 0.3
    data[..., 0][~mask] = np.nan          # speed NaN exactly where unmasked
    d = tmp_path / "p2"
    d.mkdir()
    np.savez_compressed(d / "sensor_graph_data.npz", data=data, mask=mask,
                        adjacency=np.eye(n), distances_m=np.ones((n, n)))
    (d / "MANIFEST.json").write_text(json.dumps({
        "evidence_domain": "DHAKA_SIMULATED_SENSOR_GRAPH",
        "channels": ["speed_ms", "density_veh_km", "occupancy_pct", "flow_veh"],
        "node_list_sha256": "abc", "network_sha256": "def"}))
    return d


def test_export_refuses_unlabelled_dataset(tmp_path, p2_dir):
    m = json.loads((p2_dir / "MANIFEST.json").read_text())
    m["evidence_domain"] = "SOMETHING_ELSE"
    (p2_dir / "MANIFEST.json").write_text(json.dumps(m))
    with pytest.raises(ValueError, match="refusing"):
        export_basicts_dataset(p2_dir, tmp_path / "out")


def test_export_matches_pinned_basicts_contract(tmp_path, p2_dir):
    out = tmp_path / "out"
    export_basicts_dataset(p2_dir, out)
    # File names exactly as read by tsf_dataset.py at the pinned SHA.
    for mode in ("train", "val", "test"):
        arr = np.load(out / f"{mode}_data.npy")
        ts = np.load(out / f"{mode}_timestamps.npy")
        assert arr.ndim == 3 and arr.dtype == np.float32
        assert not np.isnan(arr).any()            # torch-safe, fill recorded
        assert ts.shape[:2] == arr.shape[:2]
    assert (out / "adj_mx.npy").exists()


def test_split_hash_identical_to_baseline_split(tmp_path, p2_dir):
    out = tmp_path / "out"
    export_basicts_dataset(p2_dir, out)
    desc = json.loads((out / "DESC.json").read_text())
    t = 3 * 288
    assert desc["split"]["sha256"] == ChronoSplit.standard(t).sha256()
    tr = np.load(out / "train_data.npy")
    va = np.load(out / "val_data.npy")
    te = np.load(out / "test_data.npy")
    assert tr.shape[0] + va.shape[0] + te.shape[0] == t
    assert tr.shape[0] == ChronoSplit.standard(t).train_end


def test_mask_channel_is_authoritative(tmp_path, p2_dir):
    out = tmp_path / "out"
    export_basicts_dataset(p2_dir, out)
    z = np.load(p2_dir / "sensor_graph_data.npz")
    tr = np.load(out / "train_data.npy")
    lo_mask = z["mask"][:tr.shape[0]]
    # Last channel equals the P2 validity mask; zero-filled speeds only there.
    assert np.array_equal(tr[..., -1].astype(bool), lo_mask)
    assert (tr[..., 0][~lo_mask] == 0.0).all()
    desc = json.loads((out / "DESC.json").read_text())
    assert desc["channels"][-1] == "validity_mask"
    assert "MUST mask" in desc["nan_fill_policy"]


def test_legacy_export_matches_pre10_contract(tmp_path, p2_dir):
    import pickle
    out = tmp_path / "legacy"
    export_basicts_legacy_dataset(p2_dir, out)
    desc = json.loads((out / "desc.json").read_text())
    t, n = 3 * 288, 12
    assert desc["shape"] == [t, n, 4]
    # Loader reads data.dat as a float32 memmap with exactly desc["shape"].
    mm = np.memmap(out / "data.dat", dtype="float32", mode="r",
                   shape=tuple(desc["shape"]))
    assert not np.isnan(mm).any()
    # Missing speeds are 0 exactly where the P2 mask is False (NULL_VAL=0.0).
    z = np.load(p2_dir / "sensor_graph_data.npz")
    assert (np.asarray(mm[..., 0])[~z["mask"]] == 0.0).all()
    # load_adj's bare-matrix fallback: pickle holds the (N, N) array.
    with open(out / "adj_mx.pkl", "rb") as fh:
        adj = pickle.load(fh)
    assert adj.shape == (n, n)
    # Ratio-derived boundaries recorded and consistent.
    b = desc["loader_computed_boundaries"]
    assert b["train_len"] + b["valid_len"] + b["test_len"] == t
    assert desc["train_val_test_ratio"] == list(LEGACY_RATIOS)
