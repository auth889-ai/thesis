# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 207 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | – | – | – | **–** | – | – | 0.6969 | 48.72 min |
| DCRNN | – | – | – | **–** | – | – | 0.6632 | 50.68 min |
| GWNet | – | – | – | **–** | – | – | 0.5544 | 49.37 min |
| MegaCRN | – | – | – | **–** | – | – | 0.6788 | 48.3 min |
| STAEformer | – | – | – | **–** | – | – | 0.614 | 52.51 min |
| STID | – | – | – | **–** | – | – | 0.5 | 51.79 min |
| chronos2 | – | – | – | **–** | – | – | 0.3601 | 50.0 min |
| chronos2_mv | – | – | – | **–** | – | – | 0.3472 | 51.31 min |
| historical_average | – | – | – | **–** | – | – | 0.1295 | 52.4 min |
| persistence | – | – | – | **–** | – | – | 0.013 | 60.0 min |
| random_forest | – | – | – | **–** | – | – | 0.215 | 18.86 min |
| xgboost | – | – | – | **–** | – | – | 0.2332 | 26.33 min |

## METR-LA — 207 nodes, 120 test windows, seed 23

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | – | – | – | **–** | – | – | 0.6535 | 48.43 min |
| DCRNN | – | – | – | **–** | – | – | 0.6201 | 47.51 min |
| GWNet | – | – | – | **–** | – | – | 0.5217 | 51.98 min |
| MegaCRN | – | – | – | **–** | – | – | 0.685 | 48.91 min |
| STAEformer | – | – | – | **–** | – | – | 0.5787 | 52.26 min |
| STID | – | – | – | **–** | – | – | 0.4094 | 52.33 min |
| chronos2 | – | – | – | **–** | – | – | 0.3622 | 52.34 min |
| chronos2_mv | – | – | – | **–** | – | – | 0.3642 | 52.38 min |
| historical_average | – | – | – | **–** | – | – | 0.2106 | 54.25 min |
| persistence | – | – | – | **–** | – | – | 0.1004 | 60.0 min |
| random_forest | – | – | – | **–** | – | – | 0.2717 | 37.03 min |
| xgboost | – | – | – | **–** | – | – | 0.3031 | 36.98 min |

## METR-LA — 207 nodes, 120 test windows, seed 37

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | – | – | – | **–** | – | – | 0.6982 | 50.81 min |
| DCRNN | – | – | – | **–** | – | – | 0.6298 | 50.75 min |
| GWNet | – | – | – | **–** | – | – | 0.5553 | 49.2 min |
| MegaCRN | – | – | – | **–** | – | – | 0.6922 | 48.43 min |
| STAEformer | – | – | – | **–** | – | – | 0.6036 | 54.63 min |
| STID | – | – | – | **–** | – | – | 0.4286 | 56.29 min |
| chronos2 | – | – | – | **–** | – | – | 0.2213 | 38.23 min |
| chronos2_mv | – | – | – | **–** | – | – | 0.2072 | 35.19 min |
| historical_average | – | – | – | **–** | – | – | 0.173 | 53.55 min |
| persistence | – | – | – | **–** | – | – | 0.004 | 60.0 min |
| random_forest | – | – | – | **–** | – | – | 0.2414 | 26.5 min |
| xgboost | – | – | – | **–** | – | – | 0.2455 | 28.07 min |

## METR-LA — 80 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | 2.7727 | 5.0084 | 7.206 | **4.9639** | 0.8942 | 3.3579 | 0.7285 | 48.18 min |
| DCRNN | 2.918 | 5.4255 | 7.81 | **5.5386** | 0.8879 | 3.6018 | 0.6887 | 50.62 min |
| GWNet | 3.036 | 5.566 | 8.304 | **5.881** | 0.8797 | 3.7274 | 0.5828 | 48.69 min |
| MegaCRN | 2.8332 | 5.124 | 7.439 | **5.1943** | 0.8988 | 3.5007 | 0.7086 | 49.11 min |
| STAEformer | 2.9306 | 5.3287 | 7.882 | **5.4885** | 0.8855 | 3.4181 | 0.6623 | 50.75 min |
| STID | 3.132 | 5.9466 | 9.316 | **6.6097** | 0.8742 | 3.7521 | 0.5166 | 48.91 min |
| chronos | 4.2571 | 7.592 | 11.567 | **7.9419** | 0.8194 | 7.8544 | 0.3179 | 56.35 min |
| chronos2 | 3.9193 | 7.3964 | 10.893 | **7.5931** | 0.8322 | 7.1116 | 0.3576 | 54.07 min |
| chronos2_mv | 3.684 | 7.0202 | 10.247 | **7.209** | 0.8442 | 6.1509 | 0.351 | 54.15 min |
| historical_average | 5.5892 | 9.8724 | 23.177 | **19.6821** | 0.4272 | 5.2195 | 0.1391 | 48.1 min |
| persistence | 4.0048 | 7.1771 | 10.718 | **7.2241** | 0.8411 | 6.2388 | 0.0265 | 60.0 min |
| random_forest | 3.9829 | 7.0419 | 12.022 | **8.6196** | 0.8229 | 6.4206 | 0.1325 | 23.25 min |
| timesfm | 3.9119 | 7.4763 | 11.257 | **8.4877** | 0.8163 | 6.5428 | 0.2848 | 51.4 min |
| xgboost | 3.9689 | 7.0503 | 12.003 | **8.6148** | 0.8232 | 6.3701 | 0.1987 | 25.67 min |

## PEMS-BAY — 80 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| GWNet | – | – | – | **–** | – | – | 1.0 | 60.0 min |
| STID | – | – | – | **–** | – | – | 1.0 | 55.0 min |
| chronos | – | – | – | **–** | – | – | 0.1818 | 32.5 min |
| historical_average | – | – | – | **–** | – | – | – | None min |
| persistence | – | – | – | **–** | – | – | – | None min |
| random_forest | – | – | – | **–** | – | – | 0.5455 | 55.0 min |
| xgboost | – | – | – | **–** | – | – | 0.9091 | 54.0 min |

Regenerate: `python -m app.forecasting.evaluation.evaluate_models --all`. Machine-readable: `model_comparison.json`.
