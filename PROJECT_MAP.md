# PROJECT MAP — read this first (5 minutes)

You do not need to understand every file. The project has **6 main source
files** (the brain), **4 command scripts** (what you run), and everything else
is support, evidence, or frozen history.

---

## The 6 main source files (the brain)

| # | File | What it is, in one line |
|---|------|--------------------------|
| 1 | `research/perception/rtdetr_dhaka.py` | The EYES — loads our trained Dhaka detector (rickshaw/CNG/easy-bike) |
| 2 | `scripts/demo_react.py` | The WATCHER — any video in → vehicles tracked → FREE/SLOWING/CONGESTED |
| 3 | `research/routing/r1_router.py` | The NAVIGATOR — best route on the real 6,527-edge Dhaka map under congestion |
| 4 | `research/forecasting/basicts_adapter.py` | The PROPHET's data feed — twin sensors → the forecasting models (GWNet etc.) |
| 5 | `research/control/sumo_marl_env.py` | The SIGNAL BRAIN — 17 traffic lights as learning agents (MAPPO trains on this) |
| 6 | `scripts/same_state_counterfactual.py` | The JUDGE — saves the exact traffic state, runs "do nothing" vs "our control", measures the difference |

**If sir asks "where is your system?" — open these six files.**

## The 4 commands you actually run

| Command | What happens |
|---|---|
| `python scripts/case_report.py --source <video> --location farmgate` | THE demo: detect → state → route → twin PREDICTS next 10 min on that road → acts from the same saved state → proof page |
| `python scripts/same_state_counterfactual.py --camera karwanbazar` | The before/after proof from an identical saved state |
| `python scripts/build_dashboard.py` | Rebuilds the web dashboard from real artifacts |
| `python scripts/build_results_matrix.py` | Rebuilds the results table from real artifacts |

## The evidence (never edited by hand — always produced by runs)

- `docs/RESULTS_MATRIX.md` — every number, with protocol and domain
- `artifacts/` — raw outputs of every experiment (JSON/logs/checkpoints)
- `docs/media/` — the videos and figures (all rendered from runs)

## Your presentation documents

- `docs/PRESENTER_GUIDE.md` — what to SAY (memorize the blocks)
- `docs/INTERVIEW_CARDS.md` — answers to hard questions, incl. weaknesses
- `docs/DATA_INVENTORY.md` — where the 22 GB of datasets physically live

## Safe to IGNORE (support & history — not "the project")

- `paper_labs/` — frozen foundations from earlier phases (never edited)
- `dhakaflow/` — platform plumbing (types, providers, safety contracts)
- `dashboard/index.html` — a GENERATED export, like a PDF; the source is
  `scripts/build_dashboard.py`
- `upstream/` pins, `tests/`, notebooks — infrastructure
- anything in `artifacts/` you don't recognize — run outputs

## The flow, in one line

**video → (1 eyes) → (2 state) → (4 forecast) → (3 route) + (5 signals) →
(6 judge proves the difference)** — six files, one causal chain.
