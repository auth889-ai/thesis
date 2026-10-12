"""make demo-forecast: one figure from the saved RQ1 results; nothing is trained or run.

    python scripts/demo/forecast.py [--no-show]

Left: forecast error as a share of "no change" (persistence = 1.0; below 1 = better than assuming speeds stay as they are),
Los Angeles (METR-LA) and Dhaka (DhaTraX), 15/30/60 minutes ahead. Right: how often speed jumps (stop-and-go share).
Every number is read from results/forecasting/rq1/summary.json.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SUMMARY = REPO / "results/forecasting/rq1/summary.json"
OUT = REPO / "evidence/demo/forecast.png"
H = ("15", "30", "60")
NO_SKILL_DHAKA = {"persistence", "random_forest_from_metr_la", "xgboost_from_metr_la"}   # zero-shot models only


def series(s: dict) -> dict:
    """The plotted ratios and shares, from the summary only. Pure."""
    la, dh = s["lab"]["METR-LA"], s["dhaka"]
    best_dh = {h: min((m for m in dh if isinstance(dh[m], dict) and h in dh[m] and m not in NO_SKILL_DHAKA), key=lambda m: dh[m][h]["mae"]) for h in H}
    return {
        "Los Angeles, best trained (D2STGNN)": [la["D2STGNN"][h]["mae"] / la["persistence"][h]["mae"] for h in H],
        "Los Angeles, usual speed at this hour and weekday": [la["historical_average_weekday"][h]["mae"] / la["persistence"][h]["mae"] for h in H],
        "Dhaka, best zero-shot (" + ", ".join(sorted({s['names'].get(best_dh[h], best_dh[h]).split(' (')[0] for h in H})) + ")":
            [dh[best_dh[h]][h]["mae"] / dh["persistence"][h]["mae"] for h in H],
        "_stop_and_go": {"Dhaka BM": s["character"]["DhaTraX"]["sites"]["BM"]["stop_and_go_share"],
                         "Dhaka INT": s["character"]["DhaTraX"]["sites"]["INT"]["stop_and_go_share"],
                         "Dhaka BS": s["character"]["DhaTraX"]["sites"]["BS"]["stop_and_go_share"],
                         "Los Angeles (median sensor-day)": s["character"]["METR-LA"]["stop_and_go_share"]["median"],
                         "SF Bay Area": s["character"]["PEMS-BAY"]["stop_and_go_share"]["median"]},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-show", action="store_true")
    a = ap.parse_args()
    print("DEMO: how well can traffic speed be forecast 15, 30 and 60 minutes ahead in Los Angeles and in Dhaka, and why Dhaka is harder.",
          "SOFTWARE: saved results of BasicTS (D2STGNN), Chronos-Bolt and Chronos-2 (Amazon), TimesFM 2.5 (Google); plotted with matplotlib.",
          "PAPERS: METR-LA from DCRNN (Li et al., ICLR 2018); D2STGNN (Shao et al., VLDB 2022); Chronos (Ansari et al., TMLR 2024);",
          "  Dhaka data DhaTraX v1.0 (Roy, Zenodo, CC BY 4.0: three camera sites, one recorded day each).", "", sep="\n")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = series(json.loads(SUMMARY.read_text()))
    sg = d.pop("_stop_and_go")
    fig, (l, r) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [1.25, 1]})
    for (name, ys), c, mk in zip(d.items(), ("#1f5fa8", "#7fa6d6", "#d2552b"), ("o", "s", "D")):
        l.plot([15, 30, 60], ys, marker=mk, color=c, lw=2, label=name)
        for x, y in zip([15, 30, 60], ys):
            l.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=8, color=c)
    l.axhline(1.0, color="black", lw=1, ls="--")
    l.text(61, 1.0, '"no change"', va="center", fontsize=9)
    l.set(xticks=[15, 30, 60], xlabel="minutes ahead", ylabel="error ÷ error of \"no change\"  (below 1 = better)",
          title="Forecast error against \"no change\"")
    l.legend(fontsize=8, loc="lower left")
    names, vals = list(sg), [100 * v for v in sg.values()]
    bars = r.barh(names[::-1], vals[::-1], color=["#7fa6d6", "#1f5fa8", "#d2552b", "#d2552b", "#d2552b"])
    for b, v in zip(bars, vals[::-1]):
        r.text(b.get_width() + 0.2, b.get_y() + b.get_height() / 2, f"{v:.1f} %", va="center", fontsize=9)
    r.set(xlabel="% of 5-min steps with a speed jump > 30 % of free-flow", title="Why Dhaka is harder: stop-and-go")
    fig.suptitle("RQ1 · Los Angeles (METR-LA, 207 sensors, 4 months) and Dhaka (DhaTraX, 3 sites, 1 day each) · saved results", fontsize=10)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=130)
    la, dh = list(d.values())[0], list(d.values())[2]
    print(f"Los Angeles: the best trained model's error is {la[0]:.2f} / {la[1]:.2f} / {la[2]:.2f} of 'no change' at 15 / 30 / 60 min.")
    better = [m for m, y in zip(H, dh) if y < 1]
    print(f"Dhaka: the best zero-shot model's error is {dh[0]:.2f} / {dh[1]:.2f} / {dh[2]:.2f} of 'no change': better than 'no change' at "
          + (" and ".join(better) + " min only." if better else "no horizon."))
    print(f"Dhaka's speed jumps in {min(vals[:3]):.1f}-{max(vals[:3]):.1f} % of 5-minute steps, against {vals[3]:.1f} % in Los Angeles.")
    print(f"Figure: {OUT.relative_to(REPO)}")
    if not a.no_show and sys.platform == "darwin":
        subprocess.run(["open", str(OUT)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
