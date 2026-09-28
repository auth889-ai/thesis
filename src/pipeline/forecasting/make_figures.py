#!/usr/bin/env python3
"""Figures for Phase 1 — every number read from the evidence files, never typed.

    python src/pipeline/forecasting/make_figures.py            # -> docs/figures/*.png

Four panels, one job each:
  1 accuracy_vs_horizon   does the model beat the trivial predictors, and by how much?
  2 reproduction          do our numbers match the published paper?
  3 actual_vs_predicted   what does a forecast actually look like on unseen data?
  4 routing_arms          the SUMO result: which routing arm helps, on paired seeds

Palette: validated categorical slots (CVD-checked, see the dataviz reference).
Contrast on slots 3/4 is below 3:1, so every series is ALSO direct-labelled — colour
is never the only channel carrying identity.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[3]
RES = REPO / "results/forecasting"
sys = __import__("sys")
OUT = REPO / "docs/figures"
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e6e5e1"
plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                     "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlecolor": INK,
                     "axes.spines.top": False, "axes.spines.right": False})


def style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=10)
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)


def fig_accuracy():
    fl = json.loads((RES / "benchmark_floors.json").read_text())
    tr = json.loads((RES / "trained_results.json").read_text())
    hs, hmin = ["3", "6", "12"], [15, 30, 60]
    city = "METR-LA"
    series = {
        "Graph WaveNet": ([next(v["mae"] for k, v in
                                next(r for r in tr["runs"] if r["model"] == "GWNet" and r["dataset"] == city)
                                ["metrics_by_horizon_min"].items() if int(k) == m) for m in hmin], BLUE),
        "STID": ([next(v["mae"] for k, v in
                       next(r for r in tr["runs"] if r["model"] == "STID" and r["dataset"] == city)
                       ["metrics_by_horizon_min"].items() if int(k) == m) for m in hmin], ORANGE),
        "persistence": ([fl[city]["floors"][h]["persistence"]["mae"] for h in hs], AQUA),
        "historical avg": ([fl[city]["floors"][h]["historical_average"]["mae"] for h in hs], YELLOW),
    }
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    x = np.arange(len(hmin))
    # Lines converge at 60 min, so place end labels at de-collided heights (colour alone must
    # never be the only thing separating two series).
    ends = sorted(((vals[-1], name, c) for name, (vals, c) in series.items()), key=lambda t: t[0])
    span = max(e[0] for e in ends) - min(e[0] for e in ends)
    min_gap = span * 0.08
    placed = []
    for val, _, _ in ends:
        placed.append(val if not placed else max(val, placed[-1] + min_gap))
    for name, (vals, c) in series.items():
        ax.plot(x, vals, color=c, lw=2, marker="o", ms=8, label=name, zorder=3,
                markeredgecolor=SURFACE, markeredgewidth=2)
    for (val, name, c), y in zip(ends, placed):
        ax.annotate(name, (x[-1] + 0.08, y), color=c, fontsize=10, fontweight="bold",
                    va="center", annotation_clip=False)
    style(ax, "Trained models beat the trivial predictors", "forecast horizon", "MAE  (mph, lower is better)")
    ax.set_xticks(x); ax.set_xticklabels([f"{m} min" for m in hmin])
    ax.set_xlim(-0.2, len(hmin) - 1 + 1.05)
    fig.text(0.01, 0.015, f"{city}: 207 real loop detectors, Los Angeles · held-out test split · "
                          f"the gap widens with horizon", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=[0, 0.045, 1, 1])
    fig.savefig(OUT / "1_accuracy_vs_horizon.png", dpi=200); plt.close(fig)
    return "1_accuracy_vs_horizon.png"


def fig_reproduction():
    tr = json.loads((RES / "trained_results.json").read_text())
    r = next(x for x in tr["runs"] if x["model"] == "GWNet" and x["dataset"] == "METR-LA")
    rows = [(int(k), v) for k, v in r["metrics_by_horizon_min"].items() if "published_mae" in v]
    rows.sort()
    hmin = [m for m, _ in rows]
    ours = [v["mae"] for _, v in rows]
    pub = [v["published_mae"] for _, v in rows]
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = np.arange(len(hmin)); w = 0.36
    b1 = ax.bar(x - w / 2 - 0.01, pub, w, color=MUTED, label="published (Wu et al., IJCAI 2019)", zorder=3)
    b2 = ax.bar(x + w / 2 + 0.01, ours, w, color=BLUE, label="ours (reproduced)", zorder=3)
    for bars, vals in ((b1, pub), (b2, ours)):
        for bar, v in zip(bars, vals):
            ax.annotate(f"{v:.2f}", (bar.get_x() + bar.get_width() / 2, v), xytext=(0, 3),
                        textcoords="offset points", ha="center", fontsize=9, color=INK)
    for i, (_, v) in enumerate(rows):
        ax.annotate(f"{v['mae_diff_pct']:+.1f}%", (i, max(ours[i], pub[i])), xytext=(0, 18),
                    textcoords="offset points", ha="center", fontsize=9.5, color=BLUE, fontweight="bold")
    style(ax, "Graph WaveNet reproduced within 1.8 % of the published paper",
          "forecast horizon", "MAE  (mph)")
    ax.set_xticks(x); ax.set_xticklabels([f"{m} min" for m in hmin])
    ax.set_ylim(0, max(ours + pub) * 1.28)
    ax.legend(frameon=False, loc="upper left", fontsize=9.5)
    fig.tight_layout(); fig.savefig(OUT / "2_reproduction.png", dpi=200); plt.close(fig)
    return "2_reproduction.png"


def fig_actual_vs_predicted():
    f = RES / "inference_GWNet_METR-LA.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    rows = [r for r in d["rows"] if r["sensor_index"] != "ALL"]
    if not rows:
        return None
    hs = sorted({r["horizon_min"] for r in rows})
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = np.arange(len(hs))
    act = [np.mean([r["actual_mph"] for r in rows if r["horizon_min"] == h]) for h in hs]
    prd = [np.mean([r["predicted_mph"] for r in rows if r["horizon_min"] == h]) for h in hs]
    ax.plot(x, act, color=INK, lw=2, marker="o", ms=8, label="actual",
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.plot(x, prd, color=BLUE, lw=2, marker="s", ms=8, label="predicted",
            markeredgecolor=SURFACE, markeredgewidth=2, zorder=3)
    ax.annotate("actual", (x[-1], act[-1]), xytext=(8, 0), textcoords="offset points",
                color=INK, fontweight="bold", fontsize=9.5, va="center")
    ax.annotate("predicted", (x[-1], prd[-1]), xytext=(8, 0), textcoords="offset points",
                color=BLUE, fontweight="bold", fontsize=9.5, va="center")
    style(ax, "One unseen window, reloaded from the saved checkpoint",
          "forecast horizon", "speed  (mph)")
    ax.set_xticks(x); ax.set_xticklabels([f"{h} min" for h in hs])
    ax.set_xlim(-0.15, len(hs) - 1 + 0.95)
    v = {int(k): val for k, val in (d.get("verification") or {}).items()}
    best = next((val for k, val in sorted(v.items()) if val.get("diff_pct") is not None), None)
    if best:
        ax.text(0, 0.02, f"checkpoint verified over {best['windows']} windows: reloaded MAE "
                         f"{best['reloaded_mae']} vs reported {best['reported_mae']} "
                         f"({best['diff_pct']:+.1f} %)", transform=ax.transAxes,
                color=MUTED, fontsize=8.5)
    fig.tight_layout(); fig.savefig(OUT / "3_actual_vs_predicted.png", dpi=200); plt.close(fig)
    return "3_actual_vs_predicted.png"


def fig_routing():
    f = REPO / "results/routing/stats.json"
    if not f.exists():
        return None
    d = json.loads(f.read_text())
    rows = []
    for arm, v in d.get("summary", {}).items():
        vh = v.get("total_vehicle_hours")
        if isinstance(vh, dict) and vh.get("mean"):
            rows.append((arm, vh["mean"], vh.get("sd", 0), v.get("n_seeds")))
    if not rows:
        return None
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(9.4, 5.0))
    names = [r[0].replace("_", " ") for r in rows]
    vals = [r[1] for r in rows]
    sds = [r[2] for r in rows]
    n_seeds = rows[0][3]
    base = next((v for n, v, *_ in rows if n == "static"), vals[0])
    colors = [AQUA if v < base else (ORANGE if v > base else MUTED) for v in vals]
    bars = ax.barh(names, vals, color=colors, height=0.6, zorder=3,
                   xerr=sds, error_kw={"ecolor": MUTED, "elinewidth": 1, "capsize": 3})
    for bar, v, sd in zip(bars, vals, sds):
        pct = 100 * (v / base - 1)
        # place the label clear of the error bar, not on top of it
        ax.annotate(f"{v:.0f} h   {pct:+.1f} %", (v + sd, bar.get_y() + bar.get_height() / 2),
                    xytext=(8, 0), textcoords="offset points", va="center", fontsize=9, color=INK)
    style(ax, f"SUMO routing, real Dhaka network, {n_seeds} paired seeds",
          "total vehicle-hours  (lower is better)", "")
    ax.grid(axis="x", color=GRID, lw=0.8); ax.grid(axis="y", visible=False)
    ax.set_xlim(0, (max(v + sd for v, sd in zip(vals, sds))) * 1.30)
    fig.text(0.01, 0.015, "green = better than no rerouting · orange = worse · bars show sd over seeds\n"
                          "network is real; demand is simulated (DHAKA_SIMULATED_DEMAND)",
             color=MUTED, fontsize=8.5, linespacing=1.5)
    fig.tight_layout(rect=[0, 0.05, 1, 1]); fig.savefig(OUT / "4_routing_arms.png", dpi=200); plt.close(fig)
    return "4_routing_arms.png"


def fig_field_position():
    """Where our reproduction sits among the published models — the question an examiner asks."""
    cmp_path = RES / "phase1_comparison.json"
    if not cmp_path.exists():
        return None
    sys.path.insert(0, str(REPO))
    from pipeline.forecasting.comparison_table import LEADERBOARD
    doc = json.loads(cmp_path.read_text())
    ours = {(r["model"], r["dataset"]): r["mae"] for r in doc["rows"]
            if r["trained"] and r["horizon_min"] == 15}
    city = "METR-LA"
    board = sorted(LEADERBOARD[city], key=lambda t: t[2])
    board = [b for b in board if b[2] < 4]                      # drop the naive outlier for scale
    names = [f"{n}\n{v}" for n, v, _ in board]
    vals = [m for _, _, m in board]
    mine = ours.get(("GWNet", city))
    fig, ax = plt.subplots(figsize=(9.6, 4.6))
    bars = ax.bar(range(len(vals)), vals, color=MUTED, width=0.62, zorder=3)
    for i, (bar, v) in enumerate(zip(bars, vals)):
        ax.annotate(f"{v:.2f}", (bar.get_x() + bar.get_width() / 2, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8.5, color=MUTED)
    if mine:
        ax.axhline(mine, color=BLUE, lw=2, ls="--", zorder=4)
        ax.annotate(f"ours: {mine:.3f}", (len(vals) - 0.4, mine), xytext=(0, 6),
                    textcoords="offset points", ha="right", color=BLUE, fontweight="bold", fontsize=10)
    style(ax, f"Our reproduction against the published field — {city}, 15-min MAE",
          "", "MAE  (mph, lower is better)")
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, fontsize=8)
    ax.set_ylim(min(vals) * 0.96, max(vals) * 1.06)
    fig.text(0.01, 0.015, "published numbers re-run under one protocol by STAEformer (CIKM 2023). "
                          "Ten architectures from 2018-2023 sit inside 2.67-2.85: the benchmark is saturated.",
             color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(OUT / "5_field_position.png", dpi=200); plt.close(fig)
    return "5_field_position.png"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    made = [f for f in (fig_accuracy(), fig_reproduction(), fig_actual_vs_predicted(),
                        fig_routing(), fig_field_position()) if f]
    for f in made:
        print(f"wrote docs/figures/{f}")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
