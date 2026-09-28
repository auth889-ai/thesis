#!/usr/bin/env python3
"""Forecast -> SUMO meanData weight XML for src/pipeline/routing/predictive_routing.py --weights.

Output format (what predictive_routing.load_weights parses, and what SUMO / duarouter
--weight-files accept):

    <meandata>
      <interval begin="0.00" end="300.00" id="forecast">
        <edge id="..." traveltime="12.3"/>
      </interval>
    </meandata>

Edges not listed in an interval fall back to SUMO's free-flow travel time.

Sources:
  --source oracle       copy a static run's edgedata.xml (truth for the same seed = upper bound)
        python src/pipeline/forecasting/forecast_to_weights.py --source oracle --edgedata results/routing/static_s11_h900/edgedata.xml --out results/routing/weights/oracle_s11.xml
        python src/pipeline/forecasting/forecast_to_weights.py --source oracle --seeds 11,12,13 --horizon 3600      # Makefile form:
              reads results/routing/static_s{seed}_h{horizon}/edgedata.xml -> results/routing/weights/oracle_s{seed}_h{horizon}.xml
  --source persistence  each interval [b, e) carries the values measured in [b-lag, e-lag)
                        (the no-model forecast; intervals with no predecessor are omitted)
        python src/pipeline/forecasting/forecast_to_weights.py --source persistence --lag 300 --edgedata ... --out ...
  --source model        BasicTS prediction array of SPEEDS on the twin sensors -> traveltime =
                        length_m / speed for the sensor edges only (other edges free-flow)
        python src/pipeline/forecasting/forecast_to_weights.py --source model --pred pred.npz --sensor-nodes data/forecasting/dhaka_twin/sensor_nodes.json \
               --horizon-min 15 --t0 3900 --out results/routing/weights/gwnet_h15_s11.xml
        pred.npz: key --pred-key (default 'prediction'; falls back to the first array), shape
        (T, N) = already-selected horizon, or (T, H, N[, 1]) = full multi-horizon output.
        Row t is the forecast issued at origin t; step k (0-based) targets the bin starting at
        t0 + (t + k) * period. --horizon-min h picks k = h/period - 1, so the interval at
        time tau is written from the forecast issued h minutes earlier: ablate h to measure
        how forecast lead time changes the routing gain. --t0 = sim-time (s) at which the
        1-step-ahead target of row 0 begins (for a BasicTS test split: (test_start + INPUT_LEN)
        * 300 within the seed window).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

import numpy as np

LABEL = "DHAKA_SIMULATED_SENSOR_GRAPH"
UNIT_TO_MS = {"ms": 1.0, "kmh": 1.0 / 3.6, "mph": 0.44704}


def read_edgedata(path: Path) -> list[tuple[float, float, dict[str, float]]]:
    """SUMO meanData XML -> [(begin, end, {edge: traveltime})], chronological."""
    ivs = []
    for iv in ET.parse(path).getroot().iter("interval"):
        b, e = float(iv.get("begin")), float(iv.get("end"))
        tt = {ed.get("id"): float(ed.get("traveltime")) for ed in iv.iter("edge")
              if ed.get("traveltime") is not None}
        ivs.append((b, e, tt))
    ivs.sort(key=lambda x: x[0])
    return ivs


def write_weights(path: Path, intervals: list[tuple[float, float, dict[str, float]]],
                  provenance: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("meandata")
    root.append(ET.Comment(" " + json.dumps({"label": LABEL, **provenance}) + " "))
    for b, e, tt in intervals:
        iv = ET.SubElement(root, "interval", begin=f"{b:.2f}", end=f"{e:.2f}", id="forecast")
        for edge, t in sorted(tt.items()):
            ET.SubElement(iv, "edge", id=edge, traveltime=f"{t:.2f}")
    ET.indent(root)
    ET.ElementTree(root).write(path, xml_declaration=True, encoding="UTF-8")
    return path


def oracle(edgedata: Path) -> list:
    return read_edgedata(edgedata)


def persistence(edgedata: Path, lag: float) -> list:
    ivs = read_edgedata(edgedata)
    by_begin = {round(b, 3): tt for b, _, tt in ivs}
    out = []
    for b, e, _ in ivs:
        prev = by_begin.get(round(b - lag, 3))
        if prev is not None:
            out.append((b, e, dict(prev)))
    return out


def load_pred(path: Path, key: str) -> np.ndarray:
    z = np.load(path)
    arr = z[key] if key in z.files else z[z.files[0]]
    arr = np.asarray(arr, dtype=np.float64)
    while arr.ndim > 3 and arr.shape[-1] == 1:
        arr = arr[..., 0]
    return arr


def model(pred: np.ndarray, sensor_nodes: list[dict], horizon_min: float, t0: float,
          period: float, speed_unit: str, min_speed_ms: float, cap_factor: float) -> list:
    n = len(sensor_nodes)
    if pred.ndim == 2:
        if pred.shape[1] != n:
            raise ValueError(f"pred (T,N) has N={pred.shape[1]} but {n} sensor nodes")
        k = int(round(horizon_min * 60 / period)) - 1
        steps = pred
    elif pred.ndim == 3:
        if pred.shape[2] != n:
            raise ValueError(f"pred (T,H,N) has N={pred.shape[2]} but {n} sensor nodes")
        k = int(round(horizon_min * 60 / period)) - 1
        if not (0 <= k < pred.shape[1]):
            raise ValueError(f"--horizon-min {horizon_min} -> step {k} outside H={pred.shape[1]}")
        steps = pred[:, k, :]
    else:
        raise ValueError(f"pred must be (T,N) or (T,H,N[,1]); got {pred.shape}")
    if k < 0:
        raise ValueError("--horizon-min must be >= one period")

    lengths = np.array([nd["length_m"] for nd in sensor_nodes])
    limits = np.array([nd["speed_limit_ms"] for nd in sensor_nodes])
    ids = [nd["edge_id"] for nd in sensor_nodes]
    speed = steps * UNIT_TO_MS[speed_unit]
    out = []
    for t in range(steps.shape[0]):
        b = t0 + (t + k) * period
        tt = {}
        for j in range(n):
            s = speed[t, j]
            if not np.isfinite(s) or s <= 0:          # 0 = NULL (no traffic) -> free-flow
                continue
            s = min(max(s, min_speed_ms), limits[j] * cap_factor)
            tt[ids[j]] = lengths[j] / s
        out.append((b, b + period, tt))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["oracle", "persistence", "model"], required=True)
    ap.add_argument("--edgedata", type=Path, help="static run edgedata.xml (oracle/persistence)")
    ap.add_argument("--seeds", help="Makefile form: comma list -> results/routing/static_s{seed}_h{horizon}")
    ap.add_argument("--horizon", type=int, default=3600, help="routing-run horizon (Makefile form)")
    ap.add_argument("--lag", type=float, default=300.0, help="persistence lag (s)")
    ap.add_argument("--pred", type=Path, help="prediction .npz (model)")
    ap.add_argument("--pred-key", default="prediction")
    ap.add_argument("--sensor-nodes", type=Path, default=REPO / "data/forecasting/dhaka_twin/sensor_nodes.json")
    ap.add_argument("--horizon-min", type=float, default=5.0, help="lead time used per interval (model)")
    ap.add_argument("--t0", type=float, default=300.0, help="sim time (s) of row 0's 1-step target bin (model)")
    ap.add_argument("--period", type=float, default=300.0)
    ap.add_argument("--speed-unit", choices=list(UNIT_TO_MS), default="ms")
    ap.add_argument("--min-speed", type=float, default=0.5, help="m/s floor before length/speed")
    ap.add_argument("--cap-factor", type=float, default=1.2, help="speed cap = limit x factor")
    ap.add_argument("--out", type=Path, help="output XML (single-file form)")
    ap.add_argument("--out-dir", type=Path, default=REPO / "results/routing/weights")
    a = ap.parse_args()

    jobs: list[tuple[Path | None, Path]] = []
    if a.source in ("oracle", "persistence"):
        if a.edgedata:
            jobs.append((a.edgedata, a.out or a.out_dir / f"{a.source}_{a.edgedata.parent.name}.xml"))
        elif a.seeds:
            for s in [int(x) for x in a.seeds.split(",") if x]:
                ed = REPO / "results/routing" / f"static_s{s}_h{a.horizon}" / "edgedata.xml"
                jobs.append((ed, a.out_dir / f"{a.source}_s{s}_h{a.horizon}.xml"))
        else:
            ap.error("--edgedata or --seeds is required for oracle/persistence")
    else:
        if not a.pred:
            ap.error("--pred is required for --source model")
        jobs.append((a.pred, a.out or a.out_dir / f"model_{a.pred.stem}_h{a.horizon_min:g}.xml"))

    for src, out in jobs:
        if not src.exists():
            print(f"[weights] SKIP missing {src}")
            continue
        prov = {"source": a.source, "input": str(src), "generated": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if a.source == "oracle":
            ivs = oracle(src)
        elif a.source == "persistence":
            ivs = persistence(src, a.lag)
            prov["lag_s"] = a.lag
        else:
            nodes = json.loads(a.sensor_nodes.read_text())
            ivs = model(load_pred(src, a.pred_key), nodes, a.horizon_min, a.t0, a.period,
                        a.speed_unit, a.min_speed, a.cap_factor)
            prov.update({"sensor_nodes": str(a.sensor_nodes), "horizon_min": a.horizon_min,
                         "t0": a.t0, "period": a.period, "speed_unit": a.speed_unit,
                         "traveltime": "length_m / speed on sensor edges only; others free-flow"})
        write_weights(out, ivs, prov)
        n_rows = sum(len(tt) for _, _, tt in ivs)
        span = f"{ivs[0][0]:.0f}-{ivs[-1][1]:.0f}s" if ivs else "empty"
        print(f"[weights] {a.source}: {len(ivs)} intervals ({span}), {n_rows} edge rows -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
