#!/usr/bin/env python3
"""The figures. Every plot reads one evidence JSON and draws it; nothing is computed here.

    python -m app.protocols.figures            # all four -> results/figures/

    F1  penetration curve      results/routing/sweep_compliance.json
    F2  forecast-quality ablation  results/routing/ablation_forecast_quality.json
    F3  forecast accuracy on Dhaka results/forecasting/live_backtest.json
    F4  predicted vs actual        results/forecasting/live_backtest.json (traces)
    F5  coverage ablation          results/routing/ablation_coverage.json

A figure whose evidence file is missing is skipped and named, never drawn from placeholder data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                       # noqa: E402

from app.paths import REPO
OUT = REPO / "results/figures"
C = {"baseline": "#94a3b8", "reactive": "#f59e0b", "prediction_aware": "#a855f7",
     "oracle": "#22c55e", "Chronos-Bolt": "#a855f7", "persistence": "#f59e0b", "random": "#64748b",
     "historical_average": "#94a3b8", "actual": "#3b82f6"}
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150})


def _load(rel: str):
    f = REPO / rel
    if not f.exists():
        print(f"[figures] SKIP — missing {rel}")
        return None
    return json.loads(f.read_text())


def f1_penetration(d: dict) -> Path:
    pts = sorted(d["points"], key=lambda p: p["compliance"])
    x = [p["compliance"] * 100 for p in pts]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.axhline(0, color="#94a3b8", lw=1, ls="--", label="baseline (no rerouting)")
    for arm, label in (("reactive", "reactive: reroute on current travel times"),
                       ("prediction_aware", "prediction-aware: pre-departure on the forecast")):
        m = np.array([p["arms"][arm]["vs_baseline_pct_mean"] for p in pts])
        s = np.array([p["arms"][arm]["vs_baseline_pct_sd"] for p in pts])
        ax.plot(x, m, "o-", color=C[arm], label=label)
        ax.fill_between(x, m - s, m + s, color=C[arm], alpha=0.15)
        for xi, p in zip(x, pts):
            a = p["arms"][arm]
            if a["n_seeds"] and a["seeds_improved"] == a["n_seeds"] and xi > 0:
                ax.annotate(f"{a['seeds_improved']}/{a['n_seeds']} seeds", (xi, m[list(x).index(xi)]),
                            textcoords="offset points", xytext=(0, -14), ha="center", fontsize=8, color=C[arm])
    ax.set_xlabel("equipped vehicles (%)")
    ax.set_ylabel("total vehicle-hours vs baseline (%)")
    ax.set_title(f"Penetration curve — {len(str(d['seeds']).split(','))} seeds, "
                 f"{d['horizon_s']} s horizon, band = ±1 sd", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    fig.tight_layout()
    p = OUT / "F1_penetration_curve.png"
    fig.savefig(p); plt.close(fig)
    return p


def f2_ablation(d: dict) -> Path:
    rows = d["rows"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for i, r in enumerate(rows):
        per = r["vs_baseline"]["per_seed_pct"]
        ax.bar(i, r["vs_baseline"]["mean_pct"], color=C.get(r["forecast"], "#64748b"), alpha=0.85,
               label=None)
        ax.scatter([i + (j - len(per) / 2) * 0.06 for j in range(len(per))], per, color="k", s=14,
                   zorder=3)
        ax.text(i, max(per) + 0.4, r["vs_baseline"]["seeds_improved"], ha="center", fontsize=8)
    ax.axhline(0, color="#94a3b8", lw=1, ls="--")
    ax.set_xticks(range(len(rows)))
    ax.set_xticklabels([r["forecast"] for r in rows])
    ax.set_ylabel("vehicle-hours vs baseline (%)  •  dots = seeds")
    rs = d["route_sensitivity"]["vehicles_routed_differently"]
    ax.set_title("Which forecast the prediction arm routed on — same network, demand, seeds\n"
                 f"Chronos vs random: {rs.get('Chronos-Bolt vs random', '?')} vehicles routed differently",
                 fontsize=9)
    fig.tight_layout()
    p = OUT / "F2_forecast_quality_ablation.png"
    fig.savefig(p); plt.close(fig)
    return p


def f3_accuracy(d: dict) -> Path:
    hs = d["horizons_min"]
    models = []
    for r in d["rows"]:
        if r["model"] not in models:
            models.append(r["model"])
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4))
    for m in models:
        rows = {r["horizon_min"]: r for r in d["rows"] if r["model"] == m}
        style = "--" if rows[hs[0]]["is_baseline"] else "-"
        axes[0].plot(hs, [rows[h]["mae"] for h in hs], "o" + style, color=C.get(m, "#64748b"), label=m)
        axes[1].plot(hs, [rows[h]["class_accuracy"] * 100 for h in hs], "o" + style,
                     color=C.get(m, "#64748b"), label=m)
    axes[0].set_ylabel("MAE (congestion level 0–3)"); axes[1].set_ylabel("class accuracy (%)")
    for ax in axes:
        ax.set_xlabel("horizon (min)"); ax.set_xticks(hs)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Forecast accuracy on Dhaka's own recorded data — {d['nodes']} corridors × {d['bins']} bins, "
                 f"{d['origins_evaluated']} rolling origins", fontsize=9)
    fig.tight_layout()
    p = OUT / "F3_dhaka_forecast_accuracy.png"
    fig.savefig(p); plt.close(fig)
    return p


def f4_trace(d: dict) -> Path:
    h = d["horizons_min"][0]
    tr = d["traces"][str(h)] if str(h) in d["traces"] else d["traces"][h]
    t = np.arange(len(tr))
    fig, ax = plt.subplots(figsize=(7.6, 3.2))
    ax.plot(t, [r["actual"] for r in tr], color=C["actual"], lw=1.8, label="actual (recorded later)")
    for m in [k for k in tr[0] if k not in ("target_utc", "actual")]:
        ax.plot(t, [r[m] for r in tr], lw=1, ls="--" if m == "persistence" else "-",
                color=C.get(m, "#64748b"), label=f"{m} (+{h} min)")
    ticks = list(range(0, len(tr), max(1, len(tr) // 8)))
    ax.set_xticks(ticks); ax.set_xticklabels([tr[i]["target_utc"][5:16].replace("T", " ") for i in ticks],
                                             rotation=0, fontsize=7)
    ax.set_ylim(0, 3); ax.set_ylabel("mean congestion level"); ax.legend(fontsize=8, ncol=2)
    ax.set_title("Predicted vs actual, +15 min, mean over corridors (UTC)", fontsize=9)
    fig.tight_layout()
    p = OUT / "F4_predicted_vs_actual.png"
    fig.savefig(p); plt.close(fig)
    return p


def f5_coverage(d: dict) -> Path:
    """Does growing the priced coverage let forecast quality through? Two panels: how many
    vehicles the router routes differently for the model than for noise, and the outcome gap."""
    hops = d["coverage_hops"]
    diff = [d["route_sensitivity_by_hops"][str(h)]["vehicles_routed_differently"].get("Chronos-Bolt vs random", 0)
            if str(h) in d["route_sensitivity_by_hops"] else
            d["route_sensitivity_by_hops"][h]["vehicles_routed_differently"].get("Chronos-Bolt vs random", 0)
            for h in hops]
    by = {(r["coverage_hops"], r["forecast"]): r for r in d["rows"]}
    priced = [by[(h, "Chronos-Bolt")]["priced_edges"] for h in hops]
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.4))
    axes[0].bar(range(len(hops)), diff, color="#a855f7")
    axes[0].set_xticks(range(len(hops)))
    axes[0].set_xticklabels([f"{h} hops\n{p} edges" for h, p in zip(hops, priced)], fontsize=8)
    axes[0].set_ylabel("vehicles routed differently\n(model vs random noise)")
    axes[0].set_title("Does the forecast reach the router?", fontsize=9)
    for lab, col in (("Chronos-Bolt", "#a855f7"), ("random", "#64748b")):
        m = [by[(h, lab)]["vs_baseline"]["mean_pct"] for h in hops]
        per = [by[(h, lab)]["vs_baseline"]["per_seed_pct"] for h in hops]
        axes[1].plot(hops, m, "o-", color=col, label=lab)
        for h, ps in zip(hops, per):
            axes[1].scatter([h] * len(ps), ps, color=col, s=10, alpha=0.5)
    axes[1].axhline(0, color="#94a3b8", lw=1, ls="--")
    axes[1].set_xlabel("pricing coverage (hops from the observed corridors)")
    axes[1].set_ylabel("vehicle-hours vs baseline (%)")
    axes[1].set_title("Outcome, model vs noise (dots = seeds)", fontsize=9)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    p = OUT / "F5_coverage_ablation.png"
    fig.savefig(p); plt.close(fig)
    return p


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    made = {}
    sweep = _load("results/routing/sweep_compliance.json")
    abl = _load("results/routing/ablation_forecast_quality.json")
    bt = _load("results/forecasting/live_backtest.json")
    if sweep: made["F1"] = f1_penetration(sweep)
    if abl: made["F2"] = f2_ablation(abl)
    if bt:
        made["F3"] = f3_accuracy(bt)
        made["F4"] = f4_trace(bt)
    cov = _load("results/routing/ablation_coverage.json")
    if cov and len(cov.get("coverage_hops", [])) > 1:
        made["F5"] = f5_coverage(cov)
    for k, p in made.items():
        print(f"[figures] {k} -> {p.relative_to(REPO)}")
    (OUT / "FIGURES.json").write_text(json.dumps({k: str(p.relative_to(REPO)) for k, p in made.items()}, indent=1))
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
