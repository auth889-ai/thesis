"""ANY CITY, YOUR DATA: a CSV the user uploads becomes a dataset every model can serve.

Two layouts are accepted, both common in the traffic corpora on GitHub (LibCity's `.dyna`, the
METR-LA / PEMS `.h5` exports, the OpenCity demo CSV):

    wide    time, <road 1>, <road 2>, ...            one column per road / sensor
    long    time, road, value                        one row per (time, road)

The road graph, which the graph models need, comes from the first of: an uploaded adjacency
(`.npy`, N x N), a coordinates CSV (`road, lat, lon` -> the distance kernel OpenCity's PEMS
graphs use), or — with neither — the correlation of the series themselves, thresholded and
with every road's nearest neighbour kept so no node is isolated. What the graph was built from
is written in the dataset's card; nothing is guessed silently.

Files land under results/live/user_datasets/<id>/ in the exact layout the OpenCity CSV path reads
(`<id>.csv` + `<id>_rn_adj.npy`), plus `<id>.npz` and `meta.json` for the other models.
"""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import config

ROOT = config.REPO / "results/live/user_datasets"
QUANTITIES = {"speed_kmh": "speed km/h", "speed_mph": "speed mph", "flow": "vehicles per interval",
              "occupancy": "occupancy %", "index": "congestion index", "travel_time_s": "travel time s"}


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]
    return s or "upload"


def _parse(csv_bytes: bytes):
    import pandas as pd
    df = pd.read_csv(io.BytesIO(csv_bytes))
    if df.shape[1] < 2:
        raise ValueError("the CSV needs a time column and at least one value column")
    cols = {c.lower().strip(): c for c in df.columns}
    tcol = next((cols[k] for k in ("time", "timestamp", "datetime", "date", "utc") if k in cols), df.columns[0])
    rcol = next((cols[k] for k in ("road", "sensor", "node", "segment", "corridor", "link", "id", "region") if k in cols), None)
    vcol = next((cols[k] for k in ("value", "speed", "flow", "count", "travel_time", "index") if k in cols), None)
    if rcol is not None and vcol is not None and df.shape[1] >= 3:      # long layout
        wide = df.pivot_table(index=tcol, columns=rcol, values=vcol, aggfunc="mean")
        wide.columns = [str(c) for c in wide.columns]
        wide = wide.reset_index()
    else:
        wide = df
    t = pd.to_datetime(wide[tcol], errors="coerce", utc=True)
    if t.isna().all():
        raise ValueError(f"could not read the time column '{tcol}' — use ISO timestamps such as 2026-09-01 07:00")
    wide = wide.loc[~t.isna()].copy(); t = t[~t.isna()]
    order = np.argsort(t.values, kind="stable")
    wide, t = wide.iloc[order], t.iloc[order]
    nodes = [str(c) for c in wide.columns if c != tcol]
    vals = wide[nodes].apply(pd.to_numeric, errors="coerce").to_numpy(dtype="float64")
    if vals.shape[0] < 2:
        raise ValueError("at least two time steps are needed")
    steps = np.diff(t.values.astype("datetime64[s]").astype("int64"))
    interval = int(np.median(steps)) if len(steps) else 300
    return vals, nodes, [x.isoformat() for x in t.dt.to_pydatetime()], max(60, interval)


def _adjacency(vals: np.ndarray, nodes: list[str], adj_bytes: bytes | None, coords_bytes: bytes | None):
    n = len(nodes)
    if adj_bytes:
        A = np.load(io.BytesIO(adj_bytes))
        if A.shape != (n, n):
            raise ValueError(f"adjacency is {A.shape}, the CSV has {n} roads")
        return A.astype("float32"), "uploaded adjacency"
    if coords_bytes:
        import pandas as pd
        c = pd.read_csv(io.BytesIO(coords_bytes))
        cols = {x.lower().strip(): x for x in c.columns}
        rc = next((cols[k] for k in ("road", "sensor", "node", "id", "name") if k in cols), c.columns[0])
        la = next((cols[k] for k in ("lat", "latitude") if k in cols), None)
        lo = next((cols[k] for k in ("lon", "lng", "longitude") if k in cols), None)
        if la is None or lo is None:
            raise ValueError("the coordinates CSV needs lat and lon columns")
        by = {str(r[rc]): (float(r[la]), float(r[lo])) for _, r in c.iterrows()}
        missing = [x for x in nodes if x not in by]
        if missing:
            raise ValueError(f"no coordinates for {missing[:5]}")
        pts = np.array([by[x] for x in nodes])
        dy = (pts[:, None, 0] - pts[None, :, 0]) * 111_000
        dx = (pts[:, None, 1] - pts[None, :, 1]) * 111_000 * np.cos(np.radians(pts[:, 0].mean()))
        dist = np.sqrt(dx ** 2 + dy ** 2)
        sigma = np.std(dist[dist > 0]) or 1.0
        K = np.exp(-(dist / sigma) ** 2)
        A = np.where(K >= 0.1, K, 0.0)
        how = "distance kernel on the uploaded coordinates (OpenCity's PEMS construction)"
    else:
        with np.errstate(invalid="ignore"):
            X = np.where(np.isnan(vals), np.nanmean(vals, axis=0), vals)
            X = X - X.mean(axis=0)
            sd = X.std(axis=0); sd[sd == 0] = 1.0
            Cm = (X / sd).T @ (X / sd) / max(1, X.shape[0])
        A = np.where(np.abs(Cm) >= 0.5, np.abs(Cm), 0.0)
        dist = 1.0 - np.abs(Cm)
        how = "series correlation (no coordinates or adjacency were uploaded)"
    np.fill_diagonal(A, 1.0)
    np.fill_diagonal(dist, np.inf)
    for i in range(n):                                   # no isolated node: the Laplacian encoding needs it
        j = int(np.argmin(dist[i]))
        if n > 1 and A[i, j] == 0:
            A[i, j] = A[j, i] = max(0.1, float(A[i, j]))
    return A.astype("float32"), how


def save(name: str, csv_bytes: bytes, quantity: str = "speed_kmh", adj_bytes: bytes | None = None,
         coords_bytes: bytes | None = None) -> dict:
    vals, nodes, times, interval = _parse(csv_bytes)
    A, graph_from = _adjacency(vals, nodes, adj_bytes, coords_bytes)
    did = _slug(name)
    d = ROOT / did
    d.mkdir(parents=True, exist_ok=True)
    np.savez(d / f"{did}.npz", data=vals)
    np.save(d / f"{did}_rn_adj.npy", A)
    import pandas as pd
    pd.DataFrame(vals, columns=nodes).assign(time=times)[["time", *nodes]].to_csv(d / f"{did}.csv", index=False)
    meta = {"id": did, "name": name, "nodes": nodes, "steps": int(vals.shape[0]), "interval_s": interval,
            "quantity": QUANTITIES.get(quantity, quantity), "quantity_key": quantity, "graph_from": graph_from,
            "first_utc": times[0], "last_utc": times[-1], "uploaded_utc": datetime.now(timezone.utc).isoformat(),
            "missing_fraction": round(float(np.isnan(vals).mean()), 4)}
    (d / "meta.json").write_text(json.dumps(meta, indent=1))
    return meta


def load_meta(did: str) -> dict | None:
    f = ROOT / did / "meta.json"
    return json.loads(f.read_text()) if f.exists() else None


def paths(did: str) -> dict[str, Path]:
    d = ROOT / did
    return {"csv": d / f"{did}.csv", "adj": d / f"{did}_rn_adj.npy", "npz": d / f"{did}.npz"}


def models_for(meta: dict) -> list[str]:
    n, T = len(meta["nodes"]), meta["steps"]
    return ((["OpenCity-plus"] if T >= 288 and n >= 9 and meta["interval_s"] == 300 else [])
            + (["Chronos-Bolt"] if T >= 8 else []) + ["persistence"])


def datasets() -> list[dict]:
    out = []
    for d in sorted(ROOT.iterdir()) if ROOT.exists() else []:
        m = load_meta(d.name)
        if not m:
            continue
        out.append({"id": f"user:{m['id']}", "name": f"{m['name']} — your upload ({len(m['nodes'])} roads, every {m['interval_s'] // 60} min)",
                    "node_names": m["nodes"], "nodes": len(m["nodes"]), "steps": m["steps"], "start_utc": m["first_utc"],
                    "interval_min": m["interval_s"] // 60, "exposure": "HELD_OUT_ZERO_SHOT", "user": True,
                    "graph_from": m["graph_from"], "quantity": m["quantity"], "models": models_for(m)})
    return out


def series(did: str, region: int):
    m = load_meta(did)
    if not m:
        raise FileNotFoundError(f"no uploaded dataset '{did}'")
    p = paths(did)
    vals = np.load(p["npz"])["data"].astype("float64")
    A = np.load(p["adj"])
    order = [region] + [i for i in range(vals.shape[1]) if i != region]
    return vals[:, order], [m["nodes"][i] for i in order], A[np.ix_(order, order)].astype("float32"), {
        "quantity": m["quantity"], "reality": "USER_UPLOAD", "first_utc": m["first_utc"], "interval_s": m["interval_s"],
        "region_index": region, "subgraph": order, "graph_from": m["graph_from"]}
