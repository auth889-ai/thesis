# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 207 nodes, 40 test windows

Context 96 steps; chronological 70 / 10 / 20; windows sampled from the TEST region. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| historical_average | 4.7722 | 8.5111 | 14.355 | **19.4041** | 0.4486 | 4.71 | 0.3312 | 53.58 min |
| persistence | 3.5047 | 6.4023 | 7.814 | **7.1968** | 0.8035 | 6.7926 | 0.875 | 60.0 min |
| random_forest | 3.5252 | 6.1994 | 8.463 | **8.6876** | 0.7618 | 6.0662 | 0.8562 | 46.51 min |
| xgboost | 3.4909 | 6.1337 | 8.465 | **8.9831** | 0.7765 | 5.9391 | 0.8562 | 44.98 min |

Regenerate: `python pipeline/forecasting/evaluate_models.py --all`. Machine-readable: `model_comparison.json`.
