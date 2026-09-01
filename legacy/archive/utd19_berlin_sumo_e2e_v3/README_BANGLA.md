# UTD19 → Berlin → SUMO: Full End-to-End Paper Experiment (V3)

এই repository-টি VTC 2024 paper **“Advanced Traffic Demand Generation in SUMO: ML-based Prediction of Flow Rate based on Real-world Measured Datasets”** পুরোটা শেখা এবং একটি **runnable, paper-faithful end-to-end reconstruction** চালানোর জন্য তৈরি।

## সততার ঘোষণা

এটি paper authors-এর unpublished source code নয়। Paper-এ exact preprocessing, city-feature table, model hyperparameters, train/test split, Berlin OSM snapshot, detector-to-lane mapping, TAZ definitions এবং সব SUMO commands প্রকাশ করা হয়নি। তাই project-টি:

- paper-এ প্রকাশিত প্রতিটি stage বাস্তবায়ন করে;
- official UTD19, Berlin Open Data, OpenStreetMap এবং official SUMO tools ব্যবহার করে;
- প্রতিটি missing detail-কে configuration/assumption হিসেবে লিখে রাখে;
- authors-এর exact number পাওয়ার ভান করে না।

## Complete pipeline

```text
Full UTD19 dataset (6.65 GB, all valid rows scanned)
        ↓
Out-of-core preprocessing + detector/hour features
        ↓
Linear Regression + Linear SVM + Polynomial Regression
+ Decision Tree + Random Forest
        ↓
Random Forest দিয়ে Berlin detector-hour flow prediction
        ↓
Berlin actual detector data comparison (Figure-4 style)
        ↓
Berlin OSM PBF → OSM XML → SUMO network
        ↓
Berlin detectors → audited SUMO edge/lane mapping
        ↓
RandomTrips + grid-TAZ trips + detector-coverage trips
        ↓
duarouter → candidate route whitelist
        ↓
routeSampler --optimize full → calibrated 24-hour demand
        ↓
SUMO 24-hour headless simulation
        ↓
GEH + actual/predicted/simulated graphs + Figure-5 style graph
        ↓
Mac SUMO-GUI bundle with moving vehicles
```

## চারটি execution mode

1. `demo` — bundled synthetic data ও tiny SUMO network দিয়ে end-to-end smoke test।
2. `subset` — official full UTD19 preprocessing + capped model rows + 30 Berlin detectors + clipped network।
3. `full_colab` — official full UTD19 preprocessing + transparently capped expensive models + whole Berlin 24-hour pipeline।
4. `full` — literal all-row training for all five model families + whole Berlin 24 hours; high-memory workstation/server লাগতে পারে।

## শুরু করার file

Google Colab-এ খুলুন:

`notebooks/UTD19_Berlin_SUMO_Full_End_to_End.ipynb`

Notebook প্রতিটি paper section/page, input, code, output এবং simulation checkpoint একসঙ্গে দেখায়।

## One-command pipeline

```bash
python -m src.pipeline --config config/full.yaml
```

Resume করতে একই command আবার চালান। প্রতিটি stage-এর `.done.json` checkpoint থাকে।

## Expected final outputs

প্রতিটি run তার configured workspace-এ output লিখে। উদাহরণ: `/content/utd19_berlin_e2e_full/`।

```text
processed/utd19/utd19_audit.json
processed/utd19/utd19_model_table.parquet
models/model_comparison.csv
models/paper_vs_reimplementation.csv
processed/berlin/berlin_actual.parquet
processed/berlin/berlin_predictions.csv
sumo/network/berlin.net.xml
sumo/network/network_stats.json
sumo/mapping/mapping_review.html
sumo/mapping/mapping_accepted.csv
sumo/candidates/candidate_coverage.csv
sumo/calibration/predicted_edge_counts.xml
sumo/calibration/calibrated.rou.xml
sumo/calibration/route_sampler_summary.json
sumo/simulation/berlin.sumocfg
sumo/simulation/simulated_edge_counts.xml
reports/geh_summary.csv
reports/final_evaluation.json
reports/*.png
gui_bundle.zip
```

## গুরুত্বপূর্ণ বাস্তব সীমা

Whole-Berlin route calibration এবং 1.2M+ vehicles free Colab-এ বহু ঘণ্টা লাগতে পারে অথবা runtime disconnect হতে পারে। তাই `subset` certification পাস না করে `full` mode চালানো উচিত নয়। Current OSM এবং 2025-revised Berlin archive paper-এর 2023-accessed snapshots-এর সঙ্গে bit-for-bit একই নয়।

## Delivered-code validation

Read `docs/VALIDATION_STATUS.md` and `tests/offline_smoke_report.json`. Full public datasets and SUMO binaries were not executed inside the isolated artifact-build environment; the Colab notebook performs those stages.
