# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 80 nodes, 120 test windows

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| chronos | 4.2571 | 7.592 | 11.567 | **7.9419** | 0.8194 | 7.8544 | 0.3179 | 56.35 min |
| historical_average | 5.5892 | 9.8724 | 23.177 | **19.6821** | 0.4272 | 5.2195 | 0.1391 | 48.1 min |
| persistence | 4.0048 | 7.1771 | 10.718 | **7.2241** | 0.8411 | 6.2388 | 0.0265 | 60.0 min |
| random_forest | 3.9829 | 7.0419 | 12.022 | **8.6196** | 0.8229 | 6.4206 | 0.1325 | 23.25 min |
| xgboost | 3.9689 | 7.0503 | 12.003 | **8.6148** | 0.8232 | 6.3701 | 0.1987 | 25.67 min |

Regenerate: `python pipeline/forecasting/evaluate_models.py --all`. Machine-readable: `model_comparison.json`.
