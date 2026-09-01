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
    ("Prediction — twin floors (persistence / historical average)", "predict/results/twin_floors.md", "make data && python predict/baselines_twin.py"),
    ("Prediction — BasicTS benchmark (METR-LA / PEMS-BAY / PEMS08)", "predict/results/benchmark.md", "notebooks/Predict_BasicTS_Colab.ipynb (Colab Pro) -> predict/results/benchmark.csv"),
    ("Routing — arms × paired seeds on Dhaka R1", "route/results/stats.md", "make route"),
    ("Routing — network-wide decision guard", "route/results/decision_guard.md", "python route/decision_guard.py --horizon 7200 --reference reactive"),
    ("Live reference — Google Routes derived congestion states", "artifacts/p_live/live_reference_summary.md", "python scripts/run_live_capture.py && python scripts/summarize_live_reference.py"),
    ("Networking — V2X penetration sweep (Eclipse MOSAIC)", "network/results/penetration.md", "make network"),
    ("Networking — latency / loss vs advisory delivery", "network/results/latency.md", "python network/latency_injection.py"),
    ("NLP — incident-text classifier", "nlp/results/classifier.md", "make nlp"),
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
