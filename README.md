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

Models run so far: Graph WaveNet, STID, STAEformer (official BasicTS configs, trained on AWS GPUs), OpenCity-plus
(released weights, authors' commands), Chronos-Bolt (released weights). Nothing is re-implemented.

## Findings

Scores are MAE in mph on held-out test windows (lower is better). Protocol A numbers are compared with the published
rows of the same model on the same dataset; Protocol B numbers have no published counterpart, which is the point.

### Protocol A — reproduction (the papers' split)

| Model | Dataset | Ours 15 / 30 / 60 min | Published | Gap |
|---|---|---|---|---|
| Graph WaveNet | METR-LA | 2.72 / 3.11 / 3.59 | 2.69 / 3.07 / 3.53 | +1.1 / +1.3 / +1.8 % |
| Graph WaveNet | PEMS-BAY | 1.31 / 1.64 / 1.95 | 1.30 / 1.63 / 1.95 | +0.6 / +0.5 / −0.2 % |
| STID | METR-LA | 2.82 / 3.21 / 3.59 | 2.82 / 3.19 / 3.55 | 0.0 / +0.7 / +1.2 % |
| STID | PEMS-BAY | 1.32 / 1.64 / 1.92 | 1.31 / 1.64 / 1.91 | +0.6 / 0.0 / +0.5 % |
| STAEformer | METR-LA | 2.67 / 2.98 / 3.35 | 2.65 / 2.97 / 3.34 | +0.9 / +0.5 / +0.3 % |
| OpenCity-plus zero-shot | PEMS07M (held out of its pre-training) | 4.50 (12-step) | 4.50 | 0.0 % |
| OpenCity-plus zero-shot | TrafficSH (held out) | 0.55 | 0.55 | 0.0 % |

Protocol check: our historical-average floor on METR-LA is 4.19 MAE against the DCRNN paper's 4.16 (0.7 %), so the
split, masking and metric are the papers' own. Every row above was trained or evaluated on AWS (g4dn / g5, Tesla T4)
with the official config unmodified except epochs and horizons; checkpoint SHA-256 and the log path sit beside each
row in `results/forecasting/trained_results.csv`.

Reading: the pipeline reproduces the field. That is the precondition for Protocol B meaning anything.

### Protocol B — regime-stratified (80-node METR-LA block, 120 contiguous test windows, 96-step context)

Congestion is below 0.6 × the node's free-flow speed (85th percentile of its training values). Onset is the first
window of a congested run. Sensor outages (0.0) are excluded from every metric.

| Model | MAE@15 all | MAE@15 congested | Onset detection rate | Mean lead (min) |
|---|---|---|---|---|
| STAEformer (trained) | 2.93 | 5.49 | 0.66 | 50.8 |
| Graph WaveNet (trained) | 3.04 | 5.88 | 0.58 | 48.7 |
| STID (trained) | 3.13 | 6.61 | 0.52 | 48.9 |
| XGBoost | 3.97 | 8.61 | 0.20 | 25.7 |
| Persistence | 4.00 | 7.22 | 0.03 | 60.0 |
| Chronos-Bolt zero-shot | 4.26 | 7.94 | 0.32 | 56.4 |
| Historical average | 5.59 | 19.68 | 0.14 | 48.1 |

Reading: on the aggregate column the trained models are within 0.2 mph of each other; in congestion the spread opens
to 1.1 mph and against the zero-shot model to 2.5 mph. STAEformer flags two onsets in three, Chronos-Bolt one in
three, persistence almost none. Chronos-Bolt does not beat persistence on aggregate MAE at 15 minutes (a negative
result, kept) yet detects ten times more onsets than persistence. Neither protocol alone tells the story. DCRNN joins
this table when its reproduction lands; the page `/lab/models` → Onset serves it from the run file.

### Calibrated intervals per regime (METR-LA, 90 % level, calibrated on the validation block, scored on the test block)

Three MAPIE split-conformal calibrators on each model's point forecast: one global quantile; one per regime observed at
prediction time; one per regime the model itself predicts at the horizon. Coverage at 15 minutes, by where the truth landed.

| Model | Calibrator | All | Free flow | Congested | Transition into congestion |
|---|---|---|---|---|---|
| STAEformer | global | 0.89 | 0.91 | 0.77 | 0.39 |
| STAEformer | regime-aware | 0.91 | 0.91 | 0.88 | 0.33 |
| STAEformer | predicted-regime | 0.90 | 0.90 | 0.90 | 0.50 |
| Graph WaveNet | global | 0.89 | 0.92 | 0.75 | 0.33 |
| Graph WaveNet | predicted-regime | 0.90 | 0.90 | 0.88 | 0.41 |
| Chronos-Bolt | global | 0.88 | 0.92 | 0.68 | 0.21 |
| Chronos-Bolt | predicted-regime | 0.88 | 0.89 | 0.83 | 0.20 |
| Persistence | global | 0.89 | 0.92 | 0.74 | 0.20 |

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

Pending pages, each tied to a phase in the master plan: calibrated bands and departure advice (P8),
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

- Protocol B has been run on an 80-node METR-LA subsample with 120 consecutive windows, one seed; PEMS-BAY and
  more seeds are next, so the onset numbers are a first block, not a final estimate.
- Chronos-Bolt was evaluated, not Chronos-2; the baseline paper's model is the next zero-shot run.
- OpenCity's pre-training corpus includes METR-LA and PEMS-BAY, so its numbers there are not zero-shot; only the four
  held-out cities are reported.
- The learned model does not yet beat persistence on the recorded Dhaka corridor at 15 minutes; the corridor has six
  days of data. Reported, not hidden.
- The closed-loop twin shows a −1.83 % vehicle-hours ceiling on one corridor; gains must come from coverage, not accuracy.
- No sign-in yet; one identity per browser.

## Planned work

- [x] Protocol A: Graph WaveNet, STID, STAEformer within 2 %; OpenCity exact on held-out cities; Chronos-Bolt
- [x] Protocol B: floors, XGBoost, Chronos-Bolt, GWNet, STID, STAEformer on the 80-node block; the Onset page
- [ ] P1 DCRNN (official BasicTS config), training on AWS
- [ ] P3–P7 D2STGNN, MegaCRN, STD-MAE, HimNet, BigST, PatchSTG, STGformer
- [x] P8a regime-aware conformal intervals (MAPIE) on every Protocol B model, three calibrators, the transition result
- [ ] P8b departure advice from the calibrated lower bound
- [ ] P9 Chronos-2, TimesFM, Moirai, Time-MoE zero-shot; reproduce the baseline paper's numbers
- [ ] P10–P12 alerts, cross-city to Dhaka with UniST and OpenCity, ONNX serving and twin re-run
- [ ] Large-scale run: best supervised and best foundation model over all 8,600 LargeST sensors and thirty live cities for fourteen days; forecasts and regime labels published as Parquet with a report
- [ ] Other pillars of road traffic (imputation, incident detection, signal control, map matching) per `docs/TRAFFIC_FULL_SCOPE.md`

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
