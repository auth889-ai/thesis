#!/usr/bin/env bash
set -euo pipefail

python3 01_train_predict.py
python3 02_build_sumo_network.py
python3 03_predictions_to_sumo.py
python3 04_run_sumo.py
python3 05_compare_outputs.py

echo
echo "All stages finished. Open the outputs/ folder."
