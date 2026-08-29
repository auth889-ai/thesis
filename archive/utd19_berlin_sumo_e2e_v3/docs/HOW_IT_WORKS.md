# What the research does, and what SUMO actually does

Paper: *Advanced Traffic Demand Generation in SUMO: ML-based Prediction of Flow Rate based
on Real-world Measured Datasets* — Qiu, Alemada Sathish, Wang, Schotten, IEEE VTC Spring 2024.

---

## 1. The one idea

Most people assume the direction is **SUMO → data → ML**. This paper is the opposite:

```
Real measured traffic data  ──►  ML model  ──►  predicted flow  ──►  SUMO  ──►  simulated city
```

The problem being solved is **demand generation**. If you want to simulate Berlin, you need to
know how many cars use each road each hour. Normally you either

* have a real OD matrix (proprietary, rarely available), or
* use `randomTrips.py` and get traffic that is statistically meaningless.

The paper's answer: **train an ML model on 40 other cities, then ask it to predict flows for a
city you have no demand data for.** SUMO then builds real vehicle traffic matching those
predictions.

---

## 2. What the ML part does

### Input (from UTD19)

23,577 detectors, 40 cities, 169,032,955 rows. For each detector-hour the features are:

| Feature | Source | Example |
|---|---|---|
| hour of day, weekday, month | measurement timestamp | 8 |
| road length | UTD19 `length` | 0.196 km |
| distance to next junction | UTD19 `pos` | 0.0055 km |
| road class | UTD19 `fclass` | `secondary` |
| speed limit | UTD19 `limit` | 50 |
| number of monitored lanes | UTD19 `lanes` | 1 |
| coordinates | UTD19 `long`, `lat` | 10.889, 48.360 |

### Output

**One number: traffic flow.** How many vehicles pass that road in that hour.

> `8:00–9:00, Road A → 143 vehicles/hour`

### Models compared (paper Table V)

| Model | Paper SMAPE | Paper MAE |
|---|---|---|
| Linear Regression | 72.08 | 194.49 |
| Linear SVM | 71.53 | 187.16 |
| Polynomial Regression | 69.51 | 172.34 |
| Decision Tree | 19.74 | 79.85 |
| **Random Forest** | **17.12** | **71.04** |

Random Forest wins, so it is the model used for Berlin. **There is no deep learning in this
paper** — that is exactly where your thesis can add LSTM / XGBoost.

One thing worth understanding: the split is a **group holdout by whole detector**. No detector
appears in both train and test. That is the honest way to measure "can this model predict a
road it has never seen", which is precisely what the Berlin transfer needs.

---

## 3. What SUMO actually does

This is the part that confuses most people. SUMO does **not** predict anything. It is a
microscopic simulator: given a road network and a list of vehicles with routes, it moves every
car second by second with car-following and traffic-light logic.

So the ML output has to be converted into *vehicles with routes*. Four stages:

### Stage 1 — build the network (`netconvert`)
Berlin OpenStreetMap extract → `berlin.net.xml`. Roads, lanes, speed limits, junctions,
traffic lights.

### Stage 2 — invent candidate routes
`routeSampler.py` can only **choose** from routes you hand it; it cannot invent them. So we
generate a large pool three ways:

1. `randomTrips.py` → `duarouter` — general background traffic
2. **TAZ trips** — so every zone of the city is represented
3. **coverage trips** — routes deliberately forced through each monitored edge, because
   random routes will not reliably cross all 216 detector locations

### Stage 3 — calibrate to the prediction (`routeSampler.py`) ← **the key step**
The ML predictions are written as a SUMO `edgeData` file: "edge X must be crossed by 143
vehicles between 08:00 and 09:00".

`routeSampler --optimize full` then solves a linear program: *how many times should each
candidate route be used, so that the vehicle count on every monitored edge matches the
predicted count?*

This is the paper's Figure 3: before calibration the flows are random; after calibration they
match the ML prediction.

### Stage 4 — run it
24 hours (86,400 s) of simulation. The paper generated **~1.2 million vehicles** for Berlin.

### Then: did it work?
Compare the counts SUMO actually produced against the predicted counts using **GEH**:

```
GEH = sqrt( 2(M-C)² / (M+C) )      C = predicted count,  M = count after simulation
```

GEH < 5 is the standard traffic-engineering acceptance threshold. The paper reports **GEH < 5
for more than 85 %** of monitored lanes.

---

## 4. Where each step lives in this repo

| Step | Code | Paper |
|---|---|---|
| 01–02 download + aggregate UTD19 | `src/download_utd19.py`, `src/preprocess_utd19.py` | III-A |
| 03 train 5 models | `src/train_models.py` | V-A, Table V |
| 04–05 Berlin baseline | `src/download_berlin.py`, `src/preprocess_berlin.py` | III-B, Table III |
| 06–07 OSM → network | `src/download_osm.py`, `src/build_network.py` | IV-B |
| 08 detector → edge mapping | `src/map_detectors.py` | IV-B |
| 09–10 predict Berlin flows | `src/build_berlin_features.py`, `src/predict_berlin.py` | IV-A, Table IV |
| 11–13 candidate routes | `src/create_taz.py`, `src/generate_candidates.py` | IV-C |
| 14–15 calibration | `src/counts_to_edgedata.py`, `src/calibrate.py` | IV-D, Fig. 3 |
| 16–17 24 h simulation | `src/build_simulation.py`, `src/run_simulation.py` | V-C |
| 18–20 GEH + figures | `src/extract_simulated_counts.py`, `src/evaluate.py` | V-B/C, Fig. 4, 5 |

---

## 5. How to *see* the simulation

Colab has no display, so the GUI has to run on your Mac. Step 20 packages everything you need
into `gui_bundle.zip` (network + calibrated routes + a ready `.sumocfg`).

```bash
pip install eclipse-sumo sumolib traci
unzip gui_bundle.zip -d berlin_gui
cd berlin_gui
sumo-gui -c berlin.sumocfg
```

Press **Run** (the green triangle). Set *Delay* to ~50 ms or everything flashes past.

Things worth doing once it is open:

* **View → Color vehicles by → speed** — congestion turns red, so you can watch the morning
  peak build up and clear.
* **Right-click a monitored edge → Show parameter** — compare its live count against the
  predicted count that generated it.
* The bottom status bar shows *running* / *inserted*. If **waiting** climbs and never drains,
  the network cannot absorb the demand (this is what happened in the clipped 4 km test run).

### Reading the numbers afterwards

`reports/final_evaluation.json` is the summary:

```json
"GEH": { "GEH_lt_5_percent": ... }          <- the paper's 85% claim
"actual_vs_prediction": { "SMAPE_percent": ... }   <- ML quality on Berlin
"simulation_extraction": { "inserted_vehicles": ... }   <- the paper's 1.2M
```

Two GEH numbers exist and they mean different things:

* `route_sampler.weighted_GEH_lt_threshold_percent` — did the **linear program** find a route
  mix matching the counts? (Usually ~100 %.)
* `GEH.GEH_lt_5_percent` — did the **simulation** actually deliver those vehicles past the
  detectors? This is the honest one. It is lower whenever vehicles cannot be inserted, get
  stuck, or teleport.

If the second is far below the first, look at `teleports` and `waiting` in the same file: the
demand is not physically fitting on the network.

---

## 6. What you may claim

**Fair:** a paper-faithful end-to-end reconstruction on the official public data, using the
same SUMO tools, producing independently generated results.

**Not fair:** exact reproduction of Table V or of the 1.2 M vehicle scenario. The authors
published no code, no row filter, no split, no hyperparameters, no OSM snapshot, no TAZ
definitions and no candidate-route counts. Every one of those is a free parameter here, and
each is recorded in `training_protocol.json` / the manifests so your thesis can state exactly
what was chosen. See `REPRODUCIBILITY_GAPS.md`.

---

## 7. Where your contribution goes

The paper's own "Future Scope" section asks for exactly this:

> *"the use of more sophisticated Machine Learning models such as Artificial Neural Networks
> could be explored to increase the accuracy of traffic flow prediction"*

So the natural thesis extension is:

| Paper | You add |
|---|---|
| Linear Regression, SVM, Polynomial, Decision Tree, Random Forest | XGBoost, LSTM / GRU |
| Static per-hour features | Previous-hours sequence as input |
| One model for all cities | Per-city or fine-tuned model |

Because the pipeline swaps models at exactly one place (`train_models.py` writes
`random_forest_for_berlin.joblib`, `predict_berlin.py` loads it), adding a model means adding
one estimator and rerunning steps 03 and 09–20. The SUMO half does not change.
