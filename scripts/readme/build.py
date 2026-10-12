"""Write README.md whole, research first, from the summary files (scripts/paper_map/research.py). Never edit README.md by hand: edit
this script or the summaries, then rebuild. A test fails when README.md differs from what this script writes.

    python scripts/readme/build.py            # write
    python scripts/readme/build.py --check    # exit 1 if README.md is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "paper_map"))
import research as R  # noqa: E402

README = R.ROOT / "README.md"

WHY = ("Most traffic forecasting models, V2X safety protocols and routing ideas are built and tested on roads in Los Angeles, the San Francisco "
       "Bay Area or Europe: loop detectors with months of history, lane discipline, one vehicle type. Dhaka has none of that. Its roads mix "
       "cars, buses, rickshaws, CNGs and motorbikes, its speeds jump from minute to minute, and a camera site has one recorded day. This thesis "
       "takes established methods from their papers and official code, reproduces each one's published result first, and then measures what "
       "happens when it meets Dhaka: forecasting, forecast-aware routing, an ambulance alert over V2X, phone-to-phone alerts without a network, "
       "maps that work on a weak signal, and crash detection on the phone. The web app at the end applies what held up, and says where it did not.")

LAYOUT = [
    "| Folder | What is in it |", "|---|---|",
    "| `core/ml/` | Forecasting (adapters for the official models, training, evaluation, the Dhaka transfer study), perception, the incident text classifier |",
    "| `core/networking/` | V2X channel and delivery, the PONS mesh results, the weak-signal prefetch results, Eclipse MOSAIC |",
    "| `core/simulation/` | The SUMO twin, signal control (sumo-rl), routing, the closed-loop controller, the ambulance study |",
    "| `core/safety/` | Crash detection (WreckWatch rule), hospitals, ambulance reach |",
    "| `core/common/` | Paths, city configs, datasets and recorded data, provenance labels |",
    "| `backend/app/` | The web application only: HTTP routers, live services, alerts, the map app's adapters. It imports from `core/`; `core/` never imports it (a test checks) |",
    "| `frontend/map/` | The main map app: Headway's web frontend (Apache-2.0), pointed at our routing, tiles and search |",
    "| `frontend/` | The research pages (React, under `/app/`) |",
    "| `research/` | Per-study scripts and notes |",
    "| `results/`, `evidence/` | Summaries, logs and SHA-256 hashes for every number. Large run outputs are on Google Drive (`data/MANIFEST.yaml`, `make fetch-data`) |",
    "| `config/cities/` | One file per city; nothing city-specific lives in code |",
    "| `third_party/SOURCES.md` | Every reused repository: URL, commit, licence, paper, files used |",
    "| `docs/` | `PAPER_MAP.md` (every question in full), `EXPERIMENT_PROTOCOL.md`, `RUNBOOK.md` (run commands and the system's earlier record) |",
]

QUICK = [
    "```bash",
    "python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt",
    "make test                                              # backend and research tests",
    "make fetch-data                                        # bring back the data kept off this machine (public data from its source, our runs from Drive)",
    "PYTHONPATH=.:backend python -m core.ml.forecasting.transfer_dhaka.run summary   # rebuild RQ1's summary from its scores",
    "PYTHONPATH=.:backend python -m core.simulation.ambulance.study summary          # rebuild RQ3's summary from its runs",
    "python scripts/paper_map/build.py && python scripts/readme/build.py            # rebuild docs/PAPER_MAP.md and this README",
    "make app                                               # the web app on http://127.0.0.1:8000",
    "make check && make demo-ambulance                      # offline supervisor demos: also demo-forecast, demo-mesh (docs/DEMO.md)",
    "make present                                           # every feature live, computed now, checked against the thesis (docs/LIVE_RUNS.md)",
    "make demo                                              # the talk's live parts one after another on Enter; make run-routing-quick ARGS=\"--quick\", make sweep-v2x ARGS=\"--quick\"",
    "PYTHONPATH=.:backend python scripts/live_twin/learning_run.py --minutes 180      # the live twin's forecasters over 3 simulated hours (docs/EXPLAIN.md)",
    "```",
]


def rq_block(q: dict) -> list[str]:
    head = f"### {q['id']} · {q['title']}" if q["id"].startswith("RQ") else f"### Supporting · {q['title']}"
    L = [head, "", f"*{q['city']} · from `{q['summary']}` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*", "",
         "| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |", "|---|---|---|---|",
         *[f"| {a} | {b} | {c} | {d} |" for a, b, c, d in q["readme_rows"]], "",
         f"**The finding.** {q['finding']}", "", f"**Why.** {q['why']}", ""]
    if q.get("plain"):
        L += ["In plain words, as the app says it:", "", q["plain"], ""]
    return L


def readme() -> str:
    qs = R.all_questions()
    L = ["# Do traffic models and V2X alerts built for Western cities work in Dhaka?", "",
         "*An undergraduate thesis (IUT CSE, Networking Research Group) on machine learning and networking for road traffic, with Dhaka as the case study "
         "and Los Angeles as the comparison city (Berlin is configured; no Berlin result yet). Every number below is generated from a results file by `scripts/readme/build.py`.*", "",
         "## Why", "", WHY, "",
         "## Research questions", "", *R.numbering_table(), ""]
    for group in ("ML", "Networking and safety", "Supporting"):
        L += [f"## {group}" if group != "Supporting" else "## Supporting measurement", ""]
        for q in qs:
            if q["group"] == group:
                L += rq_block(q)
    L += ["## Limitations", "",
          *[f"- **{q['id']}:** {c[0].upper() + c[1:]}{'' if c.endswith('.') else '.'}" for q in qs for c in q["caveats"]],
          *[f"- **Future work, {t.lower()}:** {why}" for t, why in R.PLANNED], "",
          "## Repository layout", "", *LAYOUT, "",
          "## Quick start", "", *QUICK, "",
          "## The system that applies the research", "",
          "The web app is the research put to use, and it states which result each feature rests on.",
          "- **Main map** (`/`): Headway's frontend on our Valhalla routing, OpenFreeMap tiles and Photon search, with Bangla turn-by-turn, the nearest hospitals and SOS.",
          "- **Traffic on the map** (Traffic chip): Los Angeles replays recorded METR-LA speeds at the same weekday and time with D2STGNN's forecast made then (measured on every moment of the test weeks: MAE {layer_mae} mph at 15 / 30 / 60 min against {layer_nc} for no change, `results/forecasting/layer/summary.json`); Dhaka shows each DhaTraX site at this hour on its one recorded day with RQ1's per-site errors. \"Best time to leave\" appears only where the model beats no change at every horizon (Los Angeles), so not in Dhaka. Build: `PYTHONPATH=.:backend python -m core.ml.forecasting.layer.build_la`.".format(**_layer()),
          "- **Research pages** (`/app/lab`): every table above with its sources and caveats; the everyday pages show one plain sentence per result, tagged Simulation, Real recorded or Forecast, with a \"How we know\" link here.",
          "- **Live twin** (`/app/lab/live-twin`): a running SUMO simulation of the Dhaka corridor, seeded from the clock and labelled Simulation; a click places a crash or starts an ambulance (V2X alert, make-way v2, green signals), a slider changes the demand, and three forecasters (River online, Chronos-Bolt zero-shot, no change) predict each road 15 minutes ahead and are scored live. How it works and what was measured: [`docs/EXPLAIN.md`](docs/EXPLAIN.md).",
          "- **City-agnostic:** every city-specific value lives in `config/cities/<city>.yaml`; a city without data for a feature says so.",
          "- **Privacy:** opt-in only, hashed device IDs, raw positions deleted after 24 hours; alerts and SOS run in TEST mode only.",
          "", "Run commands, deployment and the system's earlier record are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).", "",
          "## Licence", "", "MIT (see `LICENSE`). Reused code keeps its own licence; every source is listed in `third_party/SOURCES.md`.", ""]
    return "\n".join(L)


def _layer() -> dict:
    """The forecast layer's card for the README line, from its results file (core/ml/forecasting/layer/build_la.py)."""
    import json
    c = json.loads((R.ROOT / "results/forecasting/layer/summary.json").read_text())["card"]
    return {"layer_mae": " / ".join(f"{c[h]['mae']:.2f}" for h in ("15", "30", "60")),
            "layer_nc": " / ".join(f"{c[h]['no_change_mae']:.2f}" for h in ("15", "30", "60"))}


def main(check: bool) -> int:
    want = readme()
    if check:
        if README.read_text() != want:
            print("out of date: README.md (run python scripts/readme/build.py)")
            return 1
        return 0
    README.write_text(want)
    print("wrote README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
