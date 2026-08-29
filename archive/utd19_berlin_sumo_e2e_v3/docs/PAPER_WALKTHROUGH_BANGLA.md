# Full Paper Walkthrough — Bangla + Code + Experiment

## Paper identity

**Advanced Traffic Demand Generation in SUMO: ML-based Prediction of Flow Rate based on Real-world Measured Datasets**  
Anjie Qiu, Prapul Alemada Sathish, Donglin Wang, Hans D. Schotten — VTC Spring 2024.

এই walkthrough paper-এর statement, আমাদের code, এবং independently generated output—এই তিনটি আলাদা রাখে।

---

## Page 1 — Abstract এবং Introduction

### Paper-এর problem

SUMO road network-এর individual vehicle simulate করতে পারে, কিন্তু realistic city demand তৈরি করা কঠিন। তিনটি common পথ:

1. random trips — সহজ, কিন্তু measured daily pattern নিশ্চিত নয়;
2. real detector/OD data — accurate হতে পারে, কিন্তু proprietary বা incomplete;
3. activity-based synthetic demand — general, কিন্তু detailed population statistics ও computation দরকার।

### Paper-এর proposed idea

```text
multi-city real detector data
→ ML model traffic flow শেখে
→ Berlin road/detector attributes দিয়ে hourly flow predicts
→ routeSampler predicted edge counts অনুযায়ী candidate routes selects
→ SUMO individual vehicles simulates
```

### Code connection

- `src/preprocess_utd19.py`
- `src/train_models.py`
- `src/predict_berlin.py`
- `src/calibrate.py`
- `src/run_simulation.py`

### Important claim boundary

Paper reports about 1.2 million vehicles in a 24-hour Berlin trial. আমাদের code সেই workflow চালায়; একই vehicle total guarantee করে না, কারণ exact authors’ settings প্রকাশিত নয়।

---

## Page 2 — Related Work এবং Methodology

### Table I-এর lesson

Bologna, Austria-West, Turin, Cologne, Monaco, Luxembourg scenario-গুলো area, vehicle count, duration, data source এবং multimodality-তে আলাদা। Paper-এর নতুন contribution হলো একটি city-specific OD survey বা full activity model ছাড়াই flow prediction থেকে demand generation।

### Methodology-এর চারটি logical stages

1. representative real dataset নির্বাচন;
2. traffic-flow regression;
3. arbitrary city network-এর lane/road features তৈরি;
4. predicted flow-কে feasible SUMO routes-এ calibrate করা।

### Conceptual question

**ML কি vehicle-এর complete route predict করে?**  
না। ML traffic count/flow predict করে। RouteSampler candidate route pool থেকে individual routes select করে।

---

## Pages 2–3 — UTD19 Training Dataset

### UTD19 scope

Paper অনুযায়ী 40 city-এর 20,000-এর বেশি stationary detector। Data mostly 2017–2019 campaigns থেকে, commonly 3–5 minute intervals।

### Measurement columns

```text
city, detid, day, interval, flow, occ, speed, error
```

Official manual-এর critical unit:

```text
flow = vehicles/hour/lane
```

তাই 5-minute rows-এর `flow` যোগ করলে unit ভুল হয়। এই project hourly window-এ `mean(flow)` ব্যবহার করে এবং sensitivity-এর জন্য median-ও রাখে। Paper exact aggregation rule দেয়নি—এটি documented reconstruction।

### Table II detector attributes

| Feature | Meaning | Code use |
|---|---|---|
| detid | detector ID | grouping/key |
| length | monitored lane length km | ML feature |
| pos | next major intersection distance km | ML feature |
| fclass | OSM road class | ML feature |
| road | road name | mapping audit, not default model feature |
| limit | speed limit | ML feature |
| citycode | city | group split/join |
| lanes | monitored lanes | ML feature and per-lane→detector total |
| linkid | link relation | metadata/audit |
| long/lat | WGS84 location | excluded from ML, used for map |

### Paper-added features

Paper says lane density, population, population density manually added. Exact table/source is not published. Project does not fabricate these values; optional sourced CSV can be supplied.

### Code connection

```text
src/download_utd19.py
src/preprocess_utd19.py
outputs: utd19_hourly.parquet, utd19_model_table.parquet, utd19_audit.json
```

---

## Pages 3–4 — Berlin Verification Dataset

### Why Berlin is separate

Berlin is external verification data, not part of UTD19 training. This tests whether learned relationships generalize to a new metropolis.

### Table III

```text
detid, date, hour, quality,
Nveh, vveh,
Npassenger, vpassenger,
Ntruck, vtruck
```

- `quality=1` valid;
- `Nveh` hourly count;
- `vveh` average speed;
- passenger and truck columns describe composition.

### Current archive warning

The official archive was revised after the paper. Current historical files may not be byte-identical to the authors’ 2023-accessed snapshot.

### Code connection

```text
src/download_berlin.py
src/preprocess_berlin.py
outputs: berlin_actual.parquet, berlin_locations.csv, berlin_audit.json
```

---

## Page 4 — Step 1: ML Predictions

### Feature alignment

A Berlin detector must receive the same input feature meanings used during training:

```text
hour, weekday, weekend, month, day-of-year,
length, position, speed limit, monitored lanes, road class
```

### Target-unit decision

UTD19 flow is per lane; Berlin `Nveh` is generally detector total. Default project protocol trains:

```text
target_flow = UTD19 per-lane flow × monitored lanes
```

This assumption is recorded because paper does not fully explain its conversion.

### Code connection

```text
src/build_berlin_features.py
src/predict_berlin.py
outputs: berlin_predictions.csv, actual_vs_predicted_all_days.csv
```

---

## Page 4 — Step 2: Berlin Network

### Paper workflow

```text
Berlin OSM
→ osmium boundary trim
→ osmfilter feature retention
→ optional JOSM manual fixes
→ netconvert
→ berlin.net.xml
```

Project uses current Geofabrik Berlin PBF, optional detector bounding box for subset mode, `osmium`, and `netconvert`. Exact 2023 OSM snapshot and manual JOSM changes are unavailable.

### Detector mapping gate

WGS84 detector coordinates must be assigned to the correct directed SUMO lane/edge. Nearest road alone can be wrong because of:

- divided roads;
- opposite direction;
- parallel roads;
- bridge/tunnel levels;
- mismatched lane count;
- station ID versus direction ID.

Project creates:

```text
mapping_candidates.csv
mapping_review.html
mapping_review_template.csv
mapping_accepted.csv
```

Full mode intentionally stops for review unless `--accept-auto-mapping` is explicitly used.

---

## Page 4 — Step 3: Candidate Routes

### RandomTrips

`randomTrips.py` creates start/end trips. `duarouter` turns them into complete paths.

### Why TAZ is required

Random routes may never cross some monitored lane. RouteSampler cannot satisfy a positive count on an edge absent from all candidate routes.

Project uses three candidate pools:

1. random trips routed by duarouter;
2. grid-based TAZ trips routed by duarouter;
3. detector-targeted coverage trips that contain each monitored edge.

The third is an explicit robustness addition, not a claim that paper used the same algorithm.

### Required certification

`candidate_coverage_summary.json` must report 100% monitored-edge coverage before calibration.

---

## Page 5 — Step 4: routeSampler Calibration

### Inputs

```text
random.routes.xml
taz.routes.xml
coverage.routes.xml
+
predicted_edge_counts.xml
```

### Operation

RouteSampler selects/reuses routes so edge counts match as closely as possible. Paper describes the matching as an LP problem and sets optimization to `full`.

### Code connection

```text
src/counts_to_edgedata.py
src/calibrate.py
outputs: calibrated.rou.xml, route_sampler_mismatch.xml, route_sampler.log
```

### Figure 3 interpretation

Before calibration, randomly generated cars produce counts unrelated to detector targets. After calibration, route quantities are adjusted to reduce underflow and overflow at monitored roads.

---

## Page 5 — Results of Five ML Models

### Paper Table V

| Model | SMAPE % | MAE |
|---|---:|---:|
| Linear Regression | 72.08 | 194.49 |
| Linear SVM | 71.53 | 187.16 |
| Polynomial Regression | 69.51 | 172.34 |
| Decision Tree | 19.74 | 79.85 |
| Random Forest | 17.12 | 71.04 |

### Why tree models help

Traffic has interactions and thresholds: road class × lane count × time × city characteristics. Linear models cannot represent many such relationships. A single tree can overfit; Random Forest averages multiple trees and generally reduces variance.

### Reimplementation protocol

- complete detector groups are held out with GroupShuffleSplit;
- seed is recorded;
- five model families are compared;
- paper and our results are stored side by side;
- same paper numbers are not expected because exact split/hyperparameters are missing.

---

## Page 6 — Figure 4: Actual vs Predicted

Paper plots actual traffic for 02–06 February 2021 and one predicted 24-hour curve.

- highway detector: relatively stable dates and clear morning peak;
- junction detector: more dynamic day-to-day variation;
- model is judged partly by whether it captures peak/off-peak shape.

Project produces one figure per selected detector and quantitative MAE/RMSE/SMAPE over matched detector-hour rows.

---

## Page 6 — GEH Validation

### Formula

```text
GEH = sqrt( 2 × (M − C)^2 / (M + C) )
```

- `C`: predicted/calibration count;
- `M`: observed count after route generation/simulation.

Project calculates GEH for every monitored edge-hour, percentage below 5 and below 10, mean and median.

### Wording inconsistency

Paper body says 85% detectors have `GEH < 5`; abstract says mismatch below five vehicles. They are not equivalent. Evaluation reports both GEH and absolute mismatch.

---

## Pages 6–7 — Figure 5 and 24-hour Simulation

Paper compares predicted/matched demand with the number of vehicles actually running in the network. A time shift occurs because:

- count target relates to vehicle passage/entry in a time interval;
- running vehicles remain in the network until routes end;
- congestion changes travel time;
- routeSampler matching and SUMO network occupancy are different quantities.

Project therefore keeps separate plots for:

1. predicted monitored-edge entries;
2. simulated monitored-edge entries;
3. mean vehicles running in the whole network.

---

## Page 7 — Conclusion and Future Scope

Paper reports a large 24-hour Berlin scenario and suggests:

- neural networks or more advanced models;
- route-generation improvements;
- fewer waiting/stuck vehicles;
- additional data and features;
- user-selected detectors;
- traffic assignment that accounts for loaded-network travel times.

Project records teleports/waiting/statistics so these limitations can be measured rather than hidden.

---

# End-to-end output checklist

```text
Full UTD19 downloaded                 [ ]
Every raw row scanned                 [ ]
Hourly feature table created          [ ]
Five models compared                  [ ]
Random Forest saved                   [ ]
Berlin actual data parsed             [ ]
Berlin predictions generated          [ ]
OSM network converted                 [ ]
Detector mapping reviewed             [ ]
Random + TAZ + coverage routes built  [ ]
100% candidate coverage               [ ]
RouteSampler calibration completed    [ ]
24-hour headless simulation completed [ ]
GEH and plots generated               [ ]
GUI bundle opened locally             [ ]
```

Only checked, evidence-backed stages should be called complete.
