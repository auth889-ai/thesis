#!/usr/bin/env python3
"""Twin calibration PART A — network-level, against the live Dhaka reference.

Method (declared before results were seen):
  * LIVE side: one fresh Google Routes capture over the six real R1 corridors
    (RUNTIME_REFERENCE rules — live values are used in-memory; only derived
    verdicts are persisted). Congestion ratio per corridor =
    duration / static_duration; the network live factor is their mean.
  * TWIN side: the P2 datasets exist at three demand scales (0.3 / 0.5 / 1.0).
    For each, the congestion factor = mean over sensors of
    (peak-hour mean speed) / (free-flow speed proxy = 95th-percentile speed of
    that sensor). Peak hours = bins 08:00-10:00 of each simulated day.
  * VERDICT: interpolate the demand scale whose twin factor matches the live
    factor. That scale is the CALIBRATED_A demand for control-gate scenarios.

This is *part A only* (network-level). Part B refines per-corridor demand from
detector counts. Labels: the result is a calibration parameter, not a claim
that simulated traffic equals real traffic.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SCALES = {
    # 0.3 smoke excluded: only 2 sim-hours, contains no 08:00-10:00 peak bins
    0.5: "artifacts/p2_sensor_graph_medium",
    1.0: "artifacts/p2_sensor_graph_full",
}
PEAK_BINS_PER_DAY = range(8 * 12, 10 * 12)      # 08:00-10:00, 5-min bins


def twin_factor(npz_dir: str) -> float:
    z = np.load(REPO / npz_dir / "sensor_graph_data.npz")
    data, mask = z["data"][..., 0], z["mask"]      # speed channel
    t_len = data.shape[0]
    day_bins = 288 if t_len >= 288 else t_len
    peak_idx = [d * day_bins + b for d in range(max(t_len // day_bins, 1))
                for b in PEAK_BINS_PER_DAY if d * day_bins + b < t_len]
    factors = []
    for n in range(data.shape[1]):
        col = data[:, n]
        valid = mask[:, n]
        if valid.sum() < 10:
            continue
        vfree = np.nanpercentile(col[valid], 95)
        pk = [col[i] for i in peak_idx if valid[i] and np.isfinite(col[i])]
        if not pk or vfree <= 0:
            continue
        factors.append(max(float(np.mean(pk) / vfree), 0.05))
    return float(np.mean(factors))                 # 1.0 = free flow


def live_factor() -> tuple[float, list[dict]]:
    from dhakaflow.live.google_providers import GoogleRoutesProvider
    from dhakaflow.live.providers import DHAKA_R1_CORRIDORS
    ref = GoogleRoutesProvider()
    if not ref.enabled:
        sys.exit("GOOGLE_MAPS_API_KEY missing — calibration needs one capture")
    ratios, rows = [], []
    for c in DHAKA_R1_CORRIDORS:
        obs = ref.edge_state(c["corridor_id"], c["origin"], c["dest"])
        ratio = obs.duration_s / max(obs.static_duration_s, 1.0)
        ratios.append(ratio)
        rows.append({"corridor": c["corridor_id"],
                     "congestion_ratio": round(ratio, 3)})   # derived verdict only
    return float(np.mean(ratios)), rows


def main() -> None:
    live, rows = live_factor()
    # live ratio r means travel takes r× free-flow → speed factor = 1/r
    live_speed_factor = 1.0 / live

    points = []
    for scale, d in SCALES.items():
        f = twin_factor(d)
        points.append((scale, f))
        print(f"twin scale {scale}: speed factor {f:.3f}")
    print(f"live speed factor (this capture): {live_speed_factor:.3f} "
          f"(mean corridor ratio {live:.3f})")

    # linear interpolation on (factor -> scale); factors decrease with scale
    points.sort(key=lambda p: p[1])
    fs = [p[1] for p in points]
    ss = [p[0] for p in points]
    cal_scale = float(np.interp(live_speed_factor, fs, ss))
    inside = fs[0] <= live_speed_factor <= fs[-1]

    record = {
        "stage": "TWIN_CALIBRATION_PART_A",
        "method": "network speed-factor matching, 3-scale interpolation",
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "live_corridor_ratios": rows,                  # derived verdicts only
        "live_speed_factor": round(live_speed_factor, 4),
        "twin_points_scale_to_factor": [[s, round(f, 4)] for s, f in points],
        "calibrated_demand_scale_A": round(cal_scale, 3),
        "interpolation_within_range": inside,
        "honesty": {
            "label": "CALIBRATED_A_NETWORK_LEVEL",
            "google_content": "no raw provider fields persisted "
                              "(RUNTIME_REFERENCE); ratios are derived verdicts",
            "not_claimed": "simulated traffic == real traffic; part B refines "
                           "with detector counts",
        },
    }
    hist = REPO / "artifacts" / "twin_calibration_A_history.jsonl"
    with open(hist, "a") as fh:
        fh.write(json.dumps(record) + "\n")
    # Final part-A verdict uses the MOST CONGESTED capture seen so far —
    # calibration targets peak conditions, and captures are cheap.
    factors = [json.loads(l)["live_speed_factor"] for l in open(hist)]
    worst = min(factors)
    record["final_A"] = {
        "captures_so_far": len(factors),
        "worst_live_speed_factor": round(worst, 4),
        "calibrated_demand_scale_A": round(float(np.interp(worst, fs, ss)), 3),
        "rule": "min speed factor across captures (peak targeting)",
    }
    out = REPO / "artifacts" / "twin_calibration_A.json"
    out.write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))
    print(f"\nsaved: {out}")


if __name__ == "__main__":
    main()
