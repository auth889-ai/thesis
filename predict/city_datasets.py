#!/usr/bin/env python3
"""One interface for ANY city's traffic sensor data.

    python predict/city_datasets.py --list                  # what is available and where
    python predict/city_datasets.py --city METR-LA          # load, validate, summarise
    python predict/city_datasets.py --city METR-LA --export predict/data/cities/metr_la.npz

The forecasting and federated code must not care which city it is looking at. This module is the
only place that knows about file formats, so a new city is added by registering a loader, not by
editing the models.

Every city resolves to the same object:

    CityData(values (T,N) float32, mask (T,N) bool, adjacency (N,N)|None, coords (N,2)|None,
             bin_seconds, sensor_ids, meta)

`mask` is the honest part: METR-LA and PEMS-BAY encode a missing reading as 0.0, which is also a
legal speed, so a loader that forgets this trains the model to predict "0 km/h" for sensor outages.
Here missing is ALWAYS carried in `mask` and never silently imputed.

Registered cities
    METR-LA     207 loop detectors, Los Angeles, 5 min, 4 months (Li et al., ICLR 2018) — REAL
    PEMS-BAY    325 loop detectors, Bay Area, 5 min, 6 months (Li et al., ICLR 2018)     — REAL
    PEMS04/08   307/170 detectors, California, 5 min (Guo et al., AAAI 2019)             — REAL
    DHAKA-TWIN  250 virtual sensors on the real Dhaka R1 network                          — SIMULATED
    DHAKA-LIVE  6 corridors, derived congestion classes from a live API                   — REAL, tiny

Reality labels travel with the data; nothing downstream can silently mix a simulated city into a
real-world claim.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
CITY_DIR = REPO / "predict/data/cities"


@dataclass
class CityData:
    name: str
    values: np.ndarray            # (T, N) float32, the target quantity
    mask: np.ndarray              # (T, N) bool, True = observed
    bin_seconds: int
    quantity: str
    reality: str                  # REAL | SIMULATED
    adjacency: np.ndarray | None = None
    coords: np.ndarray | None = None
    sensor_ids: list | None = None
    meta: dict = field(default_factory=dict)

    def summary(self) -> dict:
        T, N = self.values.shape
        obs = self.values[self.mask]
        return {"city": self.name, "timesteps": int(T), "sensors": int(N), "bin_seconds": self.bin_seconds,
                "span_days": round(T * self.bin_seconds / 86400, 2), "quantity": self.quantity,
                "reality": self.reality, "coverage": round(float(self.mask.mean()), 4),
                "value_min": round(float(obs.min()), 2) if obs.size else None,
                "value_mean": round(float(obs.mean()), 2) if obs.size else None,
                "value_max": round(float(obs.max()), 2) if obs.size else None,
                "has_adjacency": self.adjacency is not None, "has_coords": self.coords is not None,
                **self.meta}

    def validate(self) -> list[str]:
        """Return a list of problems. Empty means the city is usable for forecasting."""
        p = []
        T, N = self.values.shape
        if self.values.shape != self.mask.shape:
            p.append(f"values {self.values.shape} and mask {self.mask.shape} disagree")
        if T < 100:
            p.append(f"only {T} timesteps — too short to split train/test meaningfully")
        if self.mask.mean() < 0.5:
            p.append(f"coverage {self.mask.mean():.1%} is below 50%")
        if np.isnan(self.values[self.mask]).any():
            p.append("NaN inside observed entries (mask says observed but value is NaN)")
        if self.adjacency is not None and self.adjacency.shape != (N, N):
            p.append(f"adjacency {self.adjacency.shape} does not match {N} sensors")
        if self.coords is not None and len(self.coords) != N:
            p.append(f"coords {len(self.coords)} do not match {N} sensors")
        dead = (~self.mask).all(axis=0).sum()
        if dead:
            p.append(f"{dead} sensors never observed")
        return p


def _load_h5(city: str, d: Path, quantity: str) -> CityData:
    """METR-LA / PEMS-BAY: a pandas HDF frame (time x sensor); 0.0 encodes a missing reading."""
    import pandas as pd
    df = pd.read_hdf(next(d.glob("*.h5")))
    v = df.values.astype("float32")
    adj = coords = None
    pk = list(d.glob("adj_*.pkl"))
    if pk:
        obj = pickle.load(open(pk[0], "rb"), encoding="latin1")
        arr = next((x for x in (obj if isinstance(obj, (list, tuple)) else [obj])
                    if isinstance(x, np.ndarray) and x.ndim == 2), None)
        adj = arr.astype("float32") if arr is not None else None
    freq = int((df.index[1] - df.index[0]).total_seconds()) if len(df.index) > 1 else 300
    return CityData(city, v, v > 0, freq, quantity, "REAL", adj, coords,
                    [str(c) for c in df.columns],
                    {"source": str(next(d.glob('*.h5')).relative_to(REPO)),
                     "first": str(df.index[0]), "last": str(df.index[-1]),
                     "missing_encoding": "0.0 means no reading (carried in mask, never imputed)"})


def _load_pems_npz(city: str, d: Path, quantity: str) -> CityData:
    """PEMS03/04/07/08: data.npz with (T, N, C); channel 0 is flow."""
    z = np.load(next(d.glob("*.npz")))
    arr = z["data"] if "data" in z else z[list(z.files)[0]]
    v = arr[..., 0].astype("float32") if arr.ndim == 3 else arr.astype("float32")
    adj = None
    csv = list(d.glob("*.csv"))
    if csv:
        import csv as _csv
        n = v.shape[1]
        adj = np.zeros((n, n), dtype="float32")
        with open(csv[0]) as fh:
            for row in _csv.DictReader(fh):
                try:
                    adj[int(row["from"]), int(row["to"])] = 1.0
                except (KeyError, ValueError):
                    pass
    return CityData(city, v, np.isfinite(v), 300, quantity, "REAL", adj, None, None,
                    {"source": str(next(d.glob('*.npz')).relative_to(REPO))})


def _load_dhaka_twin(city: str, d: Path, quantity: str) -> CityData:
    z = np.load(REPO / "predict/data/dhaka_twin/data.npz", allow_pickle=True)
    v = z["data"][..., 0].astype("float32")
    m = z["mask"].astype(bool) if "mask" in z else np.isfinite(v)
    nodes = json.loads((REPO / "predict/data/dhaka_twin/sensor_nodes.json").read_text())
    coords = np.array([[n["x"], n["y"]] for n in nodes], dtype="float32") if isinstance(nodes, list) else None
    return CityData(city, np.nan_to_num(v), m, 300, quantity, "SIMULATED",
                    z["adjacency"].astype("float32") if "adjacency" in z else None, coords,
                    [n["edge_id"] for n in nodes] if isinstance(nodes, list) else None,
                    {"label": "DHAKA_SIMULATED_SENSOR_GRAPH",
                     "never": "may not support a real-world claim"})


def _load_dhaka_live(city: str, d: Path, quantity: str) -> CityData:
    z = np.load(REPO / "predict/data/live_dhaka/series.npz", allow_pickle=True)
    return CityData(city, np.nan_to_num(z["values"]).astype("float32"), z["mask"].astype(bool), 300,
                    quantity, "REAL", None, None, [str(c) for c in z["corridors"]],
                    {"provider": "google_routes", "google_data_mode": "RUNTIME_REFERENCE",
                     "caution": "derived congestion CLASSES (0-3), not speeds; short history"})


REGISTRY: dict[str, dict] = {
    "METR-LA":    {"dir": CITY_DIR / "METR-LA",  "loader": _load_h5,        "quantity": "speed_mph",
                   "paper": "Li et al., DCRNN, ICLR 2018", "sensors": 207},
    "PEMS-BAY":   {"dir": CITY_DIR / "PEMS-BAY", "loader": _load_h5,        "quantity": "speed_mph",
                   "paper": "Li et al., DCRNN, ICLR 2018", "sensors": 325},
    "PEMS04":     {"dir": CITY_DIR / "PEMS04",   "loader": _load_pems_npz,  "quantity": "flow_veh",
                   "paper": "Guo et al., ASTGCN, AAAI 2019", "sensors": 307},
    "PEMS08":     {"dir": CITY_DIR / "PEMS08",   "loader": _load_pems_npz,  "quantity": "flow_veh",
                   "paper": "Guo et al., ASTGCN, AAAI 2019", "sensors": 170},
    "DHAKA-TWIN": {"dir": REPO / "predict/data/dhaka_twin", "loader": _load_dhaka_twin, "quantity": "speed_ms",
                   "paper": "this project (simulated)", "sensors": 250},
    "DHAKA-LIVE": {"dir": REPO / "predict/data/live_dhaka", "loader": _load_dhaka_live, "quantity": "congestion_level",
                   "paper": "this project (live API)", "sensors": 6},
}


DRIVE_REMOTE = "gdrive2tb:dhakaflow/predict/raw_data"     # the 2 TB Drive is the source of truth


def fetch_from_drive(city: str) -> bool:
    """Pull a city from the 2 TB Drive. Datasets live there, not on the laptop; a local copy is a
    transient working cache that `--purge-local` removes."""
    import subprocess
    e = REGISTRY.get(city)
    if not e:
        return False
    e["dir"].mkdir(parents=True, exist_ok=True)
    print(f"[fetch] {DRIVE_REMOTE}/{city} -> {e['dir'].relative_to(REPO)}")
    r = subprocess.run(["rclone", "copy", f"{DRIVE_REMOTE}/{city}", str(e["dir"])],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"[fetch] failed: {r.stderr.strip()[-300:]}")
    return available(city)


def purge_local(city: str) -> int:
    """Delete the local working copy (the Drive keeps the data)."""
    import shutil
    e = REGISTRY.get(city)
    if not e or not e["dir"].exists() or "data/cities" not in str(e["dir"]):
        return 0
    n = sum(f.stat().st_size for f in e["dir"].rglob("*") if f.is_file())
    shutil.rmtree(e["dir"])
    return n


def available(city: str) -> bool:
    e = REGISTRY.get(city)
    if not e or not e["dir"].exists():
        return False
    return any(e["dir"].glob("*.h5")) or any(e["dir"].glob("*.npz")) or any(e["dir"].glob("*.json"))


def load_city(city: str) -> CityData:
    if city not in REGISTRY:
        raise SystemExit(f"unknown city {city!r}; registered: {', '.join(REGISTRY)}")
    e = REGISTRY[city]
    if not available(city) and not fetch_from_drive(city):
        raise SystemExit(f"{city} is not on this machine and could not be fetched from "
                         f"{DRIVE_REMOTE}/{city}. Check `rclone lsf {DRIVE_REMOTE}/`.")
    cd = e["loader"](city, e["dir"], e["quantity"])
    cd.meta |= {"paper": e["paper"], "expected_sensors": e["sensors"]}
    return cd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true")
    p.add_argument("--city")
    p.add_argument("--export", type=Path, help="write a standard .npz the models consume")
    p.add_argument("--fetch", action="store_true", help="pull the city from the 2 TB Drive")
    p.add_argument("--purge-local", action="store_true",
                   help="delete local working copies; the Drive keeps the data")
    a = p.parse_args()
    if a.purge_local:
        freed = sum(purge_local(c) for c in (([a.city] if a.city else list(REGISTRY))))
        print(f"freed {freed / 1e6:.0f} MB of local working copies; source of truth stays at {DRIVE_REMOTE}")
        return 0
    if a.fetch and a.city:
        ok = fetch_from_drive(a.city)
        print(f"{a.city}: {'available' if ok else 'FETCH FAILED'}")
        return 0 if ok else 1
    if a.list or not a.city:
        print(f"{'city':<12} {'present':<8} {'sensors':>8}  paper / source")
        for k, e in REGISTRY.items():
            print(f"{k:<12} {'yes' if available(k) else 'no':<8} {e['sensors']:>8}  {e['paper']}")
        print("\nA missing city is fetched into its directory; no loader change is needed.")
        return 0
    cd = load_city(a.city)
    print(json.dumps(cd.summary(), indent=1))
    problems = cd.validate()
    print("validation:", "OK" if not problems else "PROBLEMS")
    for x in problems:
        print("  -", x)
    if a.export:
        a.export.parent.mkdir(parents=True, exist_ok=True)
        np.savez(a.export, values=cd.values, mask=cd.mask,
                 **({"adjacency": cd.adjacency} if cd.adjacency is not None else {}),
                 **({"coords": cd.coords} if cd.coords is not None else {}))
        a.export.with_suffix(".json").write_text(json.dumps(cd.summary(), indent=1))
        print(f"wrote {a.export} (+ .json summary)")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
