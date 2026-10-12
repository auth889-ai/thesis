# AID: automatic incident detection inside SUMO (step J, 2026-10-11)

**Goal.** Detect a stopped vehicle on the Dhaka corridor from roadside loop detectors alone, every 30 s, with a learned model against the
classic California algorithm; then close the loop: a detection sends the V2X warning and reroutes the warned cars. Our own design;
everything below is SIMULATION on generated traffic fitted to two counted sections.

## Pipeline

```
corridor net + Dhaka-density demand (RQ2b)        core/simulation/ambulance/service.scenario
        │
        ▼
E1 loops every 300 m on the ambulance route        core/simulation/aid/stations.py  (11 stations, 10 pairs, one loop per lane, period 30 s)
        │
        ▼  SUMO 1.27.1 + TraCI, 1 h per seed
incidents: a vehicle stopped in its lane 3-5 min   core/simulation/aid/run.py  (random times/places from the seed; label 1 while active on that pair)
        │
        ▼  one row per pair per 30 s
rows: up/down speed, occupancy, flow, OCCDF, OCCRDF, DOCCTD, …   data/aid/train.csv (seeds 1-5, even pairs)  data/aid/test.csv (seeds 11-15, odd pairs)
        │                                   │
        ▼                                   ▼
California #7 (thresholds calibrated)      HistGradientBoosting (threshold chosen under a false-alarm cap)      scripts/aid/aid.py train
        │                                   │
        ▼  offline metrics on the test seeds and unseen pairs                                                   scripts/aid/aid.py eval
detection rate · time-to-detect · false alarms per pair-hour
        │
        ▼  closed loop, live in SUMO: detection → V2X warning (core/networking/v2x/model.py) → step-A rerouting (adaptTraveltime + rerouteTraveltime)
trip time with vs without, same seeds                                                                            evidence/aid/summary.json
```

## Upstream

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| California Algorithm #7 | Payne & Tignor, TRR 682, 1978 | the paper | © TRB | Decision tree with states reimplemented in `core/simulation/aid/california7.py`; thresholds calibrated on our training seeds (grid search), not the paper's freeway values |
| scikit-learn | pip | 1.7.2 | BSD-3 | `HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, class_weight="balanced")`, unchanged |
| Eclipse SUMO + TraCI | pip | 1.27.1 | EPL-2.0 | E1 loops (`inductionloop.getLastInterval*`), the stop (`setSpeed`, `setLaneChangeMode`), rerouting (`edge.adaptTraveltime`, `vehicle.rerouteTraveltime`) |
| the thesis's V2X delivery model | `core/networking/v2x/model.py` | ours | — | the warning from the pair's downstream station to equipped cars in range |

## Files

- `core/simulation/aid/stations.py`: station placement, loop file, interval reading, the pair row (`FEATURES`).
- `core/simulation/aid/california7.py`: the baseline state machine.
- `core/simulation/aid/run.py`: one run (incidents, rows, live detector, closed loop, trip cohort).
- `scripts/aid/aid.py`: `train`, `eval`, `gui`; metrics; threshold and California calibration.
- `tests/aid/test_aid.py`: stations, the row, the state machine, the plan, the metrics.
- Outputs: `data/aid/{train,test}.csv`, `results/aid/{model.joblib,train_summary.json,eval_summary.json}`, `evidence/aid/summary.json`.

## Commands

    make aid-train                 # about 1 min
    make aid-eval                  # about 2 min
    make aid-gui ARGS="--seed 12"  # LIVE in sumo-gui: incident red, warned yellow, rerouted blue, a label with detections / warned / rerouted


Added 2026-10-11 afternoon (owner's request; `docs/proposals.md`):

    make aid-gui ARGS="--seed 12"                  # station pairs drawn along the road: GREEN normal, YELLOW tentative, RED alarm; counter of detections and false alarms
    make aid-train ARGS="--sensor camera"          # J2: cameras at the 2 signalised junctions (IncidentNet-style sensing) -> data/aid/camera_train.csv, results/aid/camera_model.joblib
    make aid-eval ARGS="--sensor camera"           # J2: held-out seeds, offline -> evidence/aid/camera_summary.json
    make aid-frontier                              # J1: detection rate vs false alarms over every threshold, x0.78 (saved rows) and x0.3 (new runs) -> evidence/aid/frontier/

## Results (`evidence/aid/summary.json`, sha256 `eedd6fef…`; test seeds 11-15, incidents on pairs never seen in training, 4 per seed)

| Detector | Detection rate | Time to detect | False alarms per pair-hour |
|---|---|---|---|
| Model, threshold 0.9 (chosen on the training seeds for ≤ 0.5 false alarms per pair-hour) | **0.0** | — | 0.24 |
| Model, threshold 0.5 | 0.2 | 98 s | 3.67 |
| California #7 (T1 12, T2 0.2, T3 0.3, calibrated on the training seeds) | **0.0** | — | 0.26 |

Closed loop (model, threshold 0.9), mean trip time of vehicles departing after the 10-minute warm-up, paired over the 5 seeds:
without 1 012.8 s, with 1 017.1 s (+4.2 ± 9.4 s; 0 of 5 seeds better); 0.2 detections, 17 cars warned and 0.6 rerouted per run.

On the training seeds the model detects 5 of 5 incidents per seed; California #7 detects 10 %.

**The training data is clean:** 6 000 rows per split, 163 / 160 positives (2.7 %); no constant feature; no feature equals the label
or is derived from the incident plan (`train_summary.json` `audit`).

## Frontier and the camera sensor (added 2026-10-11; `evidence/aid/frontier/frontier.json`, sha256 `0902fba9…`; `evidence/aid/camera_summary.json`, sha256 `b1afeee9…`)

Held-out seeds 11-15, 20 incidents on the unseen station pairs, detections and false alarms pooled over the seeds; the loop model,
California #7 and the camera model are all fixed at Dhaka density (never retrained for x0.3). False alarms are per **sensor-pair-hour**:
the loops have 10 pairs on the corridor, the cameras 1, so per corridor-hour the loops' figure is 10x the number shown.

| Density | Detector | DR at FA <= 0.5/pair-h | DR at ~3/pair-h | best DR (its FA) |
|---|---|---|---|---|
| x0.78 (Dhaka) | loop model | 0.00 (thr 0.9) | 0.15 (thr 0.6, FA 3.0) | 0.75 (FA 11.1, thr 0.02) |
| x0.78 | California #7 (336 settings) | 0.05 | 0.10 | 0.15 (FA 5.8) |
| x0.78 | camera model (J2) | 0.05 (thr 0.98, FA 0.48) | 0.40 (thr 0.9, FA 2.9) | 0.70 (FA 7.7, thr 0.2) |
| x0.3 (low) | loop model | 0.05 (thr 0.8, FA 0.26) | 0.15 (thr 0.5-0.6, FA 2.4-3.7) | 0.80 (FA 9.4, thr 0.15) |
| x0.3 | California #7 | 0.10 | 0.15 (FA 1.8) | 0.15 |
| x0.3 | camera model | 0.00 (FA 0.7-1.2) | 0.30 (thr 0.8, FA 3.6) | 0.80 (FA 7.2, thr 0.3) |

Camera evaluation at its trained threshold 0.5 (`camera_summary.json` `summary.camera`, mean over seeds): DR 0.45, time-to-detect
101 s, 6.96 false alarms per camera-pair-hour; 8 of the 20 incidents lie between the cameras (`incidents_between_cameras`); the loop
rows of the same runs equal `data/aid/test.csv` byte for byte (`loop_rows_match_saved_test_csv: true`). Low-density runs: 5 x 1 h in
5.6-7.6 s each (`densities.low.source.real_s`).

**What the frontier says.** (1) At a false-alarm rate a control room could live with (under one every two hours per sensor pair)
nothing detects at either density: all three detectors are at 0.00-0.10. (2) Detection rates of 0.5-0.8 exist, but only at 5-11 false
alarms per pair-hour, i.e. an alarm every 5-12 minutes on every pair; the curves climb only as the threshold goes under 0.3. (3) The
camera's curve lies above the loops' in the middle of the range at Dhaka density (0.40 against 0.15 at about 3 false alarms per
pair-hour), and it is a single sensor pair where the loops are ten, so per corridor-hour its false alarms are far fewer; at low density
the two are alike. (4) California #7 never passes 0.15 at any of its 336 settings. **Camera features do not detect incidents reliably
at Dhaka density either:** the honest answer is a trade of about one false alarm every 20 minutes for catching 40 % of stopped cars,
with only 8 of 20 incidents inside the cameras' 560 m stretch (IncidentNet's own task, detection from sparse sensors, is what is scored).

## IncidentNet's own code on our rows (J3-A, 2026-10-11; `evidence/aid/frontier/incidentnet.json`)

`make aid-incidentnet`: their XGBoost detection script (`third_party/incidentnet/`, Apache-2.0, five files copied unchanged, blob hashes
checked; `NOTICE`) on our camera rows, two ways. **Their way** (their function unchanged: all 1 200 camera rows as one dataset, their
`df[299:]` warm-up drop, random 80/20 row split without a seed, balanced weights, `XGBClassifier()` defaults; 5 repeats): accuracy
0.7171 ± 0.0248, precision 0.4129 ± 0.0424, recall 0.3156 ± 0.0514, f1 0.3565 ± 0.0451 on rows 30 s apart from the same runs.
**Our protocol, their recipe** (fitted on seeds 1-5, scored on held-out seeds 11-15 with our alarm rule and metrics over the frontier's
thresholds): best detection rate 0.7 at 7.2 false alarms per pair-hour (threshold 0.15, time to detect 98.2 s), against the J2
camera model's 0.7 at 7.68: the same frontier (`incidentnet.png`). Under **their evaluate() protocol** on the same held-out series
(prediction every row, their threshold 0.5): detection 90.0 %, false alarms 0.67 % of predictions, time to detect 60.0 s; their false-alarm rule looks back
1 000 rows (1 000 s at their 1 Hz, 8.3 h at our 30 s rows), so it counts almost no false alarm here, which is why that number is far
below our per-pair-hour count. The paper's 98 % / 6.26 % / 197 s are for their Tempe scenario, which is not in their repository
(gitignored with the datasets and models), so nothing is reproduced; "IncidentNet code, our scenario - not a reproduction".

## The finding

**At this density a single stopped car is invisible to loops 300 m apart.** In the test rows the stations see sparse, free-flowing
traffic: mean occupancy 2.5 % and 3.4 vehicles per 30 s per station, speeds near 60 km/h. Incident rows look like normal rows
(downstream occupancy 1.9 % against 2.5 %; the California difference OCCDF −0.1 against +0.1; speeds 59 against 62 km/h). One car
stopped in one of 2-4 lanes for 3-5 minutes neither fills the upstream loop nor empties the downstream one, so neither the classic
decision tree nor the learned model has a signature to work with. The model's perfect training score is memorised: it fits the
training pairs' own geometry and fails on pairs it has not seen. With no reliable detections the closed loop changes nothing (+4 s,
inside the seed-to-seed noise), and at the 0.5 threshold its false alarms would reroute cars for nothing.

## Honest limits

- One corridor, one demand level (RQ2b's scale 0.78 of a demand fitted to two counted sections), incidents of one kind (a stopped car),
  5 training and 5 test seeds, 20 incidents each. No sweep over density, spacing or incident severity: a heavier blockage (two lanes,
  longer) or denser traffic may well be detectable; this is not tested.
- The California thresholds are ours (calibrated on the training seeds), not the published ones.
- Time-to-detect is measured only when a detection happens (once, at threshold 0.5).
- The closed loop's warning uses the thesis's V2X delivery model with a roadside station as sender; the thesis never measured a
  roadside sender.
- Camera sensor (J2): 2 signalised junctions on the corridor give one camera pair covering 560 m of 3 400 m; "unseen location" holds
  for the incidents, not for the sensor. A camera here is TraCI's list of vehicles on the approach edge every second (ids, speeds,
  waiting time), i.e. perfect re-identification; a real camera would not have that. IncidentNet's own numbers are not reproduced (their
  Tempe SUMO files and DOT data are not in the repo); only its sensing design is followed. Trained once at Dhaka density, 600 rows.
- The frontier's curves are not monotone everywhere: an alarm is allowed once per 5 min per pair, so lowering the threshold can move
  an alarm earlier and out of an incident's window.
- The GUI's yellow ("tentative") is the model's probability between half the threshold and the threshold: a display aid, not a state
  of the detector; California #7's own tentative state is not drawn.
