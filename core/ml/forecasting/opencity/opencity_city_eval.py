#!/usr/bin/env python3
"""Run OpenCity — the authors' harness, their released weights — on a city of OURS.

    python -m core.ml.forecasting.opencity.opencity_city_eval --source observatory --city dhaka
    python -m core.ml.forecasting.opencity.opencity_city_eval --source metrla-smoke        # CPU path check

Until now OpenCity was a capability label here: the adapter reported its gates and refused, and
the only forward passes were the published-benchmark reproductions on a GPU. This script is the
missing piece — it hands OpenCity a city it has never seen, in the exact layout its own loader
expects (`data/<NAME>/<NAME>.npz` with a (T, N) array and `<NAME>_rn_adj.npy`), and runs the
authors' `-mode test` unchanged. Their `load_st_dataset` has a generic branch for unknown names
(NaN -> 0, 5-min time features), so no upstream file is edited; the one configuration value the
authors tell readers to set (`dataset_use`) is set and restored.

WHAT OPENCITY NEEDS, MEASURED HERE RATHER THAN ASSUMED
    * 288 input steps AND 288 label steps per test window, plus one training window the harness
      insists on building: 1,176 steps, about 4 days of 5-minute data
    * >= 9 nodes: its Laplacian positional encoding takes 8 eigenvectors (`cal_lape`)
    * zeros mean "missing": its masked metrics drop targets <= 0, so an ordinal class that starts
      at 0 must be recoded (+1) or the free-flow class silently vanishes from the score

The number it produces is the authors' average-horizon MAE over 288 steps, beside persistence on
the identical windows. It is comparable to their Table 1, not to our 15-minute backtest.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from core.common.paths import REPO
sys.path.insert(0, str(REPO))
WORKSPACE = Path(os.environ.get("DHAKAFLOW_WORKSPACE", Path.home() / ".dhakaflow/upstream"))
OC = WORKSPACE / "OpenCity"
CONF = OC / "conf/general_conf/pretrain.conf"
WEIGHTS = "OpenCity-plus.pth"
OUT = REPO / "results/forecasting"
HIS = PRED = 288
MIN_NODES = 9                      # lape_dim (8) + 1, from lib/predifineGraph.cal_lape
TRAIN_KEEP = HIS + PRED + 24       # their harness always builds a shuffled TRAIN loader, and an
                                   # empty one raises; the smallest slice that holds one window
MIN_STEPS = TRAIN_KEEP + HIS + PRED   # 1,176 steps ~= 4.1 days of 5-minute data
METRIC_RE = re.compile(r"Average Horizon, MAE: ([\d.]+), RMSE: ([\d.]+), MAPE: ([\d.]+)%")


# ----------------------------------------------------------------------------- sources
def from_observatory(city: str):
    """(T, N) derived speeds in m/s from the persisted observatory window, plus node ids."""
    db = REPO / "results/live/observatory.sqlite"
    if not db.exists():
        raise SystemExit("no persisted observatory window yet (results/live/observatory.sqlite)")
    with sqlite3.connect(db) as c:
        rows = c.execute("SELECT t, utc, nodes, values_json FROM samples WHERE city=? ORDER BY t",
                         (city,)).fetchall()
    if not rows:
        raise SystemExit(f"the observatory holds no samples for {city}")
    nodes = json.loads(rows[-1][2])
    keep = [r for r in rows if json.loads(r[2]) == nodes]
    vals = np.array([[np.nan if v is None else v for v in json.loads(r[3])] for r in keep],
                    dtype="float64")
    return vals, nodes, {"quantity": "corridor mean speed, m/s (derived by us)", "reality": "REAL_LIVE",
                         "first_utc": keep[0][1], "last_utc": keep[-1][1]}


def from_recorded():
    from core.ml.forecasting.live import live_state
    rows = live_state.load_rows(live_state.SRC)
    vals, mask, corridors, bins = live_state.build(rows)
    # ordinal class 0-3 -> index 1-4 so that 0 means MISSING to OpenCity's masked metrics
    return np.where(mask, vals + 1.0, np.nan), list(corridors), {
        "quantity": "congestion index = recorded class + 1 (1 free-flow .. 4 severe)",
        "reality": "REAL_LIVE (derived classes)"}


def metrla_smoke(n_nodes: int = 12, steps: int = 2000):
    """A real-data slice used ONLY to prove the CPU path runs end to end. Never a result."""
    d = np.load(OC / "data/METR_LA/METR_LA.npz")["data"][:steps, :n_nodes]
    a = np.load(OC / "data/METR_LA/METR_LA_rn_adj.npy")[:n_nodes, :n_nodes]
    return d.astype("float64"), [f"metr_la_{i}" for i in range(n_nodes)], a, {
        "quantity": "speed mph (METR-LA slice)", "reality": "REAL, IN OpenCity's pre-training corpus"}


def geo_adjacency(nodes: list[str]) -> np.ndarray:
    """Gaussian-kernel adjacency on corridor midpoints — the construction OpenCity's own PEMS
    graphs use (distance-based, thresholded). No node is left isolated, which `cal_lape` needs."""
    from core.common.data import reference_corridors as cz
    mid = {}
    for c in cz.CORRIDORS:
        (olat, olng), (dlat, dlng) = cz.coords(c)
        mid[c["id"]] = ((olat + dlat) / 2, (olng + dlng) / 2)
    pts = np.array([mid.get(n, (np.nan, np.nan)) for n in nodes])
    if np.isnan(pts).any():
        raise SystemExit("a node has no coordinates in src/dashboard/backend/corridors.py")
    dy = (pts[:, None, 0] - pts[None, :, 0]) * 111_000
    dx = (pts[:, None, 1] - pts[None, :, 1]) * 111_000 * np.cos(np.radians(pts[:, 0].mean()))
    dist = np.sqrt(dx ** 2 + dy ** 2)
    sigma = np.std(dist[dist > 0]) or 1.0
    K = np.exp(-(dist / sigma) ** 2)
    A = np.where(K >= 0.1, K, 0.0)
    # a far-flung corridor (the airport link) must still have one neighbour, or the Laplacian
    # encoding treats it as an isolated point: keep every node's nearest neighbour, symmetrically
    np.fill_diagonal(dist, np.inf)
    for i in range(len(nodes)):
        j = int(np.argmin(dist[i]))
        A[i, j] = A[j, i] = max(A[i, j], K[i, j])
    np.fill_diagonal(A, 1.0)
    return A.astype("float32")


# ----------------------------------------------------------------------------- the run
def persistence_reference(vals: np.ndarray, test_ratio: float = 1.0) -> dict:
    """Average-horizon masked MAE of 'hold the last value' over the same test windows."""
    x = np.nan_to_num(vals, nan=0.0)
    x = x[-int(x.shape[0] * test_ratio):]
    errs, n = 0.0, 0
    for t0 in range(0, x.shape[0] - HIS - PRED + 1):
        last = x[t0 + HIS - 1]
        y = x[t0 + HIS:t0 + HIS + PRED]
        m = y > 0
        errs += float(np.abs(np.repeat(last[None], PRED, 0)[m] - y[m]).sum()); n += int(m.sum())
    return {"mae": round(errs / n, 4) if n else None, "windows": x.shape[0] - HIS - PRED + 1}


def run(name: str, vals: np.ndarray, A: np.ndarray, batch: int, timeout: int,
        first_utc: str | None = None) -> dict:
    T, N = vals.shape
    if N < MIN_NODES:
        raise SystemExit(f"OpenCity needs >= {MIN_NODES} nodes (8 Laplacian eigenvectors); {name} has {N}")
    if T < MIN_STEPS:
        raise SystemExit(f"OpenCity's harness needs {MIN_STEPS} steps ({HIS}+{PRED} per test window "
                         f"plus one training window it insists on building); {name} has {T} — "
                         f"{(MIN_STEPS - T) * 5 / 60:.1f} h more of observation")
    test_ratio = round((T - TRAIN_KEEP) / T, 4)
    ddir = OC / "data" / name
    ddir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(ddir / f"{name}.npz", data=np.nan_to_num(vals, nan=0.0).astype("float32"))
    np.save(ddir / f"{name}_rn_adj.npy", A.astype("float32"))
    original = CONF.read_text()
    started = datetime.now(timezone.utc).isoformat()
    try:
        CONF.write_text(re.sub(r"^dataset_use\s*=.*$", f"dataset_use = ['{name}']", original,
                               count=1, flags=re.MULTILINE))
        boot = REPO / "core/ml/forecasting/opencity/_opencity_boot.py"
        cmd = [sys.executable, str(boot), "-mode", "test", "-model", "OpenCity",
               "-load_pretrain_path", WEIGHTS, "-batch_size", str(batch),
               "-test_ratio", str(test_ratio), "-val_ratio", "0.0",
               "--embed_dim", "512", "--skip_dim", "512", "--enc_depth", "6"]
        env = dict(os.environ, DF_OC_SCRIPT=str(OC / "model/Run.py"))
        if first_utc:
            # Asia/Dhaka is UTC+6 with no DST; time features start at the sample's real slot
            t = datetime.fromisoformat(first_utc).astimezone(timezone.utc)
            local_min = (t.hour * 60 + t.minute + 6 * 60) % 1440
            env["DF_OC_DAY_START"] = str(local_min // 5)
            env["DF_OC_WEEK_START"] = str(((t.weekday() + (1 if local_min < 6 * 60 else 0)) % 7) + 1)
        proc = subprocess.run(cmd, cwd=OC / "model", capture_output=True, text=True,
                              timeout=timeout, env=env)
        log = (proc.stdout or "") + (proc.stderr or "")
        m = METRIC_RE.search(log)
        status = "OK" if (proc.returncode == 0 and m) else "FAILED"
        metrics = ({"mae": float(m.group(1)), "rmse": float(m.group(2)), "mape": float(m.group(3))}
                   if m else {})
    except subprocess.TimeoutExpired:
        log, status, metrics = "timed out", "TIMEOUT", {}
    finally:
        CONF.write_text(original)
        shutil.rmtree(ddir, ignore_errors=True)          # the pinned checkout stays as it was
    shims = [ln for ln in log.splitlines() if ln.startswith("[opencity-boot]")]
    return {"status": status, "metrics": metrics, "started_utc": started, "log_tail": log[-3000:],
            "windows": int(T * test_ratio) - HIS - PRED + 1, "test_ratio": test_ratio,
            "compatibility_shims": shims,
            "upstream_edited": False}


def readiness(city: str = "dhaka") -> dict:
    """How far this city is from an OpenCity run, in the harness's own terms — for the interface."""
    try:
        vals, nodes, meta = from_observatory(city)
        T, N = vals.shape
    except SystemExit as exc:
        T, N, meta = 0, 0, {"note": str(exc)}
    smoke = OUT / "opencity_df_smoke.json"
    done = OUT / f"opencity_df_{city.lower()}_live.json"
    return {
        "city": city, "steps_have": int(T), "steps_need": MIN_STEPS, "nodes_have": int(N),
        "nodes_need": MIN_NODES,
        "hours_to_go": round(max(0, MIN_STEPS - T) * 5 / 60, 1),
        "ready": T >= MIN_STEPS and N >= MIN_NODES,
        "why": {"steps": f"{HIS} input + {PRED} label steps per test window, plus one training "
                         f"window the authors' harness always builds",
                "nodes": "8 Laplacian eigenvectors for the positional encoding (cal_lape)"},
        "source": meta,
        "cpu_path_verified": json.loads(smoke.read_text()) if smoke.exists() else None,
        "result": json.loads(done.read_text()) if done.exists() else None,
        "command": f"python -m core.ml.forecasting.opencity.opencity_city_eval --source observatory --city {city}",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", choices=["observatory", "recorded", "metrla-smoke"], default="observatory")
    p.add_argument("--city", default="dhaka")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--timeout", type=int, default=3600)
    a = p.parse_args()

    if a.source == "metrla-smoke":
        vals, nodes, A, meta = metrla_smoke()
        name = "DF_SMOKE"
    elif a.source == "observatory":
        vals, nodes, meta = from_observatory(a.city); A = geo_adjacency(nodes)
        name = f"DF_{a.city.upper()}_LIVE"
    else:
        vals, nodes, meta = from_recorded(); A = geo_adjacency(nodes)
        name = "DF_DHAKA_RECORDED"

    print(f"[opencity] {name}: T={vals.shape[0]} N={vals.shape[1]} ({meta['quantity']})")
    res = run(name, vals, A, a.batch_size, a.timeout, meta.get("first_utc"))
    ref = persistence_reference(vals, res.get("test_ratio", 1.0))
    rec = {"generated_utc": datetime.now(timezone.utc).isoformat(), "city": a.city, "source": a.source,
           "dataset_name": name, "shape": list(vals.shape), "nodes": nodes, **meta,
           "opencity": res | {"model": "OpenCity-plus", "weights": WEIGHTS,
                              "command": "Run.py -mode test -model OpenCity -test_ratio 1.0 (authors' harness)",
                              "hardware": "this machine, CPU" if not os.environ.get("CUDA_VISIBLE_DEVICES") else "GPU"},
           "persistence_same_windows": ref,
           "horizon": "average over 288 steps (24 h), as the authors report it",
           "claim": ("MECHANICS ONLY — this slice is inside OpenCity's pre-training corpus"
                     if a.source == "metrla-smoke" else
                     "zero-shot: the city is absent from OpenCity's pre-training corpus")}
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"opencity_{name.lower()}.json"
    out.write_text(json.dumps(rec, indent=1))
    print(f"[opencity] {res['status']}: {res['metrics'] or res['log_tail'][-600:]}")
    print(f"[opencity] persistence on the same {ref['windows']} windows: MAE {ref['mae']}")
    print(f"[opencity] wrote {out.relative_to(REPO)}")
    return 0 if res["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
