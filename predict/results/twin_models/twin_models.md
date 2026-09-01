# Dhaka twin forecasting — official BasicTS baselines trained locally on CPU

Dataset `predict/data/dhaka_twin` (DHAKA_SIMULATED_SENSOR_GRAPH, data.dat sha `bd02b9dba7311663`), target speed m/s, chronological 70/10/20 split, official configs (PEMS04 template → DhakaR1, CPU), harness BasicTS-legacy @4c3e2d3, NULL_VAL=0 masking.

| model | MAE@15 | RMSE@15 | MAE@30 | RMSE@30 | MAE@60 | RMSE@60 | epochs | wall s |
|---|---|---|---|---|---|---|---|---|
| STID | 0.610 | 0.998 | 0.817 | 1.250 | 0.987 | 1.476 | official | 236.0 |

Floors from `predict/results/twin_floors.md` (same split). Predictions for every test window are in `<model>_test_results.npz`.
Regenerate: `python predict/train_twin_local.py --models STID`.
