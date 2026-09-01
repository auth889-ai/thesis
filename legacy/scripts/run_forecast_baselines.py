#!/usr/bin/env python3
"""P3 — score the mandatory baselines on a P2 sensor-graph dataset.

    python scripts/run_forecast_baselines.py [--data artifacts/p2_sensor_graph_local]

Persistence + Historical Average on speed and flow, horizons 5/15/30 min,
chronological split, masked metrics. These numbers are the floor every BasicTS
candidate must beat; they carry evidence domain DHAKA_SIMULATED_SENSOR_GRAPH.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import numpy as np

from research.forecasting.baselines import run_baselines
from research.twin.sensor_graph import CHANNELS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path,
                    default=REPO / "artifacts" / "p2_sensor_graph_local")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    npz = a.data / "sensor_graph_data.npz"
    manifest = json.loads((a.data / "MANIFEST.json").read_text())
    if manifest["evidence_domain"] != "DHAKA_SIMULATED_SENSOR_GRAPH":
        raise SystemExit("refusing: dataset manifest lacks the simulated label")
    z = np.load(npz)
    data, mask = z["data"], z["mask"]
    print(f"[P3] dataset T={data.shape[0]} N={data.shape[1]} "
          f"C={data.shape[2]} — {manifest['evidence_domain']}")

    results = []
    for ch in ("speed_ms", "flow_veh"):
        idx = CHANNELS.index(ch)
        for rep in run_baselines(data, mask, idx, ch):
            results.append(rep.to_dict())
            line = " | ".join(
                f"{h}: MAE {m['mae']:.3f} RMSE {m['rmse']:.3f}"
                for h, m in rep.horizons.items())
            print(f"[P3] {rep.model:<20} {ch:<10} {line}")

    out = a.out or (a.data / "baseline_results.json")
    out.write_text(json.dumps({
        "dataset_manifest_node_hash": manifest["node_list_sha256"],
        "evidence_domain": manifest["evidence_domain"],
        "reality_label": "SIMULATED",
        "results": results}, indent=2))
    print(f"[P3] written: {out}")
    print("[P3] these are the floors BasicTS candidates must beat — no winner "
          "is declared here.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
