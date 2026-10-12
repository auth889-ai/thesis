"""Works with weak signal — the experiment's results (Q3). Two parts, both SIMULATED (an emulated network, synthetic signal profiles):

1. The browser runs (frontend/tests/weak_signal.experiment.cjs): per emulated condition and arm (with / without the trip pack), the
   median time until the route is usable, the MB received, and whether the trip continued offline.
2. The estimated radio energy of the measured trip pack (Bartendr, ACM MobiCom 2010; core.networking.v2x.energy), on the real Dhaka route
   (evidence/routing/live_routes.json) cut into 100 m steps (core.simulation.routing.signal.steps), under SYNTHETIC signal profiles with weak
   stretches over 10, 30 and 50 % of the route (3 seeds each): saved now on a strong signal, fetched as needed along the drive, and
   Bartendr's minimum-energy schedule. Labelled "estimated from Bartendr's Palm Pre measurements, not measured on our phones".

    python -m core.networking.prefetch.results        # results/networking/prefetch/summary.json + evidence/prefetch/
"""
from __future__ import annotations

import hashlib
import json
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

from core.networking.v2x import energy
from core.simulation.routing import signal

REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "results/networking/prefetch"
EVIDENCE = REPO / "evidence/prefetch"
ROUTE = REPO / "evidence/routing/live_routes.json"
WEAK_SHARES = (0.1, 0.3, 0.5)
SEEDS = (1, 2, 3)
THR = {"strong": 500_000, "medium": 250_000, "weak": 125_000, "none": 0, "unknown": 250_000}  # strong = the fast-4G preset; medium and weak at Bartendr's measured ratios (-90 RSSI "50% lower" throughput; weak "25% throughput"), so the estimate stays inside the paper's measured range (energy per bit at most 6x)
MAX_CHUNKS = 200
MASTS = EVIDENCE / "masts/summary.json"          # R3 (2026-10-11): the Q3 profile from real OSM mast positions (make prefetch-masts), shown next to the synthetic rows


def profile(n_steps: int, weak_share: float, seed: int) -> list[str]:
    """A SYNTHETIC signal profile: weak runs of 3-10 steps placed at random until `weak_share` of the steps are weak; one tunnel of
    2 steps; the rest alternating strong and medium in runs of 5-15 steps."""
    rng = random.Random(f"{n_steps}-{weak_share}-{seed}")
    bins, i = [], 0
    while len(bins) < n_steps:
        bins += [rng.choice(["strong", "strong", "medium"])] * rng.randint(5, 15)
    bins = bins[:n_steps]
    target = round(weak_share * n_steps)
    while bins.count("weak") < target:
        start, length = rng.randrange(n_steps), rng.randint(3, 10)
        for j in range(start, min(n_steps, start + length)):
            bins[j] = "weak"
    t = rng.randrange(n_steps - 2)
    bins[t] = bins[t + 1] = "none"
    return bins


def energy_rows(pack_bytes: int, route: dict) -> list[dict]:
    """The three schedules' estimated energy for one pack on the real route, per synthetic profile."""
    shape = route["routes"][0]["geometry"]
    total_s = route["routes"][0]["summary"]["time_s"]
    st = signal.steps(shape)
    secs = [max(1.0, total_s * (s["end_m"] - s["start_m"]) / max(st[-1]["end_m"], 1)) for s in st]
    chunks = min(MAX_CHUNKS, -(-pack_bytes // energy.CHUNK_BYTES))
    chunk = max(1, pack_bytes // max(chunks, 1))
    needed = [0] * len(st)
    for c in range(chunks):
        needed[min(len(st) - 1, c * len(st) // chunks)] += 1                    # as needed: the map ahead of each step, spread evenly along the route
    rows = []
    for share in WEAK_SHARES:
        for seed in SEEDS:
            bins = profile(len(st), share, seed)
            steps = [{"bin": b, "t_s": t} for b, t in zip(bins, secs)]
            plan = energy.bartendr(steps, chunks, THR, chunk)
            now, asneed = energy.now_j(chunks, THR, chunk), energy.as_needed_j(steps, needed, THR, chunk)
            rows.append({"weak_share": share, "seed": seed, "steps": len(st), "pack_bytes": pack_bytes, "chunks": chunks,
                         "now_j": round(now, 1), "as_needed_j": round(asneed, 1), "bartendr_j": round(plan["energy_j"], 1) if plan["feasible"] else None,
                         "bartendr_bursts": plan["bursts"], "saving_vs_as_needed_pct": round(100 * (1 - plan["energy_j"] / asneed), 1) if plan["feasible"] and asneed else None,
                         "now_vs_as_needed_pct": round(100 * (1 - now / asneed), 1) if asneed else None})
    return rows


def browser_rows(runs: list[dict]) -> list[dict]:
    out = []
    for cond in sorted({r["condition"] for r in runs}):
        for arm in ("without_prefetch", "with_prefetch"):
            rs = [r for r in runs if r["condition"] == cond and r["arm"] == arm]
            if not rs:
                continue
            ok = [r for r in rs if r.get("ok")]
            times = [r["time_to_route_ms"] for r in ok if r.get("time_to_route_ms") is not None]
            mbs = [r.get("app_bytes", r.get("bytes_received", 0)) / 1048576 for r in ok if r.get("app_bytes", r.get("bytes_received")) is not None]
            view = [r["map_view_bytes"] / 1048576 for r in ok if r.get("map_view_bytes") is not None]
            off = [r["continues_offline"] for r in ok if r.get("continues_offline") is not None]
            out.append({"condition": cond, "arm": arm, "runs": len(rs), "failed": len(rs) - len(ok), "route_shown": f"{len(times)} of {len(rs)}",
                        "median_time_to_route_s": round(statistics.median(times) / 1000, 1) if times else None,
                        "time_range_s": [round(min(times) / 1000, 1), round(max(times) / 1000, 1)] if times else None,
                        "median_mb": round(statistics.median(mbs), 3) if mbs else None,                      # this app's own data over the emulated network
                        "median_map_view_mb": round(statistics.median(view), 2) if view else None,            # the normal map view's tiles (OpenFreeMap), never prefetched
                        "service_worker_throttled": all(r.get("service_workers_throttled", 0) >= 1 for r in ok) if ok else None,
                        "continues_offline": f"{sum(off)} of {len(off)}" if off else None})
    return out


def plain_numbers(rows: list[dict]) -> dict | None:
    """The Home sentence's numbers, from the same rows as the Research table: on the 2G-like network, the median time to the route
    without and with the saved trip; and how many offline-mid-route runs continued with the saved trip."""
    def get(cond, arm, key):
        return next((r[key] for r in rows if r["condition"] == cond and r["arm"] == arm), None)
    without, with_ = get("2g_like", "without_prefetch", "median_time_to_route_s"), get("2g_like", "with_prefetch", "median_time_to_route_s")
    off = get("offline_mid_route", "with_prefetch", "continues_offline")
    if without is None and with_ is None and off is None:
        return None
    return {"slow_without_s": without, "slow_with_s": with_, "offline_with": off, "offline_without": get("offline_mid_route", "without_prefetch", "continues_offline")}   # both arms: the app shell alone also keeps the last answers


def build(results: Path = RESULTS, evidence: Path | None = EVIDENCE) -> dict:
    runs = [json.loads(f.read_text()) for f in sorted((results / "runs").glob("*.json"))] if (results / "runs").exists() else []
    if not runs:
        return {"available": False, "reason": "no data: the experiment has not been run (node frontend/tests/weak_signal.experiment.cjs)"}
    rows = browser_rows(runs)
    packs = [sum(q["bytes"] for q in r.get("requests", []) if not q.get("after") and (q["url"].startswith(r["base"]))) for r in runs if r["arm"] == "with_prefetch" and r.get("ok")]   # everything this app fetched before the condition: the shell, the route and the pack
    pack_bytes = int(statistics.median([p for p in packs if p])) if any(packs) else None
    route = json.loads(ROUTE.read_text())["answers"]["dhaka"] if ROUTE.exists() else None
    erows = energy_rows(pack_bytes, route) if pack_bytes and route else []
    out = {"available": True, "label": "SIMULATED", "built_utc": datetime.now(timezone.utc).isoformat(),
           "network": "emulated in headless Chromium (CDP); presets fast 4G 4/3 Mbit/s 20 ms, slow 3G 400/400 kbit/s 400 ms, 2G-like 50/20 kbit/s 1000 ms, offline 10 s after the route",
           "runs_total": len(runs), "rows": rows, "pack_bytes_median": pack_bytes,
           "energy": {"label": energy.LABEL, "profiles": "SYNTHETIC: weak stretches over 10, 30 and 50 % of the real Dhaka route, 3 seeds each, one 200 m tunnel",
                      "throughput_bytes_per_s": THR, "power_w": {b: energy.P_DATA_W * energy.POWER[b] for b in energy.POWER}, "tail_j": energy.TAIL_J,
                      "rows": erows, "note": None if erows else "no pack size measured, so no energy estimate",
                      "throughput_rule": "strong = the fast-4G preset (4 Mbit/s); medium and weak at Bartendr's measured throughput ratios (1/2 and 1/4), not the slower emulated presets, so the estimate stays within what the paper measured"},
           "not_measured": "offline, the map: whether our own tiles were drawn after the network was cut (the route answers stayed on screen in both arms because the app shell keeps its last answers)",
           "references": ["Bartendr: Schulman, Navda, Ramjee, Spring, ACM MobiCom 2010", "BreadCrumbs: Nicholson, Noble, ACM MobiCom 2008", "Borkowski, Skarlat, Schulte, Dustdar, IEEE MS 2016 (secondary)"]}
    out["plain"] = plain_numbers(rows)
    out["sha256"] = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    (results).mkdir(parents=True, exist_ok=True)
    (results / "summary.json").write_text(json.dumps(out, indent=1))
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "summary.json").write_text(json.dumps(out, indent=1))
        (evidence / "summary.sha256").write_text(out["sha256"] + "\n")
    return out


def masts_row(path: Path | None = None) -> dict | None:
    """The energy row of the profile from real OpenStreetMap mast positions (core/networking/prefetch/masts.py, step Q3), read from its
    summary file; None until `make prefetch-masts` has run. Every number is that file's; the saved synthetic rows are not touched."""
    path = path or MASTS
    if not path.exists():
        return None
    d = json.loads(path.read_text())
    e = d["energy"]["on_this_profile"]
    total = sum(d["metres"].values()) or 1
    return {"label": d["label"], "radio_sites": d["radio_sites"], "elements_in_box": d["elements_in_box"], "osm_base": d["osm_base"], "weak_share": round(d["metres"]["weak"] / total, 3),
            "nearest_site_median_m": d["distance_to_nearest_site_m"]["median"], "chunks": e["chunks"], "now_j": e["now_j"], "as_needed_j": e["as_needed_j"], "bartendr_j": e["bartendr_j"],
            "bartendr_bursts": e["bartendr_bursts"], "saving_vs_as_needed_pct": e["saving_vs_as_needed_pct"], "when": d["when"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read(results: Path = RESULTS, masts: Path | None = None) -> dict:
    f = results / "summary.json"
    if not f.exists():
        return {"available": False, "reason": "no data: the weak-signal experiment has not been run on this machine", "rows": []}
    out = json.loads(f.read_text())
    if isinstance(out.get("energy"), dict):
        out["energy"]["masts"] = masts_row(masts)                     # R3: computed from the Q3 file at request time; the saved summary (and its sha256) is unchanged
    return out


if __name__ == "__main__":
    got = build()
    print(json.dumps({k: got.get(k) for k in ("available", "reason", "plain", "pack_bytes_median", "sha256")}, indent=1))
