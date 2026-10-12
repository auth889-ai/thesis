# Runbook and earlier record

Moved whole from README.md on 2026-10-09, when the README became research-first and generated (`scripts/readme/build.py`). Nothing was deleted.
- **Run commands, deployment and the system's features** are here, each with the date it was written.
- **Research numbers here are as of the date in their heading** and use the earlier question numbers (see the numbering table in `docs/PAPER_MAP.md`). The current results are in `README.md` and `docs/PAPER_MAP.md`; where they differ, those are current.
- **Paths:** research modules moved from `backend/app/` to `core/` on 2026-10-09; commands below use the new paths.

## Earlier introduction

**Do zero-shot time-series foundation models beat purpose-trained spatio-temporal graph networks for road traffic — and when does the evaluation protocol matter more than the model?**

Road-traffic speed forecasting on sensor networks, with every model run from its official code and scored under two
protocols: the aggregate protocol every paper reports, and a regime-stratified protocol that scores free flow, the
transition into congestion, and congestion separately. The result is served as a web app: a forecast map for any
city, a leaderboard of reproduced papers, calibrated uncertainty bands, and departure advice with a probability.

This repository covers the arc from controlled reproduction (Protocol A: the papers' own split, four models reproduced
within 2 %) to the question the papers do not ask (Protocol B: the same models at congestion onset) to deployment
(the served forecaster behind a map, an assistant and Alexa, with a SUMO digital twin that measures whether the
advice helps the network).

| | |
|---|---|
| Baseline paper | Yanes-Pulido, J. and Rodrigues, F. (2026). *Time Series Foundation Models as Strong Baselines in Transportation.* arXiv:2602.24238 |
| The protocol question | Reyes et al. (2026). *Do Time Series Foundation Model Benchmarks Hide Regime-Dependent Failures? Evidence from Traffic Speed Forecasting.* arXiv:2606.18367 |
| Reproduction protocol | DCRNN, Li et al. (ICLR 2018): chronological 70/10/20, 12 steps in, horizons 15/30/60 min, observed entries only |
| Master plan (55 papers with official code, build order) | [`docs/MASTER_PLAN.md`](docs/MASTER_PLAN.md) |
| Results, machine-readable | [`results/forecasting/`](results/forecasting/) (`trained_results.csv`, `model_comparison.json`, `opencity_crosscity.md`) |

[Why this project exists](#why-this-project-exists) · [Findings](#findings) · [Experimental design](#experimental-design) · [Protocols](#protocols) · [Deployment: the web app](#deployment-the-web-app) · [Data and models](#data-and-models) · [Repository layout](#repository-layout) · [Setup](#setup) · [Reproduce a row](#reproduce-a-row) · [Tests](#tests) · [Documentation](#documentation) · [Limitations](#limitations) · [Planned work](#planned-work) · [Citation](#citation)

## Why this project exists

Traffic forecasting papers report one number: mean error over every five-minute window of a test month. Most of those
windows are free flow, where persistence is already good. The windows a traveller cares about are the few where a
road tips from 60 mph to 20, and a 2026 study found that there the error triples and a "90 %" interval covers about
half the outcomes. At the same time, general time-series foundation models (Chronos-2, TimesFM) now match or beat
purpose-trained graph networks on the aggregate number without seeing the city.

Two questions matter in practice, and this repo treats them as separate jobs:

| Job | Question | Baseline it replaces |
|---|---|---|
| Forecasting | What is the speed on this road 15, 30, 60 minutes from now? | Graph networks trained per city (DCRNN, Graph WaveNet, STID, STAEformer) |
| Onset detection | Is this road about to enter congestion, and how early can we say so with an honest interval? | Persistence and historical average, the only baselines papers report for this |

The core hypothesis: **foundation models win the aggregate protocol and lose the regime protocol, and regime-aware
conformal calibration repairs the interval without giving back the aggregate gain.** Hence two protocols that share
the same models, data and horizons but differ in which windows are scored, and a rule that A and B are never averaged.

Models run so far: DCRNN, Graph WaveNet, STID, STAEformer, MegaCRN, D2STGNN (official BasicTS configs, trained on AWS GPUs),
OpenCity-plus (released weights, authors' commands), Chronos-Bolt, Chronos-2, TimesFM 2.5 (released weights). Nothing is
re-implemented.

## Findings

Scores are MAE in mph on held-out test windows (lower is better). Protocol A numbers are compared with the published
rows of the same model on the same dataset; Protocol B numbers have no published counterpart, which is the point.

### Protocol A — reproduction (the papers' split)

| Model | Dataset | Ours 15 / 30 / 60 min | Published | Gap |
|---|---|---|---|---|
| DCRNN | METR-LA | 2.67 / 3.08 / 3.57 | 2.77 / 3.15 / 3.60 | -3.5 / -2.3 / -0.8 % |
| DCRNN | PEMS-BAY | 1.31 / 1.66 / 1.97 | 1.38 / 1.74 / 2.07 | -5.1 / -4.9 / -4.7 % (63 of 100 epochs: the 16-hour cap stopped it; best-validation checkpoint) |
| D2STGNN | METR-LA | 2.56 / 2.91 / 3.36 | 2.56 / 2.90 / 3.35 | +0.1 / +0.5 / +0.1 % |
| MegaCRN | METR-LA | 2.63 / 3.02 / 3.48 | 2.52 / 2.93 / 3.38 | +4.4 / +3.0 / +2.8 % |
| Graph WaveNet | METR-LA | 2.72 / 3.11 / 3.59 | 2.69 / 3.07 / 3.53 | +1.1 / +1.3 / +1.8 % |
| Graph WaveNet | PEMS-BAY | 1.31 / 1.64 / 1.95 | 1.30 / 1.63 / 1.95 | +0.6 / +0.5 / −0.2 % |
| STID | METR-LA | 2.82 / 3.21 / 3.59 | 2.82 / 3.19 / 3.55 | 0.0 / +0.7 / +1.2 % |
| STID | PEMS-BAY | 1.32 / 1.64 / 1.92 | 1.31 / 1.64 / 1.91 | +0.6 / 0.0 / +0.5 % |
| STAEformer | METR-LA | 2.67 / 2.98 / 3.35 | 2.65 / 2.97 / 3.34 | +0.9 / +0.5 / +0.3 % |
| PatchSTG, authors' released weights | LargeST-SD (716 sensors, flow) | 16.85 / 29.57 / 11.01 % (12-step MAE / RMSE / MAPE) | 16.90 / 29.27 / 11.23 % | -0.3 % MAE |
| PatchSTG, trained here (authors' `main.py`, their 50 epochs, best epoch 48) | LargeST-SD (716 sensors, flow) | 16.98 / 29.38 / 10.98 % (12-step MAE / RMSE / MAPE) | 16.90 / 29.27 / 11.23 % | +0.5 % MAE |
| PatchSTG, trained here (authors' `Solver`, their 50 epochs, best epoch 46; epochs 1–2 on a T4, 3–50 on an A10G after one resume) | LargeST-GLA (3,834 sensors, flow) | 18.90 / 32.32 / 11.26 % (12-step MAE / RMSE / MAPE) | 18.96 / 32.33 / 11.44 % | -0.3 % MAE |
| OpenCity-plus zero-shot | PEMS07M (held out of its pre-training) | 4.50 (12-step) | 4.50 | 0.0 % |
| OpenCity-plus zero-shot | TrafficSH (held out) | 0.55 | 0.55 | 0.0 % |

MegaCRN sits 4.4 % above its authors' README at 15 min and within 3 % at 30 and 60; the authors' number comes from their own
training code, ours from the BasicTS fair-comparison config, which is the comparison the harness paper reports.
Protocol check: our historical-average floor on METR-LA is 4.19 MAE against the DCRNN paper's 4.16 (0.7 %), so the
split, masking and metric are the papers' own. Every row above was trained or evaluated on AWS (g4dn / g5, Tesla T4)
with the official config unmodified except epochs and horizons; checkpoint SHA-256 and the log path sit beside each
row in `results/forecasting/trained_results.csv`.
The PatchSTG row is the authors' own `main.py` in test mode with their released SD checkpoint, run on this laptop's CPU in 87 s; the
release carries no adjacency file, so their `construct_adj` rebuilt it from the training split, which is the only difference from
their committed log (16.90 / 29.27 / 11.23). The trained SD row is `python main.py --config ./config/SD.conf` as released on an AWS g4dn.xlarge (Tesla T4), about 174 s per epoch. Released-weights rows for GBA, GLA and CA (+0.3 / -0.4 / +1.7 % MAE) are in `results/forecasting/patchstg_largest.md`; GLA has also been trained here (row above; log and checkpoint hash in `evidence/patchstg/GLA/`); GBA and CA have not.

Reading: the pipeline reproduces the field. That is the precondition for Protocol B meaning anything.

### Protocol B — regime-stratified (METR-LA, all 207 roads, 120 consecutive test windows, 96-step context, three seeds)

Congestion is below 0.6 × the road's free-flow speed (85th percentile of its training values). Onset is the first
window of a congested run. Sensor outages (0.0) are excluded from every metric. Mean ± standard deviation over seeds
11, 23 and 37, each a different contiguous block of the test region.

| Model | MAE@15 all | MAE@15 congested | Onset detection rate | Mean lead (min) |
|---|---|---|---|---|
| MegaCRN (trained) | 2.99 ± 0.20 | 5.77 ± 0.61 | 0.69 ± 0.01 | 48.5 |
| D2STGNN (trained) | 2.94 ± 0.20 | 5.69 ± 0.66 | 0.68 ± 0.02 | 49.3 |
| DCRNN (trained) | 3.05 ± 0.23 | 5.97 ± 0.68 | 0.64 ± 0.02 | 49.6 |
| STAEformer (trained) | 3.06 ± 0.17 | 6.11 ± 0.72 | 0.60 ± 0.01 | 53.1 |
| Graph WaveNet (trained) | 3.18 ± 0.27 | 6.60 ± 0.79 | 0.54 ± 0.02 | 50.2 |
| STID (trained) | 3.29 ± 0.26 | 7.26 ± 0.81 | 0.45 ± 0.04 | 53.5 |
| Chronos-2 zero-shot, multivariate | 3.72 ± 0.20 | 7.49 ± 1.08 | 0.31 ± 0.07 | 46.3 |
| Chronos-2 zero-shot, univariate | 3.91 ± 0.17 | 7.97 ± 1.18 | 0.31 ± 0.07 | 46.9 |
| XGBoost | 4.02 ± 0.30 | 8.58 ± 0.61 | 0.26 ± 0.03 | 30.5 |
| Persistence | 4.03 ± 0.26 | 7.43 ± 0.71 | 0.04 ± 0.04 | 60.0 |
| Historical average | 5.71 ± 0.53 | 17.96 ± 0.73 | 0.17 ± 0.03 | 53.4 |

Reading: on the aggregate column the trained models sit within 0.3 mph of each other; in congestion the spread opens
and against the zero-shot models reaches 1.7 mph. The onset column separates the families by a factor of two with
seed spread of one or two points: MegaCRN, D2STGNN and DCRNN catch two onsets in three, Chronos-2 one in three, persistence
almost none. Chronos-2's multivariate mode beats its univariate mode and persistence on aggregate and still trails
every trained model on every column. The 80-road single-seed block reported earlier gave the same ordering. TimesFM
and Chronos-Bolt were scored on that block only (28 % and 32 % of onsets). The page `/lab/models` → Onset serves the
cross-seed table with the spread.

### Calibrated intervals per regime (METR-LA, all 207 roads, three seeds, 90 % level, calibrated on the validation block, scored on the test block)

Three MAPIE split-conformal calibrators on each model's point forecast: one global quantile; one per regime observed at
prediction time; one per regime the model itself predicts at the horizon. Coverage at 15 minutes, by where the truth landed;
the transition column carries the seed spread.

| Model | Calibrator | All | Free flow | Congested | Transition into congestion |
|---|---|---|---|---|---|
| MegaCRN | global | 0.90 | 0.93 | 0.78 | 0.45 ± 0.01 |
| MegaCRN | regime-aware | 0.91 | 0.92 | 0.86 | 0.39 ± 0.01 |
| MegaCRN | predicted-regime | 0.91 | 0.92 | 0.87 | 0.52 ± 0.03 |
| D2STGNN | global | 0.90 | 0.93 | 0.79 | 0.47 ± 0.03 |
| D2STGNN | predicted-regime | 0.91 | 0.92 | 0.87 | 0.53 ± 0.04 |
| DCRNN | global | 0.90 | 0.93 | 0.78 | 0.43 ± 0.02 |
| DCRNN | predicted-regime | 0.91 | 0.92 | 0.87 | 0.50 ± 0.04 |
| STAEformer | global | 0.90 | 0.93 | 0.78 | 0.40 ± 0.02 |
| STAEformer | predicted-regime | 0.91 | 0.92 | 0.86 | 0.46 ± 0.04 |
| Chronos-2 (multivariate) | global | 0.90 | 0.93 | 0.75 | 0.23 ± 0.02 |
| Chronos-2 (multivariate) | predicted-regime | 0.91 | 0.92 | 0.84 | 0.25 ± 0.05 |
| Persistence | global | 0.90 | 0.93 | 0.77 | 0.23 ± 0.03 |

Reading: a "90 %" interval reported the usual way is a 92 % interval in free flow and a 20 to 39 % interval at the moment a
jam forms. Conditioning on the regime observed now repairs congestion (0.77 → 0.88) and makes the transition *worse*
(0.39 → 0.33), because at a transition the observed regime is still free flow. Conditioning on the regime the model
predicts repairs congestion fully (0.90) and lifts the transition to 0.50 at 15 min and 0.70 at 60 min for STAEformer,
but no calibrator reaches 90 % there. The transition is a forecasting problem, not a calibration problem: an interval can
only be honest about a jam the model has some signal of. Full table in `results/forecasting/conformal.md`.

### What to take away

- Reproduction is solved: four models within 2 % of their papers, two foundation-model evaluations exact.
- Aggregate MAE is nearly blind to the congested regime; the regime column is where models separate.
- A model can lose on aggregate and win on onset.
- Published-style 90 % intervals cover about a third of transitions. Regime conditioning on the model's own forecast
  recovers congestion coverage and half of the transition gap; the rest needs a better onset forecast, not a wider band.

## Experimental design

| | Forecasting | Onset detection |
|---|---|---|
| Task | speed at +15 / +30 / +60 min per sensor | first congested window per sensor, lead time, interval coverage at the transition |
| Baselines | DCRNN, Graph WaveNet, STID, STAEformer, persistence, historical average | persistence, historical average |
| This work | the same models plus D2STGNN, MegaCRN, STD-MAE, HimNet, BigST, PatchSTG, STGformer, OpenCity, UniST, Chronos-2, TimesFM, Moirai, Time-MoE, each from official code | the same models under Protocol B, then MAPIE conformal intervals calibrated per regime |
| Metric | MAE, RMSE, MAPE on observed entries | congested-regime MAE, onset detection rate, mean lead, 90 %-interval coverage at onset |

Models are trained per dataset. Datasets: METR-LA (207 sensors), PEMS-BAY (325), PEMS04 / PEMS08 (flow),
LargeST-SD (716) and GLA (3,834). There is no Dhaka traffic dataset yet: the corridor recording used earlier was
derived from Google Routes results and has been withdrawn (see `docs/proposals.md`).

## Protocols

| Protocol | Windows scored | Status |
|---|---|---|
| A — aggregate | every test window, as in the papers | GWNet, STID, STAEformer, OpenCity, Chronos-Bolt complete |
| B — regime-stratified | free-flow, onset and congested windows separately; detection and lead | METR-LA and PEMS-BAY; served at `/api/protocol-b/onset` |
| B + conformal | 90 % intervals per calibrator and regime, calibrated on the validation block | METR-LA; served at `/api/protocol-b/conformal` |
| Deployment | the served model behind the map for any city, outcomes recorded, weekly recalibration | serving exists for GWNet; conformal bands and departure advice pending |

Protocol B uses an 80-node subsample and a contiguous block so onset transitions are real, not shuffled. That is a
deliberate departure from A and the two are never averaged.

## Deployment: the web app

The controlled experiments answer "how accurate, and where". The app answers "what happens when a person uses it".
Every number on a page is read from a model run, a dataset or an API; the structure test fails if a page hardcodes one.

### App structure (2026-10-06): the traffic app first

The menu is Home (`/`), 3D City (`/3d`), Add city (`/add-city`), Emergency (`/emergency`), Offline alerts
(`/offline`), Research (`/lab`) and Settings (`/settings`); the table is `frontend/src/app/nav.ts`. The LIFE OS pages
are kept and reached by address only: `/today`, `/plan`, `/goals`, `/messages`, `/activity`, `/map`, `/city`,
`/you-lifeos`. The top bar has a go-anywhere search (`frontend/src/app/Search.tsx`, logic in `searchRows.ts`): a
page by its label in either language, a built city (switches to it), a place inside the selected city's area (opens
Home with it as the destination), or "Add '<name>' as a city" when no built city matches. Every map with 3D
buildings says "Zoom in to see 3D buildings" while the view is above the buildings' minimum zoom (14, from
`/api/config/map`). Emergency shows the city's numbers from its config, never dialled, and the ambulance results;
Offline alerts says "no mesh result yet" until the mesh is wired in.

```bash
cd frontend && npm run build && cd ..
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011   # open http://127.0.0.1:8011/
cd frontend && npx vitest run src/app src/i18n && npx tsc --noEmit                               # menu, search, translations
PYTHONPATH=backend pytest backend/tests/test_structure_migration.py -q                              # feature folders, file sizes
```

Checked once in a browser on Dhaka, in Bangla: `evidence/app_structure/record.json` lists what was seen and what was not.

**Plain language (2026-10-06, `CLAUDE.md` "Plain language rule").** On the everyday pages a result is one sentence a
non-expert understands, a tag (Simulation, Real recorded, Forecast) and "How we know →" to Research
(`frontend/src/components/PlainResult.tsx`). The sentence's numbers are computed beside the table in the same result
file (`plain` in `core/simulation/ambulance/results.py` and `core/networking/mesh/results.py`; tests check they equal the rows).
The full tables, sources and caveats are on Research (`/lab/evidence`, `/lab/control-room`), unchanged.

**Story mode, the tour (item 7, 2026-10-06).** The "Tour" button in the top bar, or the address `/?tour=1`, walks a
viewer through nine steps: Home, the trip, the recorded day, 3D City, the ambulance, Emergency, Offline alerts, Add
city and Research, each with two plain sentences in both languages (`frontend/src/app/storySteps.ts`, `Story.tsx`;
text under `story.*`). Arrow keys move, Escape ends, the place survives a reload. No step states a number: each shows
the live page. Check: `evidence/app_structure/story_check.json`.

**Translation (item 5, 2026-10-06).** Home, 3D City, Emergency and Offline alerts are fully in Bangla and English:
every label, sentence and the twin's status words go through `frontend/src/i18n/`. What stays as written: source and
product names (OpenStreetMap, Overture Maps, SUMO, DhaTraX), the tag's provenance words on hover, and the dataset
authors' own caveat, quoted. The Bangla is machine-written and awaits a native speaker (`docs/BANGLA_REVIEW.md`);
`evidence/app_structure/translation_check.json` records the browser scan.

| Page | What it shows | Backed by |
|---|---|---|
| Forecast map | every sensor of a dataset at a chosen moment, 15 / 30 / 60 min ahead, model selector; fresh inference per request from a hash-verified checkpoint | `GET /api/forecast-map/{dataset}` |
| Leaderboard | each reproduced paper, our number, the published number, the gap | `results/forecasting/trained_results.csv` |
| City | route times for any city through Amazon Location; live traffic only where the provider returns any (it returns none for Dhaka: free-flow times only, checked 2026-10-04), each value labelled live / free-flow / recorded with data age | `core/common/data/live_providers/` |
| Train | pick model and dataset, launch on AWS, watch the log, the result registers itself | `POST /api/train` |
| Twin | the forecast fed into SUMO on the frozen Dhaka corridor; vehicle-hours with and without advice | `core/simulation/twin/`, `results/current/closed_loop/` |
| Assistant · Alexa | questions answered from the same forecast API, over Bedrock and the MCP server at `/mcp` | `backend/app/agent/`, `backend/app/mcp/` |
| Evidence | checkpoint hashes, logs, the protocol check | `/lab/evidence` |

| Onset | Protocol B: every model on the same windows, congested-regime error, onsets detected, mean lead | `GET /api/protocol-b/onset` |
| Sparse | imputation under the ImputeFormer protocol: a quarter of observed points hidden, scored on those; mean, linear, last-value and ImputeFormer with the published rows | `GET /api/protocol-b/imputation` |
| Map → Your phone is the sensor | share your position while you move; fixes are snapped to the road with Amazon Location SnapToRoads, binned into 70 m road-direction cells every five minutes and drawn on the map with how many devices each rests on; device ids hashed, raw fixes purged after 24 h | `POST /api/probes`, `GET /api/probes/cells`, `GET /api/probes/status`; tables `probe_points`, `probe_cells` |

| City → Leave when? | the shortest sensor corridor from the selected road, the served model's forecast per leg at the horizon reached, the 90 % worst case from the stored conformal half-widths, and the latest departure for a deadline | `GET /api/protocol-b/departure`, `GET /api/protocol-b/sensors` |
| City → About to tip | roads the served model forecasts into congestion within the hour at this moment; watch one and be told when it happens, once per episode | `GET /api/protocol-b/onset-now`, `/api/watch/roads` |

Pending pages, each tied to a phase in the master plan:
zero-shot upload for any city (P9), alerts (P10), cross-city page (P11).

## Data and models

Datasets and checkpoints are not stored in git.

| Item | Where | Note |
|---|---|---|
| METR-LA, PEMS-BAY | `liyaguang/DCRNN` release files, fetched by `core.common.data` | the canonical files, protocol validated |
| PEMS03/04/07/08, LargeST | BasicTS and LargeST releases | LargeST data is CC BY-NC 4.0 |
| Trained checkpoints | S3 and `results/forecasting/checkpoints/` | SHA-256 recorded per row |
| Foundation weights | Hugging Face: OpenCity-plus, Chronos, TimesFM | used as released |
| Official code | pinned in `upstream/UPSTREAM_PINS.yaml`, fetched into an external workspace, never committed, never modified | licence read at pin time |

## Repository layout

```
core/ml/forecasting/        training (BasicTS adapter, AWS launcher), evaluation (protocols A and B), live, opencity, serving
core/common/data/               datasets, live providers (Amazon Location first), recorder
backend/app/{routing,twin,control,networking,protocols}/   SUMO twin, V2X channel, closed loop
backend/app/{agent,mcp,lifeos,plan,commute,transit,profile}/   the assistant, Alexa surface, person-side planning
frontend/src/features/          forecast, results, twin, mobility, today, plan, assistant, you, references, system
results/forecasting/            trained_results.csv, benchmark_floors.md, model_comparison.{md,json}, opencity_crosscity.md, logs
docs/                           MASTER_PLAN.md, TRAFFIC_PHASES.md, TRAFFIC_SOTA_PAPERS.md, TRAFFIC_FULL_SCOPE.md, EXPERIMENT_PROTOCOL.md, GRAVEYARD.md
upstream/UPSTREAM_PINS.yaml     every official repository, commit and licence
```

## Setup

```bash
pip install -r backend/requirements.txt
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --port 8000     # API + built web app + /mcp
cd frontend && npm install && npm run build
```

Keys live only in `.env` (names only, never printed): `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`,
`BEDROCK_REGION`, `AWS_LOCATION_REGION`. Without them the app serves recorded data and says so; no Google key is needed.
GPU is required for training (AWS g4dn / g5 through the launcher, or Colab); evaluation and the app run on CPU.

## Reproduce a row

```bash
# Protocol A, one model, official config unmodified except epochs/horizons
python -m core.ml.forecasting.training.aws_train --launch --model GWNet --dataset METR-LA   # then --collect
# Protocol B, every model with a checkpoint or released weights
python -m core.ml.forecasting.evaluation.evaluate_models --all
```

Each run writes its row, log path and checkpoint hash into `results/forecasting/`; the leaderboard page reads that file.

## Cities

A city is one file, `config/cities/<city_id>.yaml`: display names per language, bounding box, time zone, default
languages, emergency numbers, units, driving side, vehicle classes, enabled plugins, datasets and the SUMO network.
Every key must be present; a value nobody has sourced is `null` with a comment saying why, and each value names its
source. Three evaluation cities have one: `dhaka`, `los_angeles`, `berlin`.

```bash
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city los_angeles   # box -> OpenStreetMap extract -> SUMO network -> random demand
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city dhaka         # prebuilt network: checked against its recorded hashes, not rebuilt
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city berlin        # refused: its config has no bounding box yet
PYTHONPATH=backend python -m core.simulation.twin.runtime --arm static --seed 11 --horizon 900 --out /tmp/dhaka_static   # the Dhaka check below
PYTHONPATH=backend python -m pytest backend/tests/city -q                # includes a real build of a fourth city (Vaduz) from a fixture config
cd frontend && npm test && npm run build
```

| City | Network | Evidence |
|---|---|---|
| Dhaka | the frozen Lab 02 corridor (`dhaka_r1`) and its calibrated demand, loaded through `dhaka.yaml` | `evidence/cities/dhaka/build.json` (both hashes equal the config's) |
| Los Angeles | built 2026-10-05 from OpenStreetMap data of 2026-10-04T22:44:33Z: 2650 edges, 1230 junctions, 437 traffic lights; 900 generated vehicles | `evidence/cities/los_angeles/build.json` and `build.log` (OSM file hash, commands, SUMO 1.27.1) |
| Berlin | none: the Berlin V2X paper and README give no coordinates and the dataset is not downloaded, so the box is `null` | — |

Built demand is generated by SUMO's `randomTrips` and labelled `SYNTHETIC_WHAT_IF`; it is never a measurement of a
city's traffic. The Los Angeles box is a 0.04° square inside the METR-LA sensor area, not the whole area.

**Dhaka gives the same number through its config.** The static arm, seed 11, 900 s, on the frozen network:
`total_vehicle_hours` 218.91972222222222 in the committed record (`results/routing/static_s11_h900/metrics.json`),
218.91972222222222 run before the change and 218.91972222222222 after it; 917 vehicles arrived each time and all
2290 per-vehicle rows are identical (`evidence/cities/dhaka/rerun_static_s11_h900/`).

**In the web app** the top bar has a city switcher (the configured cities) and a language switcher. Languages are the
files in `frontend/src/i18n/locales/`; adding one is adding a file. English and Bangla ship. Until a person picks a
language, the selected city's first supported language is used, so Dhaka opens in Bangla. A city with no data for
the City page says "No data for this city" (Berlin today).

Limits, stated: the Bangla text is machine-written and has not been reviewed by a native speaker (`bn.json` says so in
its first line). Only the shell (navigation, top bar, hero band, footer) and the City page's own text are translated;
the panels inside it (road inspector, selected road, leave-when, about-to-tip, the sensor map) and every other page
are still English. Other Dhaka-specific values still in code are listed in `docs/proposals.md`.

## Everyday home (the Today page)

`/` opens the Today page, and its top is the home: the selected city on the worldwide 3D map, a trip across it, and
when to leave. Pick a city in the switcher or add one; click the map twice (start, then destination) or search a
place; the route is found on the city's own road network (OpenStreetMap through SUMO's netconvert), with no map
provider.

- **Colours and times come only from measured speeds and forecasts made from them.** A road section with no reading is
  drawn as a grey dashed line and called "no traffic data". **Today no city has traffic data**, so every route is grey
  and no travel time in traffic is given: no phone cell lies inside any built city, the PeMS account for Los Angeles
  is pending, and no Dhaka field counts exist.
- Every traffic value carries a tag: **real** (who measured it, the time it refers to), **simulated** (what it is
  calibrated to, or "uncalibrated") or **forecast** (the model, what it rests on, how its uncertainty is given). The
  drive time at the map's speed limits is shown as simulated and uncalibrated. A value without a tag is not shown.
- The slider has four stops (now, +15, +30, +60 minutes), the horizons a forecast is issued at. A section is forecast
  only from 8 of its own readings in a row; the range shown is the model's own 10 to 90 %, labelled uncalibrated.
- "Leave when?" answers only when the route has traffic data, and says what share of the route's length it covers.
- A destination outside the city's built area is refused, with a link to build a larger area.
- Place names are suggested as you type by Photon (komoot, Apache-2.0, OpenStreetMap data), which is built for
  search-as-you-type; Nominatim's usage policy forbids auto-complete, so it answers only one explicit lookup of a typed
  place. The browser waits for a pause in typing, asks from 3 characters, at most once a second, never for a typed
  `lat, lon`, and cancels a lookup newer text made stale; the backend paces and caches (`third_party/SOURCES.md`,
  "Place search"). A city with a routing server offers any place in the city; one without offers the built area only.
- "Simulated view" draws the twin's generated traffic on the same map, labelled SIMULATED; it starts a simulation
  only when switched on and stops it when switched off.
- The alerts strip lists the city's alerts with a stamp each (real, recorded data, simulated, test). Ambulance, mesh
  and SOS alerts are named there and not built yet.

```bash
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/city/test_city_home.py -q        # router, real speeds, forecast gate, tags, feed
cd frontend && npm test && npm run build                                                   # colours, departures, tag rendering
PYTHONPATH=backend python -m core.common.data.station_matching --city los_angeles --stations <graph_sensor_locations.csv>   # 24 PeMS stations -> road sections
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011              # then open http://127.0.0.1:8011/
```

API: `GET /api/trip/{city_id}?origin=lat,lon&destination=lat,lon`, `GET /api/alerts/feed?city_id=`. Evidence:
`evidence/home/record.json` (what each city's page said, screenshots, and what was not checked).

### Whole-city routes (added 2026-10-06)

A city whose config declares `routing:` (Dhaka, Los Angeles) also gets a route **anywhere in the city**, outside the
built area too, from the city's own Valhalla server (`infra/valhalla/README.md`: instance, hours, cost, tags, start and
stop commands). Under the trip panel: car or motorcycle, the alternatives the server offers, one plain sentence per
route with the tag **Map speeds** (the time is the map's usual speeds, never live traffic), turn-by-turn steps, and the
OpenStreetMap / Valhalla credit. Where a recorded site stands on the route, a second sentence with the tag
**Real recorded** gives the time once those stretches are re-timed with the speed recorded there (clock time from
"Recorded day", else the city's time now). The route is drawn on the map in one neutral colour beneath the section
route, because map speeds carry no traffic class. A city without `routing:` shows nothing; a server that is not set
or does not answer is said plainly ("not running right now"), never guessed around.

```bash
TRAFFICTWIN_VALHALLA_URL_DHAKA=http://<ip>:8002 TRAFFICTWIN_VALHALLA_URL_LOS_ANGELES=http://<ip>:8003   # in .env, printed by infra/valhalla/launch.sh
python -m pytest backend/tests/routing/test_valhalla.py -q                                 # the answer read faithfully, re-timing, refusals
cd frontend && npx vitest run src/features/today                                           # the sentence's numbers from the summary, the map features
```

API: `GET /api/route/{city_id}?origin=lat,lon&destination=lat,lon&profile=car|motorcycle&at=HH:MM`.

## Ambulance reach, nearest hospitals, map matching (added 2026-10-06)

On the Emergency page, under the numbers and the ambulance sentence: **How far can an ambulance reach**. One sentence with the
tag **Map speeds**: the share of the city an ambulance reaches from its nearest hospital within 10, 20 and 30 minutes on the city's
own Valhalla server; where the city has recorded sites (Dhaka: DhaTraX), a second sentence with the tag **Real recorded** gives
the same shares with the recorded speeds at a clock time on the dataset's day. A map with the hospitals OpenStreetMap tags
`emergency=yes`, the chosen hospital's 10/20/30-minute polygons (map speeds) or the recorded variant as grid cells; a click on
the map (or "From my location") lists the nearest three hospitals by drive time, each as a sentence with its tag. The full table
(per hospital, both variants, the sites, the method, the hashes) is on Research. Phone fixes shared on `/map` are now matched to
the road on the city's own server (`snapper: valhalla`) when the city declares one; Amazon Location only otherwise.

```bash
python -m core.safety.hospitals --city dhaka                      # one Overpass query -> data/cities/dhaka/hospitals.json (+ sha256)
python -m core.safety.reach build --city dhaka --at 08:30         # the matrix build on the live server -> results/reach/dhaka/summary.json, evidence/reach/dhaka/
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/emergency/test_reach.py backend/tests/routing backend/tests/probes -q
cd frontend && npx vitest run src/features/emergency src/lib/places.test.ts
```

API: `GET /api/emergency/reach/{city_id}` (the built file), `…/nearest?lat&lon&k`, `…/isochrone?lat&lon`. Evidence:
`evidence/reach/dhaka/` (summary + sha256, hospitals + sha256, build log, four screenshots). Dhaka, 2026-10-06: 2 610 grid
points at 500 m, 37 hospitals; 9.7 / 27.7 / 45.9 % of the extent within 10 / 20 / 30 min; with DhaTraX speeds at 08:30 the two
sites (BM +8 s, INT +13 s per path through them) change thousands of hospital→point times but not those shares at 0.1 %.

## Crash SOS (TEST mode, added 2026-10-06)

On the Emergency page, last card: off until the person arms it. The phone's motion sensor (DeviceMotion) runs through WreckWatch's
rule (White et al. 2011: a jolt of at least 4 g; a speed over 15 mph when a speed is known) — or one of three labelled synthetic traces
is replayed through the same rule on a laptop. A jolt starts a 15-second countdown with a Cancel button; when it reaches zero the alert
path is shown step by step, computed by the backend from files and the city config: (1) the jolt on the device, (2) the countdown,
(3) over the mobile network a TEST alert placed in this app's own alert strip and the city's ambulance number shown, never dialled —
or, with no network, the phone-to-phone mesh with the city's saved mesh result (Simulation tag), (4) "nothing was sent". The TEST SOS
appears on Home's alert strip with the stamp TEST and never leaves the machine (no SNS, no SMS, no call). The rule, its source and the
peak seen stay one small line at the bottom. Research shows the synthetic traces table (peak, detected, time, hashes).

```bash
python -m core.safety.sos build                                                          # research/sos/traces/*.json + SHA256SUMS, evidence/sos/results.json
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/emergency/test_sos.py backend/tests/test_alerts.py -q
cd frontend && npx vitest run src/features/emergency
```

API: `GET /api/emergency/sos/results`, `GET /api/emergency/sos/trace/{kind}`, `GET /api/emergency/sos/path/{city_id}?online&peak_g`,
`POST /api/emergency/sos/test`. Evidence: `evidence/sos/` (results + sha256, the traces' SHA256SUMS, the offline path answer, four
screenshots, `app_check.json` with what was and was not checked — a real phone's sensor was not).

## Works with weak signal (Q3, 2026-10-07)

On Home, once a whole-city route is chosen:
- **Where the signal may be weak**, along the route in 100 m steps and in your direction of travel. This follows Bartendr
  (Schulman et al., ACM MobiCom 2010). The steps are graded strong, medium, weak, no signal (a tunnel on the city's own road
  data) or not known, from opted-in phones' recorded readings in that direction. The panel says where history is missing.
  Browsers report only a network type and download speed, and only on Chrome for Android. The mapping to Bartendr's signal
  levels is ours and is shown with the result.
- **Save this trip for weak signal** stores the route, directions, alerts and the map tiles along the route on the device:
  - The tiles come from **our own map**: Planetiler (Apache-2.0) built from the same OpenStreetMap extract, one PMTiles
    file per city in our bucket, read through this app.
  - OpenFreeMap stays for normal viewing and is never prefetched.
  - With no network, Home switches to the saved map and the last saved answers. The app shell is cached by Workbox (MIT).
- **Estimated radio energy** of the saved bytes, three ways: saved now on a strong signal, fetched as needed along the drive,
  or Bartendr's minimum-energy schedule. It is estimated from Bartendr's Palm Pre measurements, not measured on our phones.
  Spreading the download along a live drive comes with live navigation (Q2b).
- **Your own forecast** for repeated trips (BreadCrumbs, Nicholson and Noble, ACM MobiCom 2008):
  - Save a place or Home, then "Get me home".
  - With "Learn my connectivity" on, the phone learns that trip's signal on the device only.
  - The forecast is used after 5 trips; until then it shows "learning: n of 5".
- **Low-data mode** (Settings): no 3D buildings, smaller saved trips, alerts once a minute. Every trip shows "this trip used N MB",
  as reported by the browser.

```bash
infra/tiles/run.sh                                            # after `aws login`: Planetiler on the running Valhalla instance -> s3://dhakaflow-routing-<acct>/tiles/<city>/basemap.pmtiles
python infra/tiles/make_style.py                              # our style from OpenFreeMap's liberty (BSD-3) with our sources, sprite and glyphs
PLAYWRIGHT_BROWSERS_PATH=~/Library/Caches/ms-playwright node frontend/tests/weak_signal.experiment.cjs 3    # 4 networks x 2 arms x 3 runs, app served at :5173
python -m core.networking.prefetch.results                     # results/networking/prefetch/summary.json + evidence/prefetch/ (energy estimate included)
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/routing backend/tests/networking backend/tests/test_probes.py backend/tests/test_tiles_proxy.py -q
cd frontend && npx vitest run src/lib src/features/today
```

API: `GET /api/route/{city}/signal?origin&destination&profile`, `GET /api/tiles/{city}/basemap.pmtiles` (byte ranges),
`GET /api/tiles/{city}/info`, `GET /api/networking/prefetch`. Sources and quotes: `third_party/SOURCES.md`, "Works with weak signal".

## Live navigation (Q2b, 2026-10-07)

On Home, below a whole-city route: **Start a simulated drive** (moves along the route by itself, ×8 speed, labelled SIMULATION;
it never teaches the app your trips) or **Start with my location** (the browser asks first). Car or Motorbike follows the route
panel's choice. Turn-by-turn runs on Ferrostar (Stadia Maps, BSD-3): its core asks this app's proxy, which asks the city's own Valhalla
server, and its map component draws the route, your position and the next-turn banner on the Home map. Directions can be spoken (off
until switched on, on the phone only): a Bangla voice with Bangla sentences written by this app (Valhalla has no Bangla), otherwise an
English voice, otherwise text and vibration; the panel says which. "End" stops it. With "Download along the drive" chosen on the
weak-signal panel, the trip's own map tiles are fetched at the strong stretches Bartendr's plan picked, as the drive passes them.
A new version of the app waits until the person presses "Update", so it never reloads during a drive.

```bash
node frontend/tests/navigation.check.cjs motorcycle 40     # headless Chrome: Banani -> Dhaka Medical College, simulated; evidence/navigation/
node frontend/tests/navigation.check.cjs car 30
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/routing/test_navigate_proxy.py -q
cd frontend && npx vitest run src/lib/navText.test.ts src/features/today/navigation.test.ts
```

API: `POST /api/navigate/{city_id}/route` (Ferrostar's Valhalla request, car or motorbike).

## Voice alerts (Q4, 2026-10-07)

"Speak alerts and directions" (Settings, and next to turn-by-turn; off until switched on, on this phone only) speaks every alert
with the browser's own voice: crash SOS and ambulance first, then turn-by-turn, then time to leave and congestion, then the offline
mesh. The sentence spoken is the one on screen, in Bangla when the phone has a Bangla voice, in English when it has only English, and as
a vibration when it has none; Settings says which. A simulated or TEST alert is spoken with that word first, so it never sounds real.
Each alert is spoken once; "time to leave" is spoken ten minutes before the latest departure.

```bash
node frontend/tests/voice.check.cjs        # headless Chrome with a recording voice (nothing plays): SOS, a simulated drive, voice off -> evidence/voice/lines.json
cd frontend && npx vitest run src/lib/announce.test.ts
```

## Hosted app (Q5, 2026-10-07)

The app runs on the routing instance (no new server) behind Caddy: HTTPS with a Let's Encrypt certificate and a username and
password on every page. The password is kept only in `.env` (`TRAFFICTWIN_HOSTED_USER`, `TRAFFICTWIN_HOSTED_PASSWORD`; Caddy receives
only its bcrypt hash) and is given to examiners and test users directly. The routing server stays private: the app reaches it on
the instance itself, and its ports stay limited to the owner's IP. On the hosted app, route requests are limited to 30 per minute
and "Add your city" builds to 2 per visitor per day (on top of the 8-a-day limit for everyone), with a 429 that says which limit.
SUMO 1.27.1 (the laptop's version) runs there too, so the 3D City live simulation and the ambulance run work on the hosted
address: one simulation for the whole site, at most 30 simulated minutes and 10 real minutes per run, 6 starts per visitor per hour.
The package carries only the files the pages read (listed by recording the files the backend opened while every page was visited,
and the network and routes a Dhaka run gives SUMO), no keys. The password was rotated on 2026-10-07; the old one is refused. It ends with the instance (18:26 +06 on 2026-10-13, extended on 2026-10-07; a systemd timer on the instance) unless both are launched again.

```bash
infra/app/deploy.sh                        # after `aws login`: package, upload to the routing bucket (tagged), open 80/443, install the app and Caddy through SSM
HOSTED_URL=https://<ip-with-dashes>.sslip.io/ HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/hosted.check.cjs   # fresh-browser check -> evidence/hosting/
HOSTED_URL=... HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/hosted_sim.check.cjs        # a Dhaka live run, one-at-a-time, over HTTPS
HOSTED_URL=... HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/hosted_ambulance.check.cjs  # one Dhaka ambulance run over HTTPS
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/test_ratelimit.py -q
```

## RQ2 ambulance alert (2026-10-08)

In one sentence (the same sentence the Emergency page, the 3D City and the Tour show, built from `results/emergency/dhaka/rq2/summary.json`):

<!-- rq2-plain:start -->
> In simulated traffic as crowded as Dhaka's recorded morning rush on one road, warning every nearby vehicle typically got the ambulance there about 26 s sooner on a 346 s trip, though not every time; smarter traffic lights made it about 49 s later. *(Simulation, Dhaka; demand level: the Dhaka-density corridor. How we know: `docs/PAPER_MAP.md`, RQ2, and the RQ2 card on Research.)*
<!-- rq2-plain:end -->

How much time the ambulance alert saves, from light traffic to gridlock and by the share of vehicles that receive it. It is compared against three baselines:
- the siren only;
- alert plus signal preemption;
- sumo-rl's Q-learning signals (MIT).

The "why" is measured from the free space ahead of the ambulance and the queues at its signals. Results: `docs/PAPER_MAP.md` (RQ2) and the Research page. Commands: `research/ambulance_rq2/README.md`.

```bash
research/ambulance_rq2/scripts/00_reproduce_sumo_rl.sh
for s in ladder sweep rl summary; do DHAKAFLOW_NO_OBSERVATORY=1 python -m core.simulation.ambulance.study $s; done   # from the repository root
python ../research/ambulance_rq2/scripts/paper_map_rq2.py
```

## RQ1 forecasting (2026-10-08)

Baselines, the zero-shot foundation models (Chronos-Bolt, Chronos-2, TimesFM 2.5) and our trained models are compared on METR-LA, PEMS-BAY and Dhaka's recorded days (DhaTraX), at 15, 30 and 60 minutes. The step also has an unseen-city test, and measures from the data of why Dhaka differs.

- **Results and "The finding":** `docs/PAPER_MAP.md` (RQ1) and the Research page's Forecasting card.
- **Licences and reproductions:** `third_party/SOURCES.md` and `evidence/forecasting/reproduce/`.

```bash
research/forecasting_rq1/scripts/00_reproduce.sh     # each repository's own example, before use
research/forecasting_rq1/scripts/01_protocol_b.sh    # every model on METR-LA and PEMS-BAY x seeds 11/23/37, then every RQ1 stage (a few hours on a laptop CPU)
python -m core.ml.forecasting.transfer_dhaka.run summary
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest tests/forecasting/test_rq1.py -q
```

## Reality check of the hosted app (QA, 2026-10-07)

Every everyday feature is run the way a person uses it, in headless Chrome against the hosted address. There are 14 checks:
search, Add city, the whole-city route and its alternatives, the simulated drive, Leave when, recorded traffic, nearest hospitals,
ambulance reach, crash SOS, the trip pack offline, voice, the Tour, 3D City, and a place sent to Home surviving the city loading.
Each runs on a phone (390 px) and a desktop, three times on Dhaka (in Bangla) and once on Los Angeles (in English). Each run
records pass or fail, the reason, the time and a screenshot, and checks the numbers against the server's own answers.

- **First table and ranked failures:** `evidence/qa/QA_TABLE.md`.
- **Each fix:** its regression test and its before/after record are in `evidence/qa/fixes/<rank>_<name>/RESULT.md`.
- **Matrix after the fixes:** `evidence/qa/QA_TABLE_AFTER.md`.

The login comes from `.env` and is never written to any output.

```bash
export HOSTED_USER=$(grep '^TRAFFICTWIN_HOSTED_USER=' .env | cut -d= -f2-) HOSTED_PASSWORD=$(grep '^TRAFFICTWIN_HOSTED_PASSWORD=' .env | cut -d= -f2-)
node frontend/tests/qa/reality.cjs                                   # the whole matrix -> evidence/qa/runs/<feature>-<viewport>-<city>-<n>.json/.png
node frontend/tests/qa/reality.cjs F9,F11 dhaka:1,los_angeles:1 phone # some features, cities and sizes
QA_OUT=evidence/qa/fixes/<fix>/after node frontend/tests/qa/reality.cjs F1   # a fix's re-run in its own folder
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/test_hosted_package.py backend/tests/emergency -q   # what the hosted package must hold
cd frontend && npx vitest run                                        # the frontend regression tests
```

The hosted limits apply to the check as well: 6 simulation starts per visitor per hour and 30 route requests per minute. A full
matrix therefore runs in batches, and the app is restarted between them to clear its counters.

## Recorded real data ("real data without a crowd")

Real measurements from published datasets, shown with their own date and never as the present. Licences, versions
and what is used are in `third_party/SOURCES.md` ("Recorded real data").

- **DhaTraX** (Roy, Arnob, Zenodo, doi:10.5281/zenodo.22157752, CC BY 4.0): fixed cameras at three Dhaka road
  locations in April 2026. On the Dhaka home, tick **Recorded day** and choose a clock time: a route section that a
  located DhaTraX site measures is coloured by that site's 5-minute median speed, labelled "Recorded, DhaTraX,
  2026-04-20", with the authors' caveat (model output; calibration not validated by them) and the citation. Two sites
  are placed (BM at Bangla Motor, INT); the third (BS) has no stated place and is not shown on a road. A recorded
  reading never enters the "now" colours, a travel time or "Leave when?".
- **Dhaka's vehicle mix** is DhaTraX's class counts pooled over its three sites (69,083 crossings: car/microbus
  33.2 %, motorcycle 29.9 %, CNG 22.5 %, rickshaw 4.4 %, bus 4.1 %, pickup/truck 3.6 %, others 2.5 %). It is a
  detection model's output at three places, not a census. The Dhaka twin draws vehicles at these shares; each class
  is driven as the nearest SUMO class with SUMO's defaults (CNG as taxi, cycle rickshaw as bicycle). Other cities
  still have one class.
- **The researcher's own trips**: one device, listed by hand on the researcher's own machine, is exempt from the
  three-phone rule and shown as "researcher's own trips". Nothing is listed now. Each such reading shows where the
  researcher was to about 70 m and 5 minutes; it is shown only on the machine that holds the list.
- **WorldTrace** (ODbL): a Colab notebook counts its traces in each city's box. **It has not been run**, so its
  coverage of our cities is unknown.
- Not used: DRINF (planned later as a check of the mix) and the Kaggle Bangladesh Traffic Flow Dataset.

```bash
PYTHONPATH=backend python -m core.common.data.recorded.dhatrax --fetch --mix       # 12 MB from Zenodo, checksums verified; prints the pooled mix
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city dhaka           # applies the mix to the generated demand; evidence/cities/dhaka/build.json
PYTHONPATH=backend python -m core.common.data.researcher --device-id <id>        # list the researcher's own device (the browser's localStorage "tt.user")
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/city/test_city_home.py -q
# research/notebooks/WorldTrace_coverage_colab.ipynb: run on Colab, save its coverage.json as evidence/worldtrace/coverage.json
```

Evidence: `evidence/recorded/record.json`.

## Ambulance alert (simulated)

**Everything in this section is a simulation on the twin. No real vehicle, alert, call or message is involved.**

**Superseded by RQ2 (2026-10-08).** The numbers below are the first 5-seed sweep at one density, kept as a record. The app no longer
shows the "about 10 to 13 % sooner" sentence built from them. Its everyday sentence now comes from RQ2's summary, with its density level:

<!-- rq2-plain:start -->
> In simulated traffic as crowded as Dhaka's recorded morning rush on one road, warning every nearby vehicle typically got the ambulance there about 26 s sooner on a 346 s trip, though not every time; smarter traffic lights made it about 49 s later. *(Simulation, Dhaka; demand level: the Dhaka-density corridor. How we know: `docs/PAPER_MAP.md`, RQ2, and the RQ2 card on Research.)*
<!-- rq2-plain:end -->

How much earlier does a simulated ambulance reach a hospital when it announces itself, by technology (ITS-G5, C-V2X;
plain 4G is refused until its delivery ratio has a source) and by the share of vehicles that receive the alert, and
what does it cost other traffic? Arms: siren and blue light only (SUMO's bluelight device), alert to vehicles, alert
to vehicles and signals. Every arm runs with the same sublane setting (`--lateral-resolution 0.8`), so earlier results
made without it are not comparable.

```bash
PYTHONPATH=backend python -m core.simulation.twin.calibration --city dhaka --sumo-extra "--lateral-resolution 0.8"   # fit the demand to DhaTraX counts; evidence/cities/dhaka/calibration.json
PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --one --demand generated                 # one run of each arm
PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --sweep --demand generated               # the sweep on the light uncalibrated demand (about 6 minutes)
PYTHONPATH=backend python -m core.simulation.ambulance.service --city dhaka --sweep --demand calibrated              # the same on the partly calibrated demand (hours; NOT RUN yet)
DHAKAFLOW_NO_OBSERVATORY=1 PYTHONPATH=backend python -m pytest backend/tests/emergency backend/tests/signals backend/tests/networking backend/tests/city/test_calibration.py -q
```

- **Calibration is a miss, and it covers two road sections only** (one direction each, two different days treated as
  one hour, 07:00 to 08:00; everything else is uncalibrated). routeSampler places exactly the counted vehicles, but in
  simulation 56 % of Bangla Motor's count and 81 % of INT's pass; 20.8 % of 24 site-intervals are within GEH 5.
- **SUMO 1.27.1's bluelight device crashes on the Dhaka network** (`evidence/emergency/dhaka/sumo_bluelight_crash.json`).
  A crashed run has no result and is replaced by the next seed; every table says how many crashed. The rows therefore
  rest on the seeds that survived.
- Results so far, Dhaka, **uncalibrated generated demand**, 5 paired seeds per row, mean ± sd against the no-alert run
  of the same seed (`evidence/emergency/dhaka/results_generated.json`): with every vehicle equipped the ambulance saves
  19.6 ± 17.9 s (ITS-G5) or 23.6 ± 16.1 s (C-V2X) of a 209 s trip; with 25 % or 50 % equipped, nothing measurable;
  preemption alone saves 22.8 ± 13.2 s with C-V2X and 3.0 ± 10.6 s with ITS-G5. No result exists on the partly
  calibrated demand yet.
- **Plain 4G added 2026-10-06** (final plan item 4), same demand, seeds and arms; the ITS-G5 and C-V2X runs were not
  repeated (45 new runs, 2 crashed; `evidence/emergency/dhaka/sweep_generated_4g.log`). Its delivery ratio, 0.96, is
  the packet loss of 4 % at 60 km/h that Xu et al. 2017 measured on one test-bed LTE network in Xi'an, China, with one
  vehicle pair: **one field study, not Dhaka**. Through the network the alert has no radio range limit, so preemption
  alone reaches both junctions from 1,000 m ahead and saves 32.0 ± 12.9 s; with every vehicle equipped the alert alone
  saves 18.6 ± 12.8 s and alert with preemption 23.6 ± 22.3 s. The table under Emergency and Lab → Evidence prints the
  provenance line of every technology.
- Network parameters and their sources: `core/networking/v2x/configs/network_model.yaml`. With one-second steps the
  technologies differ by range and delivery ratio only. Reused code and its reproduction: `third_party/SOURCES.md`, "Ambulance alert phase".
- In the app: Lab → Control Room → "Ambulance alert" starts one run to watch (a viewing run, not a result); the home's
  alerts strip shows it stamped SIMULATED while it drives; Lab → Evidence has the tables.

## Offline mesh (simulated)

When there is no mobile network, a message can travel from phone to phone as vehicles meet. `research/mesh_pons/` ran
PONS 0.2.1 (MIT, unchanged; `third_party/SOURCES.md`, "Offline mesh") on a 300 s window of the Dhaka SUMO run:
17 of 277 vehicles (those present for the whole window), a 10 m radio (the ONE simulator's Bluetooth default, cited),
one 100-byte message a second with a 300 s lifetime, three routers (Epidemic, Spray and Wait, PRoPHET) × 5 seeds.
Everything is simulated on generated, uncalibrated traffic; the full report is `research/mesh_pons/RESULTS.md`.

Since 2026-10-06 the app reads those files (final plan item 2): `core/networking/mesh/results.py` builds one table per
city from `research/mesh_pons/evidence/runs/*.json` with the report's own formulas (delivery ratio, delay over
delivered messages, copies per message, overhead; mean ± sample sd over seeds), checks every run against the recorded
movement trace, and writes `results/networking/mesh/<city_id>/summary.json` and `evidence/mesh/<city_id>/results.json`
with the sha256 of every run file. `GET /api/mesh/results/{city_id}` serves it; the Offline alerts page shows the
figure and table, Lab → Evidence the table, and the alerts feed carries one SIMULATED line per city with a result.
A city without a run says "no data for this city".

```bash
PYTHONPATH=backend python -m core.networking.mesh.results --city dhaka                                       # the table from the saved runs
DHAKAFLOW_NO_OBSERVATORY=1 PYTHONPATH=backend python -m pytest backend/tests/mesh -q
cd research/mesh_pons && .venv/bin/python scripts/04_report.py                                   # RESULTS.md and SHA256SUMS from the same files
```

Reading the Dhaka numbers (delivery ratio 0.028 ± 0.009 Epidemic, 0.027 ± 0.014 Spray and Wait, 0.029 ± 0.013
PRoPHET): with 17 vehicles over a 5.8 × 5.5 km network and a 10 m radio, contacts are rare, so most messages never
meet their destination within 300 s. That is the sparse setup, not a property of Dhaka. The movement is the same in
every seed; the spread is over message draws only.

## Chronos-2 against recorded readings (backtest)

Chronos-2, zero-shot, forecasts 15, 30 and 60 minutes ahead from each series' own unbroken run of 5-minute readings
and is scored against the later recorded reading, beside persistence on the same pairs. Los Angeles: METR-LA, the 24
stations in the city's box, 21 to 27 June 2012. Dhaka: DhaTraX, sites BM and INT, one day each. Runs on a laptop CPU
in about a minute.

```bash
pip install chronos-forecasting==2.3.1                                             # no tensorflow beside it (requirements.txt)
PYTHONPATH=backend python -m core.ml.forecasting.evaluation.recorded_backtest          # results/forecasting/recorded_backtest.json
PYTHONPATH=backend python -m pytest backend/tests/forecasting/test_recorded_backtest.py -q
```

Evidence: `evidence/live_forecast/` (the output, its sha256 and the run log).

## Real recorded traffic (DhaTraX trajectory replay)

The vehicles DhaTraX's two located cameras tracked (BM, 20 Apr 2026; INT, 19 Apr 2026), replayed at their recorded
positions, speeds and classes at a chosen clock time: on the Home map under **Recorded day → Real recorded traffic**,
and in Lab → Control Room → **Real recorded traffic (3D)**. Every block is labelled "REAL · recorded traffic, DhaTraX,
<day> <time> (camera clock) — replay, not live", with the authors' caveat and each camera's coverage (62 m at BM,
89 m at INT); only those metres carry any vehicle. Our derivations are stated on screen: half-second sampling, heading,
and the latitude/longitude mapping from the authors' calibration files.

```bash
PYTHONPATH=backend python -m core.common.data.recorded.dhatrax --fetch-trajectories --build-replay   # about 1 GB from Zenodo, checksums verified, kept out of git; replay files under data/recorded/dhatrax/replay/
curl "http://127.0.0.1:8011/api/recorded/dhaka/replay?at=08:30:00&seconds=60"              # the frames the map plays
DHAKAFLOW_NO_OBSERVATORY=1 PYTHONPATH=backend python -m pytest backend/tests/city/test_city_home.py -q
```

Evidence: `evidence/recorded/trajectories.json`. The simulated twin's notice now states, per run, what its roads,
vehicle mix and demand are (`frontend/src/features/twin/notice.ts`).

## Simulated 3D twin

The selected city's SUMO simulation, shown in the browser in 3D: extruded buildings, roads, signal heads that follow
SUMO's phase state, and vehicles moving once a second. **It is a simulation.** Roads and building outlines are
OpenStreetMap geometry; the traffic is generated at random and uncalibrated, in every city, and every number on the
panel is marked SIMULATED.

```bash
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city dhaka          # frozen network + generated demand + building outlines
PYTHONPATH=backend python -m core.simulation.twin.city_pipeline --city los_angeles    # network built from OpenStreetMap + the same
DHAKAFLOW_NO_OBSERVATORY=1 PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --port 8000
# open http://127.0.0.1:8000/lab/control-room  →  "Simulated twin (3D)"; the simulation starts by itself
```

| City | Roads | Signals | Building outlines | Heights from a mapped height / storeys × 3 m / assumed 6 m | Generated vehicles (30 min) |
|---|---|---|---|---|---|
| Dhaka | 6,527 sections | 17 junctions | 20,290 | 42 / 2,684 / 17,564 | 900 |
| Los Angeles | 2,650 sections | 437 junctions | 11,119 | 10,684 / 12 / 423 | 900 |
| Berlin | no data for this city | | | | |

**Buildings appear anywhere you pan, without building the city.** They come from Overture Maps' worldwide buildings
file (ODbL; the map credits OpenStreetMap contributors and the Overture Maps Foundation). A building with a recorded
height is coloured by height. One without is drawn at an assumed height (its floor count × 3 m, or 6 m) in a single
grey-beige and the legend calls it "estimated height". In the tile measured over Dhaka about 90 % of buildings have no
recorded height; over Los Angeles about 5 %. Roads, signal heads and simulated vehicles are still drawn only for a
city that has been built. The view is kept in the page address, so a place can be linked. The comparison with
OpenFreeMap that led to this choice is in `evidence/basemap/`.

**Camera and light.** Three buttons on the twin map: a slow orbit (2.7° a second, never looking straight down), a
street-level view that rides with one simulated vehicle and faces the way it drives, and night lighting. Night is a
look only and the map says so; it is not the time in the simulation and changes no number. The speeds, limits and
colours are those of the MIT-licensed reference recorded in `third_party/SOURCES.md` (`evidence/twin/cinematic/`).

**Base map, satellite picture, roads, colours, automatic start** (`evidence/twin/realism/`).
- The street map on every page is OpenFreeMap (OpenStreetMap data, no key or account), with its own building layers
  removed so that buildings come only from Overture. The Esri tiles used before are gone: their terms require Esri
  software or a subscription (`third_party/SOURCES.md`), and a test fails if their address returns.
- "Satellite" on the twin map shows Sentinel-2 cloudless 2016 by EOX (CC BY 4.0). It is a composite of 2016 captures
  at 10 m per pixel, labelled "not live" on the map, and a blur at street level; it is shown as it is.
- Roads are drawn as wide as their lanes in the SUMO network (lane count × lane width, not a measured width), with
  dashed lane lines from zoom 16 that are drawn from the lane count, not seen in any image. Each section records where
  its lane count comes from: an OpenStreetMap `lanes` tag (Los Angeles 968 of 2,650 sections, Sylhet 265 of 4,230),
  netconvert's default for the road class, or "not recorded" (all 6,527 Dhaka sections, whose frozen network has no
  kept extract).
- Vehicle colours are decoration and carry no data; the legend says so. All vehicles are still one class.
- The twin starts a simulation when it opens and again when a run ends. It does not start after you press Stop, and
  it never replaces another city's running simulation without being asked.

```bash
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/test_live_twin.py backend/tests/city -q -m "not slow"   # map config, no Esri address, lane sources
cd frontend && npm test && npm run build                                                                          # road widths, lane lines, colours, autostart, base map style
```

**Add your city.** On the City page, type a city's name. The app looks it up in Overture Maps' places (4.69 million;
a new name takes about 50 seconds, a repeated one is instant), proposes a 4 × 4 km area you can move or resize up to
about 6.5 km, writes `config/cities/<city_id>.yaml` with a source for each value, fetches that area's roads from
OpenStreetMap and builds the network with the same pipeline as every other city. The city then appears in the city
list and runs in the simulated twin. Its traffic is generated at random and labelled simulated; it has no forecasts
and no measurements. Time zone, languages, emergency numbers, units and vehicle classes are left `null`, because the
source read does not hold them. A city whose driving side is not recorded is refused. Limits: one build at a time,
eight new cities a day, a built city is returned without any request. Tested with Sylhet, Bangladesh, which was in no
list: 4,230 road sections, 690 signalised junctions, 900 generated vehicles, built in 13 seconds after the search
(`evidence/cities/sylhet/`). This runs on the laptop only; nothing here uses AWS.

The table's building-outline columns describe the OpenStreetMap outlines the city pipeline also fetches when it builds
a city; in Dhaka 87 % of those have no mapped height either.
Dhaka's vehicles follow the DhaTraX mix (see "Recorded real data"); every other city's are one class. Evidence: `evidence/cities/<id>/build.json` (file
hashes, OSM dates, commands) and `evidence/twin/` (a screenshot per city and what was and was not checked).
Reused work is listed in `third_party/SOURCES.md`: the vehicle box shapes come from an MIT-licensed project; the
project named as the technical base has no licence, so only its ideas were used.

## The map app (Headway's frontend, 2026-10-09)

The app opens on a full-screen map: Headway's web frontend (Apache-2.0, commit `d0b994e`, the code behind maps.earth),
vendored in `frontend/map/` and pointed at our own services through adapters (`backend/app/routing/headway_adapter.py`):
- **search:** our Photon / Nominatim search, shaped as Pelias;
- **directions:** Headway's travelmux, unchanged, one container per city in front of that city's Valhalla;
- **map:** Headway's style on our map provider's tiles.

Inside its flow are our features, run by our own code (`frontend/src/maplink`, built to `/tt/maplink.js`):
- **Start:** spoken turn-by-turn in Bangla or English (Ferrostar) on the route chosen in Headway's list;
- **weak signal:** the trip is saved before it starts;
- **crash SOS:** a floating button during a trip, TEST mode, never sends or dials;
- **alerts:** ambulance and congestion banners;
- **hospitals:** the nearest ones as places with Directions.

Every other page (Emergency, Offline alerts, Add city, Settings) and Research, 3D City and the simulations are unchanged, under
`/app/` and in the map's menu. Old links (`/emergency`, `/lab/...`) redirect there.
What was changed in Headway: `frontend/map/UPSTREAM.md`. Licences: `third_party/SOURCES.md`, "Map app (Headway)".

```bash
# Headway's own build and tests, reproduced first, unchanged (Node 24, which Headway's engines allow)
cd frontend/map && npx -y -p node@24 -- corepack yarn install --frozen-lockfile && npx -y -p node@24 -- corepack yarn build && npx -y -p node@24 -- corepack yarn test
# our shared code for the map app, then the map app, then the React pages (/app/)
cd frontend && npx vite build --config vite.maplink.config.ts && (cd map && npx -y -p node@24 -- corepack yarn build) && npx vite build
# directions: one travelmux per city (pinned image), each in front of that city's Valhalla; the app finds it in TRAFFICTWIN_TRAVELMUX_URL_<CITY>
docker run -d --name travelmux-dhaka -p 127.0.0.1:9101:8000 ghcr.io/headwaymaps/travelmux@sha256:7b57fa0443d53d06ec28b4aef66e749a96de3a86a84cddcb94251cbb16f9a672 "$TRAFFICTWIN_VALHALLA_URL_DHAKA"
# tests: the adapters, Headway's suite with our tests, the five tasks and the map-flow QA (hosted credentials from .env, never written)
DHAKAFLOW_NO_OBSERVATORY=1 python -m pytest backend/tests/routing/test_headway_adapter.py -q
cd frontend/map && npx -y -p node@24 -- corepack yarn test
HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/qa/compare.cjs apps=google,headway,ours_map out=ours_after   # evidence/design/compare/
HOSTED_USER=... HOSTED_PASSWORD=... node frontend/tests/qa/mapflow.cjs viewports=phone,desktop cities=dhaka,los_angeles  # evidence/qa/mapflow/
```

The gap analysis against Google Maps and maps.earth, before and after: `evidence/design/compare/GAPS.md`.

## Tests

```bash
PYTHONPATH=backend python -m pytest -q --ignore=backend/tests/test_frontend_e2e.py     # 592 passed, 5 skipped, no key, no network
cd frontend && npx vitest run                                                          # 27 passed
```

The research tests pin what matters: fresh inference per request with checkpoint verification, frozen protocols, a real
SUMO run, the model gate, and an anti-hardcode test that fails when an input stops changing an output.

## Documentation

| Document | Purpose |
|---|---|
| `docs/MASTER_PLAN.md` | the workflow, all features, all 55 papers with official code and licence, build order |
| `docs/TRAFFIC_PHASES.md` | one paper per phase, reproduction target, the web feature it delivers |
| `docs/TRAFFIC_SOTA_PAPERS.md` | the prediction catalogue in tiers and the regime-transition gap |
| `docs/TRAFFIC_FULL_SCOPE.md` | the other six pillars of road traffic (sense, estimate, detect, control, advise, verify) |
| `docs/EXPERIMENT_PROTOCOL.md` | the frozen research contract and metrics |
| `docs/GRAVEYARD.md` | what was tried and dropped, with the reason |
| `results/forecasting/benchmark_floors.md` | the floors and the protocol check against the papers |

## Limitations

- Protocol B is three seeds on all 207 METR-LA roads; PEMS-BAY has one seed with GWNet and STID only, and PEMS04 is
  pending, so the family claim rests on one city.
- Chronos-2 and TimesFM 2.5 are evaluated under Protocol B only (one block, one seed); their Protocol A rows on the full
  test split, and Moirai / Time-MoE, are pending. TimesFM's outages are forward-filled inside the window (it takes dense input).
- OpenCity's pre-training corpus includes METR-LA and PEMS-BAY, so its numbers there are not zero-shot; only the four
  held-out cities are reported.
- Dhaka has no observed traffic data yet. Results on a Dhaka corridor recording (a forecast backtest, error floors,
  a forecast scoreboard and twenty routing-chain runs) were withdrawn on 2026-10-05 because the recording was derived
  from Google Routes results, which Google's terms do not allow to be stored or used to test models. The Dhaka twin's
  demand scale (0.584) was calibrated on the same data; it is now labelled synthetic what-if, uncalibrated.
- The closed-loop twin shows a −1.83 % vehicle-hours ceiling on one corridor; gains must come from coverage, not accuracy.
- No sign-in yet; one identity per browser.

## Planned work

- [x] Protocol A: Graph WaveNet, STID, STAEformer within 2 %; OpenCity exact on held-out cities; Chronos-Bolt
- [x] Protocol B: floors, XGBoost, Chronos-Bolt, GWNet, STID, STAEformer on the 80-node block; the Onset page
- [x] P1 DCRNN: 2.67 / 3.08 / 3.57 against 2.77 / 3.15 / 3.60, on AWS with the official config
- [x] P4 MegaCRN: 2.63 / 3.02 / 3.48 against 2.52 / 2.93 / 3.38; best onset detector so far (71%)
- [x] P3 D2STGNN: 2.56 / 2.91 / 3.36 against 2.56 / 2.90 / 3.35, an exact reproduction; best congested error of the table
- [x] P7a PatchSTG released weights reproduced on LargeST-SD (-0.3 % MAE); SD training job on AWS running
- [ ] P5–P7 STD-MAE (job prepared), HimNet, BigST, STGformer; PatchSTG GBA / GLA / CA rows
- [x] P8a regime-aware conformal intervals (MAPIE) on every Protocol B model, three calibrators, the transition result
- [x] P8b departure advice on a sensor corridor from the calibrated half-widths
- [x] P9a Chronos-2 (univariate and multivariate) and TimesFM 2.5 zero-shot under Protocol B with conformal rows
- [ ] P9b Moirai (needs its own environment on the GPU machine) and Time-MoE (upstream generation code broken against current transformers; see `docs/GRAVEYARD.md`); Protocol A rows on the full test split
- [x] P10 regime-aware alerts: roads about to tip at a moment, watches, hysteresis, one alert per episode
- [x] P12a serving: every trained checkpoint on the forecast map with fresh inference and its hash
- [ ] P11 cross-city to Dhaka with UniST and OpenCity · P12b twin re-run with the new forecaster
- [ ] Large-scale run: best supervised and best foundation model over all 8,600 LargeST sensors and thirty live cities for fourteen days; forecasts and regime labels published as Parquet with a report
- [x] Probes: the phone as the sensor (signature feature S1), snapped with Amazon Location, H3 cells, relational tables
- [x] Q1 Sparse sensing: ImputeFormer under its paper's 25 % point-missing protocol; mean fill 7.51 vs the paper's 7.52 validates the setup; 2.42 MAE after 60 laptop epochs against linear 2.48, last 2.93, the paper's 1.80 at 300 × 300 batches
- [ ] Other pillars of road traffic (imputation, incident detection, signal control) per `docs/TRAFFIC_FULL_SCOPE.md`

## Citation

```bibtex
@misc{traffictwin-2026,
  title  = {TrafficTwin: foundation models versus purpose-trained graph networks for road traffic, under aggregate and regime-stratified protocols},
  author = {Jannatul Ferdouse},
  year   = {2026},
  note   = {Islamic University of Technology; official implementations reproduced; code and evidence at this repository}
}
@article{yanespulido2026tsfm,
  title  = {Time Series Foundation Models as Strong Baselines in Transportation},
  author = {Yanes-Pulido, Javier and Rodrigues, Filipe},
  year   = {2026}, eprint = {2602.24238}, archivePrefix = {arXiv}
}
@inproceedings{li2018dcrnn,
  title  = {Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting},
  author = {Li, Yaguang and Yu, Rose and Shahabi, Cyrus and Liu, Yan},
  booktitle = {ICLR}, year = {2018}
}
```

Licence: MIT (see `LICENSE`). Official research code is pinned and fetched, never vendored; licences in `docs/THIRD_PARTY_LICENSES.md`.
