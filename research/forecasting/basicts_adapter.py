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

from .baselines import STEP_S, ChronoSplit

MODES = ("train", "val", "test")


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
