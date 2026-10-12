"""Weak-signal results: the browser rows from run files, the plain numbers from the same rows, the energy rows on the real route with
synthetic profiles (deterministic, labelled), and "no data" before any run."""
from __future__ import annotations

import json

from core.networking.v2x import energy
from core.networking.prefetch import results as pr


def run(cond, arm, i, ms, mb, offline=None, ok=True, pack=0):
    req = [{"url": "http://x/api/tiles/dhaka/basemap.pmtiles", "bytes": pack, "ms": 10, "after": False}] if pack else []
    return {"condition": cond, "arm": arm, "run": i, "ok": ok, "time_to_route_ms": ms, "app_bytes": mb * 1048576, "map_view_bytes": 0, "service_workers_throttled": 1,
            "continues_offline": offline, "requests": req, "base": "http://x"}


def test_no_runs_no_data(tmp_path):
    assert pr.build(results=tmp_path, evidence=None)["available"] is False
    assert pr.read(tmp_path)["available"] is False


def test_rows_plain_and_energy(tmp_path):
    (tmp_path / "runs").mkdir()
    runs = [run("2g_like", "without_prefetch", i, 40000 + i, 1.0) for i in (1, 2, 3)] + [run("2g_like", "with_prefetch", i, 3000 + i, 0.1, pack=2_000_000) for i in (1, 2, 3)] \
        + [run("offline_mid_route", "with_prefetch", i, 900, 0.1, offline=True, pack=2_000_000) for i in (1, 2, 3)] + [run("offline_mid_route", "without_prefetch", 1, 900, 1.0, offline=False)]
    for k, r in enumerate(runs):
        (tmp_path / "runs" / f"{k}.json").write_text(json.dumps(r))
    out = pr.build(results=tmp_path, evidence=None)
    assert out["plain"] == pr.plain_numbers(out["rows"]) == {"slow_without_s": 40.0, "slow_with_s": 3.0, "offline_with": "3 of 3", "offline_without": "0 of 1"}
    e = out["energy"]
    assert e["label"] == energy.LABEL and "SYNTHETIC" in e["profiles"] and len(e["rows"]) == 9
    assert all(r["bartendr_j"] <= r["as_needed_j"] + 1e-6 for r in e["rows"] if r["bartendr_j"] is not None)   # the optimum is never worse than fetching as needed
    assert pr.profile(100, 0.3, 1) == pr.profile(100, 0.3, 1) and pr.profile(100, 0.3, 1).count("weak") >= 30
