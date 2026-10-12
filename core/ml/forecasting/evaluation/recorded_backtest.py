"""Chronos-2, zero-shot, scored against recorded real readings: a rolling-origin backtest per city and dataset.

    PYTHONPATH=backend python -m core.ml.forecasting.evaluation.recorded_backtest          # METR-LA and DhaTraX

At each origin the series is cut, the model forecasts 15, 30 and 60 minutes ahead from that history alone, and the
forecast is scored against the reading the dataset holds for that later time. The history a series is given is the
same the app's own forecast uses (`operations/section_forecast.py`): the unbroken run of 5-minute readings that ends
at the origin, at least 8 of them. The floor is persistence, "the speed stays what it is now", scored on exactly the
same (origin, series, horizon) pairs. A pair whose later reading is missing is not scored; nothing is filled in.

Each city is scored on its own dataset, in that dataset's unit, and the two are never pooled:
  - Los Angeles: METR-LA (Li et al., DCRNN, ICLR 2018), the 24 stations inside the city's box, the last 7 days.
  - Dhaka: DhaTraX v1.0, the two located sites. The deposit holds ONE day per site, so this is a within-day result.

Chronos-2's forecast is deterministic (quantiles, no sampling), so there is no seed; the spread given is over days.
Whether METR-LA was in Chronos-2's pre-training corpus has not been verified (see the adapter).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from core.ml.forecasting.adapters.base import CityData, NotAvailable
from core.ml.forecasting.operations.section_forecast import BIN_MIN, HORIZONS_MIN, MIN_READINGS
from core.common.paths import REPO

OUT = REPO / "results/forecasting/recorded_backtest.json"
EVIDENCE = REPO / "evidence/live_forecast"
METR_NPZ = REPO / "data/forecasting/cities/metr_la.npz"
METR_H5 = REPO / "data/forecasting/cities/METR-LA/METR-LA.h5"
LA_STATIONS = REPO / "evidence/home/los_angeles/station_matching.json"
MAX_CONTEXT = 288             # one day of 5-minute readings
METR_DAYS, METR_STRIDE = 7, 3  # the last 7 days, an origin every 15 minutes


def unbroken_context(values: np.ndarray, t: int, cap: int = MAX_CONTEXT) -> np.ndarray:
    """Rows t-cap+1..t of a (T, N) array; in each column everything before its last gap is blanked, so only the
    unbroken run ending at t remains (a column without a reading at t is blanked entirely)."""
    ctx = values[max(0, t - cap + 1): t + 1].astype("float32").copy()
    gap = ~np.isfinite(ctx)
    for n in range(ctx.shape[1]):
        where = np.flatnonzero(gap[:, n])
        if len(where):
            ctx[: where[-1] + 1, n] = np.nan
    return ctx


def backtest(values: np.ndarray, origins: list[int], adapter, city_id: str, unit: str, horizons: list[int] = HORIZONS_MIN,
             groups: list[str] | None = None) -> dict:
    """Score `adapter` and persistence on the same pairs. `values` is (T, N) with NaN where there is no reading;
    `groups` names the group (a day) of each row, for the spread."""
    steps = {h: h // BIN_MIN for h in horizons}
    err: dict = {h: [] for h in horizons}              # (group, |model - truth|, |persistence - truth|)
    for t in origins:
        ctx = unbroken_context(values, t)
        usable = np.isfinite(ctx).sum(axis=0) >= MIN_READINGS
        if not usable.any():
            continue
        data = CityData(city_id=city_id, node_ids=[str(n) for n in range(ctx.shape[1])], values=ctx, interval_s=BIN_MIN * 60, unit=unit)
        try:
            f = adapter.forecast(data, horizons)
        except NotAvailable:
            continue
        for h in horizons:
            if t + steps[h] >= len(values):
                continue
            truth, pred = values[t + steps[h]], np.array(f.values[h], dtype="float64")
            for n in np.flatnonzero(usable & np.isfinite(truth) & np.isfinite(pred)):
                err[h].append((groups[t] if groups else "", abs(pred[n] - truth[n]), abs(values[t, n] - truth[n])))
    out = {}
    for h in horizons:
        if not err[h]:
            out[str(h)] = {"pairs": 0, "note": "no pair could be scored"}
            continue
        g = np.array([e[0] for e in err[h]])
        m, p = np.array([e[1] for e in err[h]]), np.array([e[2] for e in err[h]])
        row = {"pairs": len(m), "mae_model": round(float(m.mean()), 3), "mae_persistence": round(float(p.mean()), 3),
               "skill_vs_persistence": round(float(1 - m.mean() / p.mean()), 3) if p.mean() > 0 else None}
        days = sorted(set(g) - {""})
        if len(days) > 1:
            per = {d: (float(m[g == d].mean()), float(p[g == d].mean())) for d in days}
            row["per_day"] = {d: {"pairs": int((g == d).sum()), "mae_model": round(a, 3), "mae_persistence": round(b, 3)} for d, (a, b) in per.items()}
            row["mae_model_sd_over_days"] = round(float(np.std([a for a, _ in per.values()], ddof=1)), 3)
            row["mae_persistence_sd_over_days"] = round(float(np.std([b for _, b in per.values()], ddof=1)), 3)
            row["days_model_beats_persistence"] = sum(a < b for a, b in per.values())
        out[str(h)] = row
    return out


def metr_la() -> tuple[np.ndarray, list[int], list[str], dict]:
    import pandas as pd
    z = np.load(METR_NPZ)
    frame = pd.read_hdf(METR_H5)
    columns = [str(c) for c in frame.columns]
    stations = [s["station"] for s in json.loads(LA_STATIONS.read_text())["stations"]]
    last = METR_DAYS * 288
    values = np.where(z["mask"], z["values"], np.nan)[-(last + MAX_CONTEXT):, [columns.index(s) for s in stations]]
    stamps = frame.index[-(last + MAX_CONTEXT):]
    origins = list(range(MAX_CONTEXT, len(values) - 1, METR_STRIDE))     # from 00:00 of the first scored day
    return values, origins, [s.strftime("%Y-%m-%d") for s in stamps], {
        "city_id": "los_angeles", "dataset": "METR-LA (Li et al., DCRNN, ICLR 2018)", "unit": "mph", "series": f"the {len(stations)} stations inside the city's box",
        "stations": stations, "origins_from": str(stamps[origins[0]]), "origins_to": str(stamps[origins[-1]]), "origin_every_min": METR_STRIDE * BIN_MIN,
        "missing": "a 0.0 in METR-LA means no reading; such a time is never a context reading nor a scored target",
        "inputs": {str(METR_NPZ.relative_to(REPO)): _sha(METR_NPZ), str(METR_H5.relative_to(REPO)): _sha(METR_H5)}}


def dhatrax_site(site: dict) -> tuple[np.ndarray, list[int], dict]:
    from core.common.data.recorded import dhatrax
    rows = dhatrax.readings()[site["site"]]
    first, end = (datetime.fromisoformat(r) for r in (min(v["start"] for v in rows.values()), max(v["start"] for v in rows.values())))
    bins = int((end - first) / timedelta(minutes=BIN_MIN)) + 1
    values = np.full((bins, 1), np.nan)
    for v in rows.values():
        values[int((datetime.fromisoformat(v["start"]) - first) / timedelta(minutes=BIN_MIN)), 0] = v["median_kmh"]
    return values, list(range(MIN_READINGS - 1, bins - 1)), {
        "city_id": "dhaka", "dataset": dhatrax.CITATION, "unit": "km/h", "series": f"site {site['site']}, 5-minute median speed", "day": site["day"],
        "readings": len(rows), "bins": bins, "origin_every_min": BIN_MIN,
        "limits": f"one day at one site, so no spread over days exists; {dhatrax.CAVEAT}",
        "inputs": {k: v["sha256"] for k, v in json.loads((dhatrax.DIR / "MANIFEST.json").read_text())["files"].items()}}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    import importlib.metadata as md

    from core.common.data.recorded import dhatrax
    from core.ml.forecasting.adapters.chronos_adapter import Chronos2Adapter
    adapter, t0, results = Chronos2Adapter(), time.time(), []
    values, origins, days, meta = metr_la()
    print(f"[los_angeles] METR-LA: {values.shape[1]} stations, {len(origins)} origins", flush=True)
    results.append({**meta, "horizons_min": backtest(values, origins, adapter, "los_angeles", "mph", groups=days), "seconds": round(time.time() - t0, 1)})
    for site in dhatrax.sites():
        if not site["located"]:
            continue                                    # BS has no stated place and is left out (owner, 2026-10-06)
        t1 = time.time()
        values, origins, meta = dhatrax_site(site)
        print(f"[dhaka] DhaTraX {site['site']}: {meta['readings']} readings, {len(origins)} origins", flush=True)
        results.append({**meta, "horizons_min": backtest(values, origins, adapter, "dhaka", "km/h"), "seconds": round(time.time() - t1, 1)})
    snapshots = Path.home() / ".cache/huggingface/hub/models--amazon--chronos-2/snapshots"
    record = {
        "what": "Chronos-2 zero-shot against recorded real readings, with persistence on the same pairs. Each block is one city on one dataset; "
                "results are not pooled and a block says nothing about another city.",
        "run_utc": datetime.now(timezone.utc).isoformat(), "command": "PYTHONPATH=backend python -m core.ml.forecasting.evaluation.recorded_backtest",
        "model": {"name": adapter.name, "weights": adapter.model_id, "revision": sorted(p.name for p in snapshots.iterdir()) if snapshots.exists() else None,
                  "used": "as released, nothing trained, one series at a time through app/forecasting/adapters/chronos_adapter.py",
                  "deterministic": "quantile output, no sampling; there is no seed to vary",
                  "pretraining_exposure": "UNVERIFIED: whether METR-LA was in the pre-training corpus has not been checked"},
        "packages": {p: md.version(p) for p in ("chronos-forecasting", "torch", "transformers", "numpy")},
        "method": {"context": f"the unbroken run of 5-minute readings ending at the origin, at least {MIN_READINGS}, at most {MAX_CONTEXT}",
                   "persistence": "the reading at the origin, held", "metric": "mean absolute error in the dataset's own unit; skill = 1 - MAE/MAE of persistence",
                   "forecast_value": "the model's median (0.5 quantile)"},
        "results": results}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=1))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "recorded_backtest.json").write_text(OUT.read_text())
    (EVIDENCE / "recorded_backtest.sha256").write_text(f"{_sha(OUT)}  recorded_backtest.json\n")
    for r in results:
        for h, row in r["horizons_min"].items():
            print(r["city_id"], "|", r["series"], "|", h, "min |", {k: v for k, v in row.items() if k != "per_day"})
    print("wrote", OUT.relative_to(REPO), "and", EVIDENCE.relative_to(REPO), file=sys.stderr)


if __name__ == "__main__":
    main()
