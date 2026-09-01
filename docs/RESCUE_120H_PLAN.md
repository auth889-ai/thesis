# DhakaFlow 120-Hour Rescue Plan

Current date: 2026-09-01. If the deadline is five calendar days from now, the
execution window is 2026-09-01 through 2026-09-06.

This repo is already close to a defensible thesis project. The rescue goal is
not to add every possible ML/DL/RL/NLP feature. The goal is to make one complete
paper-grounded chain work end to end:

```
traffic video / live state
  -> vehicle detection + tracking
  -> physical traffic observation
  -> synchronized SUMO twin
  -> 5/15/30 minute graph forecast
  -> route + signal candidates
  -> network-wide counterfactual guard
  -> decision: act or honest no-action
  -> reproducible report + demo
```

## Grade-Critical Rule

Never claim real-world deployment. Claim a decision-support prototype validated
inside a calibrated SUMO digital twin, with real video/API inputs and honest
domain labels.

## Papers To Build Around

| Area | Paper / project | Use in this repo |
|---|---|---|
| Detection | RT-DETR, CVPR 2024 | Vehicle detector for Dhaka traffic classes. Keep `artifacts/p1_winner` as the primary detector if its evidence files are present. |
| Tracking | ByteTrack, ECCV 2022 | Replace toy IoU IDs on the app path; tracking must feed queue/flow/stopped evidence. |
| Bangladeshi vehicle data | Poribohon-BD, BNVD | Ground the local vehicle taxonomy: rickshaw, CNG, easybike, bus, truck, etc. |
| Simulation | SUMO, ITSC 2018 | Core digital twin and counterfactual engine. Use save/load state and paired seeds. |
| Digital twin sync | Geneva Motorway DT-GM, AEI 2023 | Pattern for ingesting measured flow/speed and continuously calibrating SUMO. |
| Forecasting | DCRNN, ICLR 2018 | Directed graph diffusion baseline. |
| Forecasting | Graph WaveNet, IJCAI 2019 | Main 5/15/30 min traffic forecast candidate. |
| Forecasting | STID, CIKM 2022 | Fast, strong sanity baseline. |
| Forecasting | STAEformer, CIKM 2023 | Transformer comparison if time remains. |
| Benchmarking | BasicTS, TKDE 2024 | Fair training/eval harness and common metrics. |
| Signal control | Varaiya max-pressure, TR-C 2013 | Strong non-RL baseline; must be correct before claiming RL. |
| Signal control benchmark | RESCO, NeurIPS Datasets 2021 | Evaluation protocol reference for realistic SUMO signal-control comparisons. |
| Dynamic routing | SUMO DUA/rerouting docs | DUE vs DSO and bounded rerouting compliance ladder. |
| Networking | Eclipse MOSAIC | V2X/actuation latency gate only; do not let it block the main thesis. |
| NLP / LLM | Incident text summarization | Use only as an explanation/report layer, not as the traffic controller. |

## Three-Person Split

| Person | Owns | Done means |
|---|---|---|
| A: Sensing + demo | App path, RT-DETR/ByteTrack, state estimator, UI/report wording | Any video produces a physical observation and honest label. |
| B: Twin + routing/control | SUMO sync, paired counterfactuals, max-pressure, dynamic routing | Same-state multi-seed decision accepts only network-wide improvements. |
| C: Forecasting + evidence | BasicTS exports, GWNet/STID/DCRNN runs, tables, reproduce docs | Forecast metrics and every claim trace to artifacts. |

## 120-Hour Execution Order

### H+0 to H+12: Freeze The Truth

1. Run the local smoke tests and gate commands that do not need cloud.
2. Regenerate `docs/RESULTS_MATRIX.md`.
3. Mark every missing artifact as `NOT_COMPLETED`, not `PENDING_SUCCESS`.
4. Remove or relabel claims that imply deployment or live Dhaka validation.

Deliverable: a clean status board with no fake success.

### H+12 to H+36: Make Real-State Solid

1. Ensure `scripts/dhakaflow_run.py` is the main demo command.
2. Confirm RT-DETR detections feed ByteTrack on the app path.
3. Classify stationary-start congestion from absolute evidence: occupancy,
   queue persistence, stopped tracks, and flow, not only relative pixel speed.
4. Output `TrafficObservation` JSON with camera, frame count, stride, classes,
   queue proxy, flow proxy, stopped ratio, and confidence.

Deliverable: `REAL_STATE_PASS.json`.

### H+36 to H+60: Make The Twin Honest

1. Use the real observation to seed or scale the SUMO demand.
2. Consume calibration scale in the actual route/control scenarios.
3. Constrain the selected signal/intervention area to the observed corridor.
4. Use paired seeds and saved state for each candidate.

Deliverable: `TWIN_SYNC_PASS.json` and `COUNTERFACTUAL_PASS.json`.

### H+60 to H+78: Forecasting Gate

1. Run STID first because it is fast and gives a strong floor.
2. Run Graph WaveNet next as the main graph forecast.
3. Run DCRNN if time allows; run STAEformer only after GWNet evidence exists.
4. Log availability fraction. A forecast feature that is zero during the
   decision window is a failed forecast-in-loop claim.

Deliverable: `FORECAST_PASS.json` with MAE/RMSE at 5, 15, and 30 minutes.

### H+78 to H+96: Routing + Signals

1. Fix signal action semantics before training or presenting RL.
2. Compare fixed-time, actuated, and max-pressure.
3. Add route candidates with bounded compliance: 0%, 10%, 20%, 40%.
4. Accept an intervention only if network delay/stopped/arrivals improve across
   paired seeds. Local queue relief alone is not success.

Deliverable: `SIGNAL_CONTROL_PASS.json`, `DYNAMIC_ROUTING_PASS.json`,
`NETWORK_GUARD_PASS.json`.

### H+96 to H+108: Optional RL / NLP

1. RL is optional. If FA-MAPPO is not already running, do not gamble the grade on
   late training.
2. Use MAPPO only as an experimental arm against max-pressure, not the core
   contribution.
3. NLP/LLM should summarize road incident text and generate explanations from
   grounded artifacts only.

Deliverable: honest experimental section.

### H+108 to H+120: Presentation Freeze

1. One command runs the demo.
2. One table lists every metric and artifact path.
3. One limitations section states simulated-domain limits, domain shift, and
   missing real signal-control authority.
4. Three dry runs with a known video and one live/reference input.

Deliverable: final reproducible demo and slides.

## Must-Not-Do List

1. Do not claim vehicles will move faster on real Dhaka roads unless you have a
   real deployment or authority data.
2. Do not attach an old DUE/DSO result to every uploaded video as if it was
   freshly computed.
3. Do not report local queue reduction as success when network metrics worsen.
4. Do not use Road511 US data as Dhaka validation. It is provider integration and
   domain-shift evidence only.
5. Do not start a new huge model in the final 36 hours unless the baseline gates
   are already passing.

## Minimum Passing Story

DhakaFlow is a paper-grounded traffic decision-support system. It takes a real
traffic video or API state, extracts vehicle-level traffic evidence, synchronizes
a SUMO digital twin of the road network, forecasts near-future traffic on a graph,
tests route and signal candidates from the same saved simulation state, rejects
local-only improvements that hurt the network, and outputs an auditable
act/no-action decision with reproducible artifacts.

