#!/usr/bin/env python3
"""Latency / loss injection: how many route advisories still arrive BEFORE the decision point?

Inputs
  * base network latency: the distribution SIMULATED by the official Eclipse MOSAIC Barnim
    example (results/artifacts/gates/mosaic_barnim/latencies.json) sampled through. These are simulated
    ITS-G5 communication events from MOSAIC's SNS ad-hoc model, NOT radio hardware measurements;
    every latency and loss figure downstream inherits that nature and must be described as such.
    src/pipeline/adapters/networking/v2x_bus.py::V2XBus (the same adapter the routing arm uses);
    `--base sweep` instead uses the per-message latency histogram of the Dhaka sweep JSONs.
  * per-vehicle time budget  tth  = time from the vehicle's FIRST DENM reception until it reaches
    the hazard zone (decision point). Source, in order of preference:
      (a) results/networking/penetration_p*_s*.json -> time_to_hazard.rows  (from the sweep:
          position/speed at first reception from the MOSAIC output ambassador, distance to the
          hazard rectangle; analytic straight-line model, labelled in the JSON);
      (b) if no sweep JSON exists: a CLEARLY LABELLED analytic fallback -- distance to the
          hazard drawn uniformly on [0, 3000 m] (the DENM geocast radius of WeatherWarningApp),
          speed = 11 m/s (SUMO summary meanSpeed of the smoke run).

Model (per vehicle i, Monte Carlo over `--draws` seeds)
  single-shot:  delivered_i = (u > loss) and (lat_i + L_added < tth_i)
  1 Hz repeat:  the official WeatherWarningApp re-broadcasts a DENM every second while the sender
                is inside the hazard, so a vehicle gets  n_i = 1 + floor(tth_i - lat_i - L_added)
                independent chances (n_i = 0 if the first one is already too late):
                P_i = 1 - loss ** n_i
  fraction = mean_i delivered_i   (rows: L_added in {0, 500, 2000, 5000} ms x loss in {0, 10, 30} %)

Outputs: results/networking/latency.csv, latency.md
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import statistics
from pathlib import Path

from core.common.paths import REPO
RESULTS = REPO / "results/networking"
V2X_BUS = REPO / "core/networking/v2x/v2x_bus.py"
ADDED_MS = [0, 500, 2000, 5000]
LOSS_PCT = [0, 10, 30]


def load_bus():
    spec = importlib.util.spec_from_file_location("v2x_bus", V2X_BUS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def base_latency_samples(base: str, sweep_jsons: list[Path]) -> tuple[list[float], str]:
    if base == "barnim":
        bus = load_bus().V2XBus(seed=0)
        return list(bus.samples_ms), f"V2XBus <- {bus.source}"
    samples = []
    for f in sweep_jsons:
        h = json.loads(f.read_text())["v2x"]["latency"].get("hist_10us_bins")
        if isinstance(h, dict):
            for b, n in h.items():
                samples.extend([(int(b) + 0.5) * 0.01] * min(n, 2000))  # 10 us bins -> ms, cap per bin
    if not samples:
        raise SystemExit("no latency histogram in sweep JSONs; use --base barnim")
    return samples, f"Dhaka sweep V2X_MESSAGE_RECEPTION - TRANSMISSION per MessageId ({len(sweep_jsons)} JSONs)"


def tth_samples(sweep_jsons: list[Path], seed: int) -> tuple[list[float], str]:
    rows = []
    for f in sweep_jsons:
        d = json.loads(f.read_text())
        if d["point"]["p"] > 0:
            rows.extend(r["tth_s"] for r in d["time_to_hazard"]["rows"])
    if rows:
        return rows, (f"sweep JSONs ({len(sweep_jsons)} points, {len(rows)} rerouting vehicles): "
                      "distance from position at first DENM reception to hazard rectangle / speed")
    rng = random.Random(seed)
    rows = [rng.uniform(0, 3000) / 11.0 for _ in range(2000)]
    return rows, "ANALYTIC FALLBACK (no sweep JSON): distance ~ U[0, 3000 m] (DENM geocast radius) / 11 m/s"


def simulate(tth: list[float], lat_ms: list[float], added_ms: float, loss: float, draws: int, seed: int):
    rng = random.Random(seed)
    single, repeat, eff = [], [], []
    for _ in range(draws):
        for t in tth:
            lat = rng.choice(lat_ms) + added_ms
            eff.append(lat)
            in_time = (lat / 1000.0) < t
            single.append(1.0 if (in_time and rng.random() >= loss) else 0.0)
            n = 1 + int(t - lat / 1000.0) if in_time else 0
            repeat.append(1.0 - loss ** n if n > 0 else 0.0)
    return statistics.fmean(single), statistics.fmean(repeat), statistics.fmean(eff)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", choices=["barnim", "sweep"], default="barnim")
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    sweep_jsons = sorted(RESULTS.glob("penetration_p*_s*.json"))
    lat_ms, lat_src = base_latency_samples(a.base, sweep_jsons)
    tth, tth_src = tth_samples(sweep_jsons, a.seed)
    tth_sorted = sorted(tth)

    upstream = [t for t in tth if t > 0]     # vehicles still upstream of the hazard at first reception
    rows = []
    for added in ADDED_MS:
        for lp in LOSS_PCT:
            s, r, eff = simulate(tth, lat_ms, added, lp / 100.0, a.draws, a.seed)
            su, ru, _ = simulate(upstream, lat_ms, added, lp / 100.0, a.draws, a.seed) if upstream else (0, 0, 0)
            rows.append({"added_latency_ms": added, "loss_pct": lp, "n_vehicles": len(tth),
                         "n_upstream": len(upstream),
                         "frac_delivered_single_shot": round(s, 4),
                         "frac_delivered_1hz_repeat": round(r, 4),
                         "frac_single_upstream_only": round(su, 4),
                         "frac_repeat_upstream_only": round(ru, 4),
                         "effective_latency_mean_ms": round(eff, 1)})
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / "latency.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    q = lambda p: tth_sorted[min(len(tth_sorted) - 1, int(p * (len(tth_sorted) - 1)))]
    md = ["# Latency / loss injection - fraction of route advisories delivered before the decision point", "",
          f"* base latency: {lat_src}  (n={len(lat_ms)}, mean {statistics.fmean(lat_ms):.1f} ms, "
          f"p95 {sorted(lat_ms)[int(0.95 * (len(lat_ms) - 1))]:.1f} ms)",
          f"* time budget tth: {tth_src}",
          f"  n={len(tth)}, p10 {q(.1):.1f} s, p50 {q(.5):.1f} s, p90 {q(.9):.1f} s; "
          f"{len(tth) - len(upstream)} vehicles ({(len(tth) - len(upstream)) / len(tth):.0%}) were already inside the hazard "
          "rectangle at first reception (tth = 0: no advisory can arrive in time; counted as not delivered in the "
          "all-vehicle columns, excluded in the upstream-only columns)",
          f"* Monte Carlo: {a.draws} draws per vehicle, seed {a.seed}; delivered = not lost AND (latency + added) < tth", "",
          "| added latency ms | loss % | delivered (single DENM) | delivered (1 Hz DENM repeat) | upstream-only single | upstream-only repeat | eff. latency mean ms |",
          "|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['added_latency_ms']} | {r['loss_pct']} | {r['frac_delivered_single_shot']:.3f} | "
                  f"{r['frac_delivered_1hz_repeat']:.3f} | {r['frac_single_upstream_only']:.3f} | "
                  f"{r['frac_repeat_upstream_only']:.3f} | {r['effective_latency_mean_ms']} |")
    md += ["", "single DENM: one advisory per vehicle, lost with probability `loss`. 1 Hz repeat: the official "
               "WeatherWarningApp re-sends a DENM every second while in the hazard, so a vehicle with slack "
               "tth - latency gets one extra chance per second (P = 1 - loss^n).",
           "", "Regenerate: `python -m core.networking.mosaic.latency_injection [--base sweep]`."]
    (RESULTS / "latency.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
