# Experiment protocol

The research questions are frozen; a new repository never adds one.

| | Question | Phases that answer it | Primary evidence |
|---|---|---|---|
| RQ1 | Does lower traffic-forecasting error translate into better routing and arrival outcomes? | 4, 11, 12 | forecast MAE per model × routing arms in the twin, paired over unseen days |
| RQ2 | Does calibrated uncertainty improve arrival reliability compared with point-estimate routing? | 7, 11 | coverage and width of intervals; on-time rate of interval-based vs point-based departure |
| RQ3 | How much sensor/probe coverage is required before forecast-aware decisions provide benefit? | 8, 9, 11 | benefit vs covered share of the route, swept |
| RQ4 | How well do zero-shot / few-shot traffic models adapt to a data-poor city? | 5 | skill vs persistence and local baselines as a function of days of local data |
| RQ5 | How robust are routing/control decisions under V2X latency, loss and penetration? | 15 | outcome vs impairment sweeps |
| RQ6 | Does forecast-aware closed-loop routing/control outperform reactive/static baselines in the digital twin? | 12, 13, 14 | oracle-first protocol: baseline · reactive · oracle · learned · shuffled control |

## Rules

1. Chronological splits; the test days are never seen in training or model selection.
2. Persistence and historical average are always reported next to every learned model.
3. A number reaches a page only from a run file under `results/`; nothing is typed in; published scores are quoted
   as "published" and never presented as ours.
4. Negative results are kept and shown (the current one: on the frozen corridor the learned forecast does not beat
   no advice, and the perfect-information ceiling is about 2 %).
5. Every run records the exact command, the source commit, the checkpoint hash, the seed and the environment.
6. A model drives advice only after its validation gate on the city's own data; a provider is never a training target.
7. Recorded, simulated and emulated data are labelled as such wherever they appear.

## What a forecasting run must record (Phase 4 onward)

```text
dataset · split (train/val/test dates) · normalisation · hyperparameters · seed · epoch · checkpoint path and SHA-256
parameter count · MAE · RMSE · MAPE · per-horizon metrics (15/30/60 min) · training duration · compute (instance, cost)
source repository and commit SHA · harness version · command line
```

## What a routing / twin run must record (Phases 11–14)

```text
network and demand files with hashes · saved-state fork id · arms run · seeds · per-arm vehicle-hours, waiting, stops,
queues, spillback, throughput, teleports · paired differences with 95 % CI over unseen days · the stress calibration
(travel-time index ≥ 1.3, standing jams, ≤ 1 % lost vehicles) · command line · provenance.json
```

## What an uncertainty run must record (Phase 7)

```text
method · calibration set · nominal coverage · empirical coverage (overall and per horizon) · mean interval width ·
drift over time · the decision rule derived from it
```

## Canonical commands

- Closed loop: `make canonical` → `research/closed_loop/canonical.py --execute --stage oracle` (see `EXPERIMENTS.md`).
- Forecasting: `experiments/train.py` through the BasicTS harness (path fixed; never renamed) and
  `backend/app/forecasting/evaluation/evaluate_models.py`.
- Every phase adds its command here when it produces a result.

## Where evidence lives

`results/current/**` (promoted runs), `results/forecasting/**` (model cards), `results/live/**` (the app's own
records: outcomes, audit), and the lab pages that read them. `docs/METHODOLOGY.md` keeps the scientific core of the
closed-loop protocol; this file is the contract every later phase extends.
