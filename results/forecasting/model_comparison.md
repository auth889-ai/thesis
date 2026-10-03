# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 207 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
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
| DCRNN | 2.9052 | 5.7559 | 7.813 | **6.7875** | 0.8381 | 4.3953 | 0.6298 | 50.75 min |
| GWNet | 3.0068 | 5.8583 | 8.29 | **7.2622** | 0.8273 | 4.6413 | 0.5553 | 49.2 min |
| MegaCRN | 2.8534 | 5.5895 | 7.614 | **6.5124** | 0.8457 | 4.2585 | 0.6922 | 48.43 min |
| STAEformer | 2.9756 | 5.9652 | 8.092 | **7.0003** | 0.8322 | 4.2152 | 0.6036 | 54.63 min |
| STID | 3.1303 | 6.2852 | 8.935 | **8.0908** | 0.8164 | 4.5156 | 0.4286 | 56.29 min |
| chronos2 | 3.7485 | 7.7507 | 10.643 | **9.5961** | 0.7877 | 6.8367 | 0.2213 | 38.23 min |
| chronos2_mv | 3.5432 | 7.0602 | 10.047 | **8.9872** | 0.7885 | 6.3974 | 0.2072 | 35.19 min |
| historical_average | 5.0922 | 9.0537 | 17.299 | **18.1262** | 0.483 | 5.7537 | 0.173 | 53.55 min |
| persistence | 3.7571 | 7.0281 | 9.998 | **8.3507** | 0.7993 | 6.5183 | 0.004 | 60.0 min |
| random_forest | 3.7457 | 6.9571 | 10.673 | **9.2326** | 0.7857 | 6.7625 | 0.2414 | 26.5 min |
| xgboost | 3.7487 | 6.9685 | 10.702 | **9.2993** | 0.7877 | 6.773 | 0.2455 | 28.07 min |

## METR-LA — 80 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| DCRNN | – | – | – | **–** | – | – | 0.6887 | 50.62 min |
| GWNet | – | – | – | **–** | – | – | 0.5828 | 48.69 min |
| MegaCRN | – | – | – | **–** | – | – | 0.7086 | 49.11 min |
| STAEformer | – | – | – | **–** | – | – | 0.6623 | 50.75 min |
| STID | – | – | – | **–** | – | – | 0.5166 | 48.91 min |
| chronos | – | – | – | **–** | – | – | 0.3179 | 56.35 min |
| chronos2 | – | – | – | **–** | – | – | 0.3576 | 54.07 min |
| chronos2_mv | – | – | – | **–** | – | – | 0.351 | 54.15 min |
| historical_average | – | – | – | **–** | – | – | 0.1391 | 48.1 min |
| persistence | – | – | – | **–** | – | – | 0.0265 | 60.0 min |
| random_forest | – | – | – | **–** | – | – | 0.1325 | 23.25 min |
| timesfm | – | – | – | **–** | – | – | 0.2848 | 51.4 min |
| xgboost | – | – | – | **–** | – | – | 0.1987 | 25.67 min |

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
