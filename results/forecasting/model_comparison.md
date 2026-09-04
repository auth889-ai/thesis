# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 80 nodes, 60 test windows

Context 96 steps; chronological 70 / 10 / 20; windows sampled from the TEST region. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| chronos | 3.7279 | 7.5055 | 8.566 | **9.1831** | 0.7885 | 7.0214 | 0.8162 | 54.14 min |
| historical_average | 5.0816 | 8.9906 | 16.397 | **20.6456** | 0.3866 | 5.0116 | 0.2991 | 47.43 min |
| persistence | 3.432 | 6.7157 | 7.751 | **7.9313** | 0.7867 | 5.1073 | 0.8419 | 60.0 min |
| random_forest | 3.7654 | 6.81 | 8.845 | **9.2735** | 0.7619 | 5.7327 | 0.8291 | 46.21 min |
| xgboost | 3.4695 | 6.266 | 8.457 | **9.4462** | 0.7738 | 5.3949 | 0.8376 | 46.25 min |

Regenerate: `python pipeline/forecasting/evaluate_models.py --all`. Machine-readable: `model_comparison.json`.
