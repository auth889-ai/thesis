#!/usr/bin/env python3
"""DhakaFlow — THE main entry point. One file, one command, the whole system in order.

    python main.py status                 # what exists, what is real, what is missing
    python main.py predict --city METR-LA # STAGE 1: traffic prediction
    python main.py route                  # STAGE 2: route optimisation when traffic occurs
    python main.py all --city METR-LA     # stage 1 then stage 2
    python main.py demo                   # the examiner-facing app

The system is a pipeline, and the order matters — you cannot optimise a route around congestion you
have not predicted:

    STAGE 1  PREDICT   sensors / live API -> forecast of near-future congestion
             src/pipeline/forecasting/city_datasets.py     one loader interface per city (METR-LA, PEMS-BAY, PEMS04/08, Dhaka)
             # portability of the pipeline, NOT a cross-city accuracy claim
             src/pipeline/forecasting/record_live.py       live Dhaka congestion recorder (real API, compliant)
             src/pipeline/forecasting/live_state.py        stream -> forecastable series + arithmetic floors
             src/pipeline/forecasting/federated_forecast.py  ML + NETWORKING: FedAvg across RSUs over a SIMULATED V2X link (MOSAIC ITS-G5)
             experiments/notebooks/*.ipynb            GPU training (Colab) — never trained on this machine

    STAGE 2  ROUTE     forecast -> future edge travel times -> routing -> proof it helped
             src/pipeline/forecasting/live_to_edges.py     forecast -> SUMO edge travel times on the real road network
             src/pipeline/routing/predictive_routing.py  the routing arms (static / reactive / predictive)
             src/pipeline/routing/run_arms.py            paired-seed experiment driver
             src/pipeline/routing/live_chain.py          the whole chain -> ACT / NO_ACTION decision
             src/pipeline/routing/decision_guard.py      refuses to claim an improvement the seeds do not support

    EVIDENCE results/build_results.py -> results/RESULTS.md   every number -> command -> file

Everything else in the repo is support: `dhakaflow/` is the reusable library, `research/` holds
imported algorithm adapters, `src/pipeline/networking/` the V2X experiments, `src/pipeline/nlp/` the incident-text pipeline,
`results/artifacts/` is RUN OUTPUT (not source), and `legacy/` is retired code kept only for history.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
PY = sys.executable


def run(cmd: list[str], why: str) -> int:
    print(f"\n\033[1m>>> {why}\033[0m\n    $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.call([PY] + [str(c) for c in cmd], cwd=REPO)


def status(_a) -> int:
    print("STAGE 1 — PREDICTION")
    sys.path.insert(0, str(REPO))
    from pipeline.forecasting.city_datasets import REGISTRY, available, load_city
    for city in REGISTRY:
        if available(city):
            try:
                cd = load_city(city)
                s = cd.summary()
                print(f"  {city:<12} {s['sensors']:>4} sensors  {s['timesteps']:>6} bins  "
                      f"{s['coverage']:>6.1%} covered  {s['reality']}")
            except SystemExit as ex:
                print(f"  {city:<12} present but unreadable: {ex}")
        else:
            print(f"  {city:<12} not fetched")
    rec = REPO / "results/artifacts/live_dhaka/RECORDER_MANIFEST.json"
    if rec.exists():
        m = json.loads(rec.read_text())
        print(f"  live recorder: {m['ticks']} sweeps, {m['rows_ok']} rows, {m['rows_failed']} failed "
              f"({m['reality']}, every {m['interval_s']}s)")
    for f, what in (("results/forecasting/federated.md", "federated (ML x networking)"),
                    ("results/forecasting/twin_models.md", "trained models"),
                    ("results/forecasting/benchmark.md", "public benchmark (Colab)")):
        print(f"  {'OK  ' if (REPO / f).exists() else 'MISS'} {what:<32} {f}")

    print("\nSTAGE 2 — ROUTE OPTIMISATION")
    for f, what in (("results/routing/stats.md", "routing arms, paired seeds"),
                    ("results/routing/decision_guard_h7200.md", "decision guard"),
                    ("results/routing/live_chain.md", "live chain -> ACT/NO_ACTION"),
                    ("results/routing/incident.md", "NLP incident -> reroute"),
                    ("results/routing/real_demand.md", "real measured demand (Athens)")):
        print(f"  {'OK  ' if (REPO / f).exists() else 'MISS'} {what:<32} {f}")

    print("\nNETWORKING")
    for f, what in (("results/networking/penetration.md", "V2X penetration sweep"),
                    ("results/networking/latency.md", "latency / loss"),
                    ("results/networking/event_sweep.md", "DENM from our own event")):
        print(f"  {'OK  ' if (REPO / f).exists() else 'MISS'} {what:<32} {f}")

    res = REPO / "results/RESULTS.md"
    if res.exists():
        txt = res.read_text()
        print(f"\nEVIDENCE  results/RESULTS.md: {txt.count(chr(10) + '## ')} sections, "
              f"{txt.count('NOT YET PRODUCED')} still missing")
    return 0


def predict(a) -> int:
    """STAGE 1. Data first, then the floors that any model must beat, then the ML x networking run."""
    rc = run(["src/pipeline/forecasting/city_datasets.py", "--city", a.city], f"load and validate {a.city}")
    if rc:
        return rc
    if (REPO / "data/forecasting/live_dhaka/series.npz").exists() or (REPO / "results/artifacts/live_dhaka").exists():
        run(["src/pipeline/forecasting/live_state.py", "--report"], "live Dhaka stream -> series + floors")
    run(["src/pipeline/forecasting/federated_forecast.py", "--self-test"], "verify the federated + V2X mechanics")
    print("\n\033[1mGPU training runs on Colab, never here:\033[0m")
    print("  experiments/notebooks/Predict_BasicTS_Colab.ipynb   official baselines (STID/GWNet/DCRNN/AGCRN/STAEformer)")
    print("  experiments/notebooks/Federated_V2X_Colab.ipynb     federated forecasting over the simulated V2X link")
    print("  push the source first:  bash src/pipeline/forecasting/sync_src_to_drive.sh")
    return 0


def route(a) -> int:
    """STAGE 2. Only meaningful once a forecast exists — that is why it is stage 2."""
    if not (REPO / "data/forecasting/live_dhaka/corridor_edges.json").exists():
        run(["src/pipeline/forecasting/live_to_edges.py", "--map"], "map live corridors onto the real road network")
    rc = run(["src/pipeline/routing/live_chain.py", "--seeds", a.seeds], "live congestion -> routing -> ACT/NO_ACTION")
    run(["results/build_results.py"], "collect every table into results/RESULTS.md")
    return rc


def all_stages(a) -> int:
    return predict(a) or route(a)


def demo(_a) -> int:
    print("starting the demo:  streamlit run demo/app.py")
    return subprocess.call(["streamlit", "run", str(REPO / "demo/app.py")], cwd=REPO)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("status", help="what exists, what is real, what is missing").set_defaults(fn=status)
    sp = sub.add_parser("predict", help="STAGE 1: traffic prediction"); sp.set_defaults(fn=predict)
    sp.add_argument("--city", default="METR-LA")
    sr = sub.add_parser("route", help="STAGE 2: route optimisation"); sr.set_defaults(fn=route)
    sr.add_argument("--seeds", default="11,12,13")
    sa = sub.add_parser("all", help="stage 1 then stage 2"); sa.set_defaults(fn=all_stages)
    sa.add_argument("--city", default="METR-LA"); sa.add_argument("--seeds", default="11,12,13")
    sub.add_parser("demo", help="the examiner-facing app").set_defaults(fn=demo)
    a = p.parse_args()
    if not getattr(a, "fn", None):
        p.print_help()
        return 0
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
