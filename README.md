# TrafficTwin

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

## Contents

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
| D2STGNN | METR-LA | 2.56 / 2.91 / 3.36 | 2.56 / 2.90 / 3.35 | +0.1 / +0.5 / +0.1 % |
| MegaCRN | METR-LA | 2.63 / 3.02 / 3.48 | 2.52 / 2.93 / 3.38 | +4.4 / +3.0 / +2.8 % |
| Graph WaveNet | METR-LA | 2.72 / 3.11 / 3.59 | 2.69 / 3.07 / 3.53 | +1.1 / +1.3 / +1.8 % |
| Graph WaveNet | PEMS-BAY | 1.31 / 1.64 / 1.95 | 1.30 / 1.63 / 1.95 | +0.6 / +0.5 / −0.2 % |
| STID | METR-LA | 2.82 / 3.21 / 3.59 | 2.82 / 3.19 / 3.55 | 0.0 / +0.7 / +1.2 % |
| STID | PEMS-BAY | 1.32 / 1.64 / 1.92 | 1.31 / 1.64 / 1.91 | +0.6 / 0.0 / +0.5 % |
| STAEformer | METR-LA | 2.67 / 2.98 / 3.35 | 2.65 / 2.97 / 3.34 | +0.9 / +0.5 / +0.3 % |
| OpenCity-plus zero-shot | PEMS07M (held out of its pre-training) | 4.50 (12-step) | 4.50 | 0.0 % |
| OpenCity-plus zero-shot | TrafficSH (held out) | 0.55 | 0.55 | 0.0 % |

MegaCRN sits 4.4 % above its authors' README at 15 min and within 3 % at 30 and 60; the authors' number comes from their own
training code, ours from the BasicTS fair-comparison config, which is the comparison the harness paper reports.
Protocol check: our historical-average floor on METR-LA is 4.19 MAE against the DCRNN paper's 4.16 (0.7 %), so the
split, masking and metric are the papers' own. Every row above was trained or evaluated on AWS (g4dn / g5, Tesla T4)
with the official config unmodified except epochs and horizons; checkpoint SHA-256 and the log path sit beside each
row in `results/forecasting/trained_results.csv`.

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
LargeST-SD (716) and GLA (3,834), and the project's own recorded Dhaka corridor (5-minute bins, no training on
Google-Routes history by rule).

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

| Page | What it shows | Backed by |
|---|---|---|
| Forecast map | every sensor of a dataset at a chosen moment, 15 / 30 / 60 min ahead, model selector; fresh inference per request from a hash-verified checkpoint | `GET /api/forecast-map/{dataset}` |
| Leaderboard | each reproduced paper, our number, the published number, the gap | `results/forecasting/trained_results.csv` |
| City | live roads for any city through Amazon Location, labelled live / typical / recorded with data age | `backend/app/data/live_providers/` |
| Train | pick model and dataset, launch on AWS, watch the log, the result registers itself | `POST /api/train` |
| Twin | the forecast fed into SUMO on the frozen Dhaka corridor; vehicle-hours with and without advice | `backend/app/twin/`, `results/current/closed_loop/` |
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
| METR-LA, PEMS-BAY | `liyaguang/DCRNN` release files, fetched by `app.data` | the canonical files, protocol validated |
| PEMS03/04/07/08, LargeST | BasicTS and LargeST releases | LargeST data is CC BY-NC 4.0 |
| Trained checkpoints | S3 and `results/forecasting/checkpoints/` | SHA-256 recorded per row |
| Foundation weights | Hugging Face: OpenCity-plus, Chronos, TimesFM | used as released |
| Official code | pinned in `upstream/UPSTREAM_PINS.yaml`, fetched into an external workspace, never committed, never modified | licence read at pin time |

## Repository layout

```
backend/app/forecasting/        training (BasicTS adapter, AWS launcher), evaluation (protocols A and B), live, opencity, serving
backend/app/data/               datasets, live providers (Amazon Location first), recorder
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
python -m app.forecasting.training.aws_train --launch --model GWNet --dataset METR-LA   # then --collect
# Protocol B, every model with a checkpoint or released weights
python -m app.forecasting.evaluation.evaluate_models --all
```

Each run writes its row, log path and checkpoint hash into `results/forecasting/`; the leaderboard page reads that file.

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
- The learned model does not yet beat persistence on the recorded Dhaka corridor at 15 minutes; the corridor has six
  days of data. Reported, not hidden.
- The closed-loop twin shows a −1.83 % vehicle-hours ceiling on one corridor; gains must come from coverage, not accuracy.
- No sign-in yet; one identity per browser.

## Planned work

- [x] Protocol A: Graph WaveNet, STID, STAEformer within 2 %; OpenCity exact on held-out cities; Chronos-Bolt
- [x] Protocol B: floors, XGBoost, Chronos-Bolt, GWNet, STID, STAEformer on the 80-node block; the Onset page
- [x] P1 DCRNN: 2.67 / 3.08 / 3.57 against 2.77 / 3.15 / 3.60, on AWS with the official config
- [x] P4 MegaCRN: 2.63 / 3.02 / 3.48 against 2.52 / 2.93 / 3.38; best onset detector so far (71%)
- [x] P3 D2STGNN: 2.56 / 2.91 / 3.36 against 2.56 / 2.90 / 3.35, an exact reproduction; best congested error of the table
- [ ] P5–P7 STD-MAE (job prepared), HimNet, BigST, PatchSTG, STGformer
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
