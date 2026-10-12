"""P2 sensor-graph → BasicTS dataset export.

Contract verified against the PINNED BasicTS checkout (`upstream/UPSTREAM_PINS
.yaml` @ c2bb6e3, `src/basicts/data/tsf_dataset.py`): a dataset directory holds
`train_data.npy` / `val_data.npy` / `test_data.npy`, each (T_mode, N, C), plus
optional `{mode}_timestamps.npy`; windows are sliced by the loader itself.
This module only translates — it implements no training logic (adapters
translate, never alter; official-implementation policy).

Honesty rules carried into the export:

* The split is `ChronoSplit.standard` — the same object, and therefore the
  same sha256, as the baseline floors in `baselines.py`. Every BasicTS
  candidate trains on byte-identical splits.
* NaN speeds (bins where no vehicle was sampled) cannot enter a torch model.
  They are filled with 0.0 **explicitly**, the validity mask is appended as an
  extra channel, and DESC.json records the fill policy — losses/metrics must
  mask, and the mask channel is how. Nothing is silently zeroed.
* DESC.json carries evidence_domain DHAKA_SIMULATED_SENSOR_GRAPH; results on
  this dataset are simulated-domain results, never real-Dhaka claims.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from core.ml.forecasting.evaluation.twin_baselines import STEP_S, ChronoSplit

MODES = ("train", "val", "test")

# The pinned v1.0 zoo (models/) has STID/StemGNN but NOT DCRNN, Graph WaveNet
# or STAEformer; those live in the pre-1.0 benchmark layout (baselines/ at
# commit 4c3e2d3, 2025-05-26 — the published fair-comparison harness). Both
# checkouts therefore get an export: v1.0 (`export_basicts_dataset`) and
# legacy (`export_basicts_legacy_dataset`). Verified from the repo history,
# not from memory, 2026-08-19.
LEGACY_BASELINE_SHA = "4c3e2d373c647667c2123e1591f2d79c229dfcc6"
LEGACY_RATIOS = (0.7, 0.1, 0.2)


def export_basicts_dataset(p2_dir: Path, out_dir: Path,
                           period_steps: int = 288) -> Path:
    """Translate a P2 dataset directory into a BasicTS dataset directory."""
    manifest = json.loads((Path(p2_dir) / "MANIFEST.json").read_text())
    if manifest["evidence_domain"] != "DHAKA_SIMULATED_SENSOR_GRAPH":
        raise ValueError("refusing to export: dataset is not labelled "
                         "DHAKA_SIMULATED_SENSOR_GRAPH")
    z = np.load(Path(p2_dir) / "sensor_graph_data.npz")
    data, mask, adj = z["data"], z["mask"], z["adjacency"]
    t_len, n, c = data.shape

    split = ChronoSplit.standard(t_len)
    bounds = {"train": (0, split.train_end),
              "val": (split.train_end, split.val_end),
              "test": (split.val_end, t_len)}

    # Channels + validity mask as the last channel; explicit NaN→0 fill.
    filled = np.nan_to_num(data, nan=0.0).astype(np.float32)
    full = np.concatenate([filled, mask[..., None].astype(np.float32)], axis=2)

    # Timestamps: time-of-day fraction and day index, per bin (simulated clock).
    idx = np.arange(t_len)
    tod = (idx % period_steps) / period_steps
    day = idx // period_steps
    ts = np.repeat(np.stack([tod, day], axis=1)[:, None, :], n, axis=1
                   ).astype(np.float32)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for mode in MODES:
        lo, hi = bounds[mode]
        np.save(out / f"{mode}_data.npy", full[lo:hi])
        np.save(out / f"{mode}_timestamps.npy", ts[lo:hi])
    np.save(out / "adj_mx.npy", adj.astype(np.float32))

    desc = {
        "name": "DhakaR1SensorGraph",
        "evidence_domain": manifest["evidence_domain"],
        "reality_label": "SIMULATED",
        "never_described_as": "real sensor measurements",
        "shape": {"timesteps": t_len, "nodes": n,
                  "channels": c + 1},
        "channels": list(manifest["channels"]) + ["validity_mask"],
        "nan_fill_policy": "speed NaN (zero-traffic bins) filled with 0.0; "
                           "validity_mask channel is authoritative — losses "
                           "and metrics MUST mask on it",
        "step_s": STEP_S,
        "split": {"train_end": split.train_end, "val_end": split.val_end,
                  "sha256": split.sha256(),
                  "rule": "chronological, identical for every candidate"},
        "source_manifest_node_hash": manifest["node_list_sha256"],
        "network_sha256": manifest["network_sha256"],
        "adjacency": "adj_mx.npy — DCRNN gaussian-kernel recipe, directed",
        "basicts_pin_sha": "c2bb6e31e591167e84459775a21a62e70a5893ce",
    }
    p = out / "DESC.json"
    p.write_text(json.dumps(desc, indent=2))
    return p


def export_basicts_legacy_dataset(p2_dir: Path, out_dir: Path,
                                  period_steps: int = 288) -> Path:
    """Translate a P2 dataset into the pre-1.0 BasicTS benchmark layout.

    Contract verified at commit 4c3e2d3 (`basicts/data/simple_tsf_dataset.py`,
    `basicts/utils/serialization.py::load_adj`):

    * `data.dat`   — float32 memmap, shape recorded in desc.json["shape"];
      the loader computes the chronological split itself from ratios.
    * `desc.json`  — must carry "shape"; extra honesty keys are tolerated.
    * `adj_mx.pkl` — `load_adj` accepts a bare pickled (N, N) matrix.

    Channel layout follows the METR-LA convention: target first, then time
    features. Missing speeds are 0.0 by explicit fill, matching the legacy
    harness's own masking convention (NULL_VAL = 0.0 in masked losses).
    """
    import pickle

    manifest = json.loads((Path(p2_dir) / "MANIFEST.json").read_text())
    if manifest["evidence_domain"] != "DHAKA_SIMULATED_SENSOR_GRAPH":
        raise ValueError("refusing to export: dataset is not labelled "
                         "DHAKA_SIMULATED_SENSOR_GRAPH")
    z = np.load(Path(p2_dir) / "sensor_graph_data.npz")
    data, mask, adj = z["data"], z["mask"], z["adjacency"]
    t_len, n, _ = data.shape

    speed = np.nan_to_num(data[..., 0], nan=0.0)      # NULL_VAL=0.0 convention
    flow = data[..., 3]
    idx = np.arange(t_len)
    tod = np.repeat(((idx % period_steps) / period_steps)[:, None], n, axis=1)
    # dow as FRACTION day/7 — STID indexes day_in_week_emb[(dow*7).long()],
    # so integer day values overflow the 7-slot embedding (found live: index 7).
    dow = np.repeat((((idx // period_steps) % 7) / 7.0)[:, None], n, axis=1)
    # METR-LA channel convention as the graph baselines actually index it
    # (STID arch: ch1 = time-of-day fraction, ch2 = day-of-week) — flow rides
    # fourth, unused by input_dim=3 models. Found live: flow in ch1 made
    # STID's tod embedding index 1152 >> 288.
    arr = np.stack([speed, tod, dow, flow], axis=2).astype(np.float32)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    mm = np.memmap(out / "data.dat", dtype="float32", mode="w+",
                   shape=arr.shape)
    mm[:] = arr
    mm.flush()
    with open(out / "adj_mx.pkl", "wb") as fh:
        pickle.dump(adj.astype(np.float32), fh)

    valid_len = int(t_len * LEGACY_RATIOS[1])
    test_len = int(t_len * LEGACY_RATIOS[2])
    desc = {
        "name": "DhakaR1SensorGraph_legacy",
        "shape": list(arr.shape),                     # the key the loader reads
        "evidence_domain": manifest["evidence_domain"],
        "reality_label": "SIMULATED",
        "channels": ["speed_ms", "tod_fraction", "day_index_mod7", "flow_veh"],
        "target_channel": 0,
        "null_val": 0.0,
        "nan_fill_policy": "speed NaN (zero-traffic bins) filled with 0.0 to "
                           "match the legacy harness NULL_VAL=0.0 masking",
        "train_val_test_ratio": list(LEGACY_RATIOS),
        # Contract addition (found live 2026-08-26): get_regular_settings()
        # at 4c3e2d3 reads desc["regular_settings"] — shape copied from the
        # official generators (scripts/data_preparation/*/generate_training_data.py).
        "regular_settings": {
            "INPUT_LEN": 12,
            "OUTPUT_LEN": 12,
            "TRAIN_VAL_TEST_RATIO": list(LEGACY_RATIOS),
            "NORM_EACH_CHANNEL": False,
            "RESCALE": True,
            "METRICS": ["MAE", "RMSE", "MAPE"],
            "NULL_VAL": 0.0,
        },
        "loader_computed_boundaries": {
            "train_len": t_len - valid_len - test_len,
            "valid_len": valid_len, "test_len": test_len},
        "source_manifest_node_hash": manifest["node_list_sha256"],
        "network_sha256": manifest["network_sha256"],
        "basicts_legacy_sha": LEGACY_BASELINE_SHA,
    }
    p = out / "desc.json"
    p.write_text(json.dumps(desc, indent=2))
    return p
