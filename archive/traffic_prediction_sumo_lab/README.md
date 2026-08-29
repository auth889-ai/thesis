# Traffic Prediction → SUMO Learning Lab

This is a **small, transparent reproduction of the pipeline idea** used by:

> Advanced Traffic Demand Generation in SUMO: ML-based Prediction of Flow Rate based on Real-world Measured Datasets (VTC Spring 2024)

Important honesty note:

- This is **not the authors' official code**. No verified public official repository was found for that paper.
- This lab reproduces the paper's main pipeline using official SUMO tools:
  historical flow → ML prediction → predicted flow as SUMO demand → simulation output comparison.
- The included CSV is synthetic and is only for learning the complete plumbing today.
- Replace it with a UTD19 subset for a research-grade experiment.

## What goes in and what comes out

### Stage 1 — ML prediction

Input:

`data/demo_flow_history.csv`

Columns:

- `hour`
- `is_weekend`
- historical vehicle flow
- lag features are created in code

Output:

- `outputs/predictions.csv`
- `outputs/ml_metrics.json`
- `outputs/actual_vs_predicted.png`

### Stage 2 — SUMO demand

Input:

`outputs/predictions.csv`

Output:

`sumo/predicted_flows.rou.xml`

Each predicted hourly count becomes one SUMO `<flow>`.

### Stage 3 — SUMO simulation

Input:

- `sumo/simple.net.xml`
- `sumo/predicted_flows.rou.xml`
- `sumo/experiment.sumocfg`

Output:

- `outputs/edge_output.xml`
- `outputs/tripinfo.xml`

### Stage 4 — Validation

Input:

- ML predictions
- SUMO edge output

Output:

- `outputs/final_comparison.csv`
- `outputs/sumo_validation_metrics.json`
- `outputs/actual_predicted_sumo.png`

## macOS setup

Install XQuartz, then install the official SUMO macOS package.

Check:

```bash
sumo --version
sumo-gui --version
netconvert --version
```

Create Python environment:

```bash
cd traffic_prediction_sumo_lab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Check tools:

```bash
./00_check_tools.sh
```

## Run one stage at a time

```bash
python 01_train_predict.py
python 02_build_sumo_network.py
python 03_predictions_to_sumo.py
python 04_run_sumo.py
python 05_compare_outputs.py
```

See the simulation visually:

```bash
python 04_run_sumo.py --gui
```

Run everything:

```bash
./run_all.sh
```

## Concept while watching SUMO

The ML model does **not** drive cars.

It predicts:

`how many vehicles should enter each hour`

SUMO consumes that prediction and simulates:

- individual vehicle insertion
- movement along the route
- speed
- density
- waiting time
- completed trips

The validation asks:

`Did SUMO reproduce the predicted hourly traffic counts?`

## Upgrade to thesis quality

1. Replace the synthetic CSV with a small UTD19 city/detector subset.
2. Compare Naive, Random Forest, XGBoost, LSTM.
3. Use chronological train/validation/test splits.
4. Predict 5, 15, 30, and 60 minutes ahead.
5. Use multiple SUMO routes and detector locations.
6. Compare actual flow, ML prediction, and SUMO realized counts.
7. Repeat with multiple random seeds and report uncertainty.
