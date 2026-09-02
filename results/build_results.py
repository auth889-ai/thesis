#!/usr/bin/env python3
"""Collect every result table into results/RESULTS.md — one file, every number -> command -> evidence.

Reads only files produced by the pipelines (never invents numbers). Missing sections are
listed as NOT YET PRODUCED with the command that produces them.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SECTIONS = [  # (title, markdown produced by the pipeline, command that produces it)
    ("Evidence audit — reality labels and missing work", "results/evidence_audit.md", "python results/evidence_audit.py"),
    ("Real route advisor — live Dhaka advisory without fixed seeds", "live/results/route_advice.md", "python live/route_advisor.py --live --yes --corridor farmgate_to_shahbagh"),
    ("Real user pilot — 3-user trip timestamp evidence", "live/results/pilot_metrics.md", "python live/user_trip_logger.py start ... && python live/user_trip_logger.py complete ..."),
    ("Prediction — LIVE Dhaka congestion floors (real Google-derived stream)", "results/forecasting/live_floors.md", "python pipeline/forecasting/record_live.py --live --yes  (recorder) && python pipeline/forecasting/live_state.py --report"),
    ("Prediction — twin floors (persistence / historical average)", "results/forecasting/twin_floors.md", "make data && python pipeline/forecasting/baselines_twin.py"),
    ("Prediction — BasicTS benchmark (METR-LA / PEMS-BAY / PEMS08)", "results/forecasting/benchmark.md", "notebooks/Predict_BasicTS_Colab.ipynb (Colab Pro) -> results/forecasting/benchmark.csv"),
    ("Prediction — PHASE 1 verdict: floors vs trained vs published, with gate", "results/forecasting/phase1_comparison.md", "python pipeline/forecasting/comparison_table.py"),
    ("Prediction — forecasting floors on real cities + protocol validation vs published", "results/forecasting/benchmark_floors.md", "python pipeline/forecasting/benchmark_floors.py --cities METR-LA,PEMS-BAY"),
    ("Prediction — city dataset registry (any city, one interface)", "results/forecasting/cities.md", "python pipeline/forecasting/city_datasets.py --list"),
    ("Prediction × Networking — federated forecasting under the MEASURED V2X link", "results/forecasting/federated.md", "notebooks/Federated_V2X_Colab.ipynb (Colab GPU) -> rclone copy gdrive2tb:dhakaflow/predict/results results/forecasting --include federated*"),
    ("Routing — arms × paired seeds on Dhaka R1", "results/routing/stats.md", "make route"),
    ("Routing — network-wide decision guard", "results/routing/decision_guard.md", "python pipeline/routing/decision_guard.py --horizon 7200 --reference reactive"),
    ("Live reference — Google Routes derived congestion states", "artifacts/p_live/live_reference_summary.md", "python pipeline/forecasting/run_live_capture.py && python pipeline/forecasting/summarize_live_reference.py"),
    ("Routing — demand-scale sensitivity / gridlock check (why scale 0.25 is primary)", "results/routing/gridlock_check.md", "see file"),
    ("Routing — arms × 10 paired seeds at scale 0.20 (sensitivity appendix)", "results/routing/scale0.2/stats.md", "python pipeline/routing/run_arms.py --scale 0.2 --seeds 11,…,20 --results results/routing/scale0.2 && python pipeline/routing/stats.py --results results/routing/scale0.2"),
    ("Routing — NLP incident scenario at scale 0.20 incl. pre-departure arms", "results/routing/scale0.2/incident.md", "python pipeline/routing/incident_scenario.py --scale 0.2 --results results/routing/scale0.2"),
    ("Prediction — Dhaka twin models (official BasicTS-legacy baselines; Colab results replace the local file)", "results/forecasting/twin_models.md", "notebooks/Predict_Twin_Colab.ipynb (Colab GPU) -> rclone copy gdrive2tb:dhakaflow/predict/results/twin_models results/forecasting/twin_models"),
    ("Routing — forecast model in the loop (pre-departure route choice on the twin test window)", "results/routing/model_in_loop_STID.md", "python pipeline/routing/model_in_loop.py --model STID --horizons 15,60 --compliance 0.1,0.3"),
    ("Live chain — Dhaka live congestion to an ACT / NO_ACTION routing decision", "results/routing/live_chain.md", "python pipeline/routing/live_chain.py --seeds 11,12,13"),
    ("Live chain — advised-share sweep under a labelled congested what-if", "results/routing/live_chain_c0.05.md", "python pipeline/routing/live_chain.py --compliance 0.05 --tag _c0.05 --levels ..."),
    ("Routing — REAL MEASURED demand (Athens pNEUMA d8, 697 drone-observed vehicles)", "results/routing/real_demand.md", "python pipeline/routing/real_demand_arms.py --seeds 11,12,13 --compliance 0.05,0.1,0.3"),
    ("Routing — NLP incident scenario (text → reroute → measured delay)", "results/routing/incident.md", "python pipeline/routing/incident_scenario.py --seeds 11,12,13"),
    ("Routing — value of early incident detection (report-delay sweep)", "results/routing/incident_delay_sweep.md", "python pipeline/routing/incident_scenario.py --seeds 11 --report-delays 60,300,900"),
    ("Networking — V2X penetration sweep (Eclipse MOSAIC)", "results/networking/penetration.md", "make network"),
    ("Networking — V2X advisory from our NLP / predicted event (Eclipse MOSAIC)", "results/networking/event_sweep.md", "python pipeline/networking/event_sweep.py --source nlp_event --p 0.25"),
    ("Networking — latency / loss vs advisory delivery", "results/networking/latency.md", "python pipeline/networking/latency_injection.py"),
    ("NLP — incident-text classifier", "results/nlp/classifier.md", "make nlp"),
]


def git_sha() -> str:
    return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=REPO).stdout.strip()


def csv_to_md(path: Path) -> str:
    rows = [r.rstrip("\n").split(",") for r in path.read_text().splitlines() if r.strip()]
    if not rows:
        return "(empty)"
    head = "| " + " | ".join(rows[0]) + " |\n|" + "---|" * len(rows[0]) + "\n"
    return head + "".join("| " + " | ".join(r) + " |\n" for r in rows[1:])


def main() -> int:
    out = [f"# RESULTS — DhakaFlow rebuild\n\nGenerated {dt.datetime.now().isoformat(timespec='minutes')} @ `{git_sha()}` by `python results/build_results.py`.\n",
           "Every table below is read from a file written by the pipeline named next to it. Nothing here is typed by hand.\n"]
    for title, rel, cmd in SECTIONS:
        p = REPO / rel
        out.append(f"\n## {title}\n\n`{cmd}` → `{rel}`\n")
        if p.exists():
            out.append(p.read_text().strip() + "\n")
        elif p.with_suffix(".csv").exists():
            out.append(csv_to_md(p.with_suffix(".csv")))
        else:
            out.append("_NOT YET PRODUCED_\n")
    (REPO / "results/RESULTS.md").write_text("\n".join(out))
    print("wrote results/RESULTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
