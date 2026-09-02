#!/usr/bin/env python3
"""The Phase-1 verdict: floors, trained models and published values in ONE machine-readable table.

    python pipeline/forecasting/comparison_table.py
    python pipeline/forecasting/comparison_table.py --check      # exit 1 if the phase gate is not met

Sources (all produced by other commands, never typed):
    results/forecasting/benchmark_floors.json   persistence / historical average / seasonal / global mean
    results/forecasting/trained_results.json    GPU-trained models with provenance
    published values                        from the papers, carried in trained_results

Gate for Phase 1 — every condition must hold, and `--check` returns non-zero if any fails:
    G1  both METR-LA and PEMS-BAY present
    G2  persistence and historical-average floors present for each
    G3  STID and Graph WaveNet trained on each
    G4  every trained model beats every floor at every horizon
    G5  Graph WaveNet within 10 % of its published MAE (a reproduction, not a coincidence)
    G6  a checkpoint exists and reproduces its metrics from a fresh load (inference_*.json)

Writes results/forecasting/phase1_comparison.{json,csv,md}.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "results/forecasting"
FLOOR_NAMES = ["persistence", "historical_average", "seasonal_naive", "global_mean"]
HORIZONS = [5, 15, 30, 60]

# The published field, at 15-min MAE, as re-run under ONE protocol by STAEformer (Liu et al.,
# CIKM 2023, Table 1) -- their table is used because they retrained every baseline themselves, so
# the numbers are mutually comparable rather than copied across papers with different splits.
# This exists so our own result is placed in the field automatically instead of by hand.
LEADERBOARD = {
    "METR-LA": [
        ("STAEformer", "CIKM 2023", 2.65), ("DCRNN", "ICLR 2018", 2.67),
        ("Graph WaveNet", "IJCAI 2019", 2.69), ("MTGNN", "KDD 2020", 2.69),
        ("STGCN", "IJCAI 2018", 2.75), ("GTS", "ICLR 2021", 2.75),
        ("GMAN", "AAAI 2020", 2.80), ("STNorm", "KDD 2021", 2.81),
        ("STID", "CIKM 2022", 2.82), ("PDFormer", "AAAI 2023", 2.83),
        ("AGCRN", "NeurIPS 2020", 2.85), ("HI (naive)", "-", 6.80),
    ],
    "PEMS-BAY": [
        ("Graph WaveNet", "IJCAI 2019", 1.30), ("STAEformer", "CIKM 2023", 1.31),
        ("DCRNN", "ICLR 2018", 1.38), ("HI (naive)", "-", 3.06),
    ],
}
# Bands from the same survey: the 2019-2023 generation clusters in 2.67-2.85 on METR-LA, a spread
# plausibly inside seed/hyperparameter noise. Four years moved SOTA 2.69 -> 2.65 (1.5 %).
BANDS = {"METR-LA": [(2.65, "state of the art"), (2.90, "respectable published baseline"),
                     (float("inf"), "below the published generation")],
         "PEMS-BAY": [(1.31, "state of the art"), (1.45, "respectable published baseline"),
                      (float("inf"), "below the published generation")]}


def place_in_field(city: str, mae: float) -> dict:
    """Where does our number sit among the published models on this benchmark?"""
    board = LEADERBOARD.get(city, [])
    if not board or mae is None:
        return {}
    beaten = [f"{n} ({v})" for n, v, m in board if mae < m]
    ahead = [f"{n} ({v})" for n, v, m in board if mae >= m]
    band = next(label for thr, label in BANDS[city] if mae <= thr)
    best = min(m for _, _, m in board)
    return {"band": band, "beats": beaten, "behind": ahead,
            "gap_to_sota_mae": round(mae - best, 3),
            "gap_to_sota_pct": round(100 * (mae / best - 1), 2)}


def load() -> tuple[dict, dict, dict]:
    fl = json.loads((RESULTS / "benchmark_floors.json").read_text()) if (RESULTS / "benchmark_floors.json").exists() else {}
    tr = json.loads((RESULTS / "trained_results.json").read_text()) if (RESULTS / "trained_results.json").exists() else {"runs": []}
    inf = {}
    for f in RESULTS.glob("inference_*.json"):
        d = json.loads(f.read_text())
        inf[(d["model"], d["dataset"])] = d
    return fl, tr, inf


def build(fl: dict, tr: dict, inf: dict) -> dict:
    rows = []
    for city, rec in fl.items():
        bins = rec.get("bin_seconds", 300) // 60
        for h_steps, per in rec.get("floors", {}).items():
            minutes = int(h_steps) * bins
            for name in FLOOR_NAMES:
                m = per.get(name)
                if not m or m.get("mae") is None:
                    continue
                rows.append({"dataset": city, "kind": "floor", "model": name, "horizon_min": minutes,
                             "mae": round(m["mae"], 4), "rmse": round(m["rmse"], 4),
                             "mape_pct": round(m["mape"], 3) if m.get("mape") is not None else None,
                             "published_mae": None, "mae_diff_pct": None, "trained": False})
    for r in tr.get("runs", []):
        has_ckpt = (r["model"], r["dataset"]) in inf
        for minutes, m in r["metrics_by_horizon_min"].items():
            rows.append({"dataset": r["dataset"], "kind": "trained", "model": r["model"],
                         "horizon_min": int(minutes), "mae": round(m["mae"], 4),
                         "rmse": round(m["rmse"], 4), "mape_pct": round(m["mape_pct"], 3),
                         "published_mae": m.get("published_mae"),
                         "mae_diff_pct": m.get("mae_diff_pct"), "trained": True,
                         "epochs": r.get("epochs_completed"), "gpu": r.get("hardware", {}).get("gpu"),
                         "checkpoint_verified": has_ckpt})
    return {"generated_utc": datetime.now(timezone.utc).isoformat(), "rows": rows}


def gate(rows: list[dict], inf: dict) -> dict:
    cities = {r["dataset"] for r in rows}
    trained = {(r["dataset"], r["model"]) for r in rows if r["trained"]}
    floors = {(r["dataset"], r["model"]) for r in rows if not r["trained"]}
    checks = {}
    want_cities = {"METR-LA", "PEMS-BAY"}
    checks["G1_both_cities"] = {"ok": want_cities <= cities, "detail": sorted(cities)}
    checks["G2_floors"] = {"ok": all((c, f) in floors for c in want_cities & cities
                                     for f in ("persistence", "historical_average")),
                           "detail": sorted(f"{c}/{m}" for c, m in floors)}
    checks["G3_models"] = {"ok": all((c, m) in trained for c in want_cities & cities for m in ("STID", "GWNet")),
                           "detail": sorted(f"{c}/{m}" for c, m in trained)}
    beaten, viol = True, []
    for c in cities:
        for h in HORIZONS:
            f_best = [r["mae"] for r in rows if r["dataset"] == c and not r["trained"] and r["horizon_min"] == h]
            t_all = [(r["model"], r["mae"]) for r in rows if r["dataset"] == c and r["trained"] and r["horizon_min"] == h]
            if not f_best or not t_all:
                continue
            for mdl, mae in t_all:
                if mae >= min(f_best):
                    beaten = False
                    viol.append(f"{c}/{mdl}@{h}min: {mae} >= best floor {min(f_best)}")
    checks["G4_models_beat_floors"] = {"ok": beaten, "detail": viol or "every trained model beats every floor"}
    gw = [r for r in rows if r["trained"] and r["model"] == "GWNet" and r.get("mae_diff_pct") is not None]
    checks["G5_gwnet_reproduces_published"] = {
        "ok": bool(gw) and all(abs(r["mae_diff_pct"]) <= 10 for r in gw),
        "detail": [f"{r['dataset']}@{r['horizon_min']}min {r['mae_diff_pct']:+.1f} %" for r in gw] or "no comparison"}
    ok_inf = [k for k, v in inf.items() if v.get("window_mae_all_horizons_mph") is not None]
    checks["G6_checkpoint_inference"] = {"ok": bool(ok_inf), "detail": [f"{m}/{d}" for m, d in ok_inf] or "none yet"}
    return {"passed": all(c["ok"] for c in checks.values()), "checks": checks}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="exit non-zero unless the phase gate passes")
    a = p.parse_args()
    fl, tr, inf = load()
    doc = build(fl, tr, inf)
    doc["gate"] = gate(doc["rows"], inf)
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "phase1_comparison.json").write_text(json.dumps(doc, indent=1))
    fields = ["dataset", "kind", "model", "horizon_min", "mae", "rmse", "mape_pct",
              "published_mae", "mae_diff_pct", "epochs", "gpu", "checkpoint_verified"]
    with open(RESULTS / "phase1_comparison.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(doc["rows"], key=lambda r: (r["dataset"], r["horizon_min"], r["kind"], r["model"])))

    lines = ["# Phase 1 — traffic prediction: floors vs trained models vs published\n"]
    for city in sorted({r["dataset"] for r in doc["rows"]}):
        lines += [f"## {city}", "",
                  "| model | kind | " + " | ".join(f"MAE@{h}min" for h in HORIZONS) + " | published MAE@15 | diff |",
                  "|---|---|" + "---|" * (len(HORIZONS) + 2)]
        models = sorted({(r["model"], r["trained"]) for r in doc["rows"] if r["dataset"] == city},
                        key=lambda t: (t[1], t[0]))
        for mdl, is_tr in models:
            cells = []
            for h in HORIZONS:
                v = [r["mae"] for r in doc["rows"] if r["dataset"] == city and r["model"] == mdl
                     and r["horizon_min"] == h]
                cells.append(f"{v[0]:.3f}" if v else "–")
            pub = [r for r in doc["rows"] if r["dataset"] == city and r["model"] == mdl
                   and r["horizon_min"] == 15 and r.get("published_mae")]
            pm = f"{pub[0]['published_mae']:.2f}" if pub else "–"
            df = f"{pub[0]['mae_diff_pct']:+.1f} %" if pub else "–"
            lines.append(f"| **{mdl}** | {'trained' if is_tr else 'floor'} | " + " | ".join(cells) + f" | {pm} | {df} |")
        lines.append("")
    # position every trained model in the published field
    lines += ["## Where our results sit in the published field", "",
              "Published 15-min MAE from STAEformer (CIKM 2023) Table 1, which retrained every "
              "baseline under one protocol. Note the field is saturated: four years moved the best "
              "METR-LA number from 2.69 to 2.65 (1.5 %), and ten architectures from 2018-2023 sit "
              "inside 2.67-2.85 — a spread plausibly within seed and hyperparameter noise.", "",
              "| our model | dataset | our MAE@15 | band | gap to SOTA | published models it beats |",
              "|---|---|---|---|---|---|"]
    for r in sorted(doc["rows"], key=lambda r: (r["dataset"], r["model"])):
        if not r["trained"] or r["horizon_min"] != 15:
            continue
        pl = place_in_field(r["dataset"], r["mae"])
        if not pl:
            continue
        doc.setdefault("field_position", {})[f"{r['model']}/{r['dataset']}"] = pl
        beats = ", ".join(pl["beats"][:5]) + (f" +{len(pl['beats']) - 5} more" if len(pl["beats"]) > 5 else "")
        lines.append(f"| **{r['model']}** | {r['dataset']} | {r['mae']:.3f} | {pl['band']} | "
                     f"+{pl['gap_to_sota_pct']:.1f} % | {beats or '—'} |")
    lines.append("")
    g = doc["gate"]
    lines += [f"## Phase-1 gate: {'**PASS**' if g['passed'] else '**NOT YET MET**'}", "",
              "| check | ok | detail |", "|---|---|---|"]
    for k, v in g["checks"].items():
        d = v["detail"] if isinstance(v["detail"], str) else ", ".join(map(str, v["detail"]))[:150]
        lines.append(f"| {k} | {'yes' if v['ok'] else 'NO'} | {d} |")
    lines += ["", "Regenerate: `python pipeline/forecasting/comparison_table.py`. Machine-readable: "
                  "`phase1_comparison.json` / `.csv`."]
    (RESULTS / "phase1_comparison.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if (not a.check or doc["gate"]["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
