# Model comparison — one protocol, models that can be compared

Every model below sees the SAME test windows, the SAME context and the SAME horizons, on datasets where the future is known. This is what turns a forecast into evidence.

OpenCity is deliberately absent: it is scored on a 288-step horizon under its authors' split, and mixing that with 5/15/30/60-minute horizons would be the incompatible comparison this project keeps refusing to make.


## METR-LA — 207 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | 2.7732 | 4.9928 | 7.551 | **4.824** | 0.9045 | 3.3004 | 0.6969 | 48.72 min |
| DCRNN | 2.8624 | 5.2062 | 7.88 | **5.1331** | 0.9001 | 3.4961 | 0.6632 | 50.68 min |
| GWNet | 2.9772 | 5.3643 | 8.448 | **5.4926** | 0.8944 | 3.5227 | 0.5544 | 49.37 min |
| MegaCRN | 2.8458 | 5.1173 | 7.786 | **5.0066** | 0.9058 | 3.3952 | 0.6788 | 48.3 min |
| STAEformer | 2.9091 | 5.2451 | 8.087 | **5.2356** | 0.8957 | 3.2672 | 0.614 | 52.51 min |
| STID | 3.085 | 5.6454 | 9.29 | **6.1696** | 0.8855 | 3.5564 | 0.5 | 51.79 min |
| chronos | 4.1735 | 7.3378 | 11.196 | **7.043** | 0.8372 | 7.8153 | 0.3523 | 56.36 min |
| chronos2 | 3.8389 | 7.1348 | 10.609 | **6.8452** | 0.8476 | 7.0218 | 0.3601 | 50.0 min |
| chronos2_mv | 3.6163 | 6.7644 | 10.029 | **6.4742** | 0.8598 | 6.0734 | 0.3472 | 51.31 min |
| historical_average | 5.6319 | 9.7911 | 23.61 | **18.7471** | 0.4749 | 5.2485 | 0.1295 | 52.4 min |
| persistence | 3.9621 | 6.9319 | 10.605 | **6.6314** | 0.8604 | 6.1268 | 0.013 | 60.0 min |
| random_forest | 3.8812 | 6.726 | 11.58 | **7.626** | 0.8459 | 6.3008 | 0.215 | 18.86 min |
| timesfm | 3.8769 | 7.2397 | 11.032 | **7.5596** | 0.8332 | 6.5636 | 0.3135 | 54.92 min |
| xgboost | 3.8796 | 6.7745 | 11.614 | **7.7966** | 0.8445 | 6.2936 | 0.2332 | 26.33 min |

## METR-LA — 207 nodes, 120 test windows, seed 23

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | 3.2202 | 6.1783 | 10.285 | **5.8502** | 0.8824 | 4.0306 | 0.6535 | 48.43 min |
| DCRNN | 3.37 | 6.4596 | 10.653 | **5.9848** | 0.8796 | 4.3823 | 0.6201 | 47.51 min |
| GWNet | 3.5639 | 6.7951 | 12.043 | **7.0479** | 0.868 | 4.5818 | 0.5217 | 51.98 min |
| MegaCRN | 3.2835 | 6.1818 | 10.394 | **5.7777** | 0.886 | 4.2424 | 0.685 | 48.91 min |
| STAEformer | 3.3047 | 6.2576 | 10.529 | **6.0837** | 0.8801 | 4.1522 | 0.5787 | 52.26 min |
| STID | 3.6572 | 7.0448 | 12.552 | **7.5191** | 0.8619 | 4.5878 | 0.4094 | 52.33 min |
| chronos | 4.4268 | 8.0843 | 14.394 | **8.473** | 0.8317 | 7.427 | 0.2874 | 52.12 min |
| chronos2 | 4.1399 | 8.0958 | 13.039 | **7.4701** | 0.8526 | 6.9838 | 0.3622 | 52.34 min |
| chronos2_mv | 4.0014 | 7.7467 | 12.48 | **6.998** | 0.8548 | 6.5578 | 0.3642 | 52.38 min |
| historical_average | 6.3942 | 10.296 | 26.219 | **16.9938** | 0.5566 | 6.1677 | 0.2106 | 54.25 min |
| persistence | 4.3751 | 7.9266 | 13.204 | **7.3113** | 0.8513 | 6.8714 | 0.1004 | 60.0 min |
| random_forest | 4.3958 | 7.6989 | 14.79 | **8.484** | 0.8346 | 7.1671 | 0.2717 | 37.03 min |
| timesfm | 4.2348 | 7.9951 | 13.619 | **8.1555** | 0.8356 | 6.8759 | 0.2894 | 56.39 min |
| xgboost | 4.4383 | 7.8332 | 15.003 | **8.6406** | 0.8324 | 7.2305 | 0.3031 | 36.98 min |

## METR-LA — 207 nodes, 120 test windows, seed 37

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | 2.8209 | 5.5825 | 7.506 | **6.4054** | 0.8488 | 4.0063 | 0.6982 | 50.81 min |
| DCRNN | 2.9052 | 5.7559 | 7.813 | **6.7875** | 0.8381 | 4.3953 | 0.6298 | 50.75 min |
| GWNet | 3.0068 | 5.8583 | 8.29 | **7.2622** | 0.8273 | 4.6413 | 0.5553 | 49.2 min |
| MegaCRN | 2.8534 | 5.5895 | 7.614 | **6.5124** | 0.8457 | 4.2585 | 0.6922 | 48.43 min |
| STAEformer | 2.9756 | 5.9652 | 8.092 | **7.0003** | 0.8322 | 4.2152 | 0.6036 | 54.63 min |
| STID | 3.1303 | 6.2852 | 8.935 | **8.0908** | 0.8164 | 4.5156 | 0.4286 | 56.29 min |
| chronos | 3.8297 | 7.3497 | 11.201 | **10.3473** | 0.7655 | 6.8066 | 0.1469 | 35.07 min |
| chronos2 | 3.7485 | 7.7507 | 10.643 | **9.5961** | 0.7877 | 6.8367 | 0.2213 | 38.23 min |
| chronos2_mv | 3.5432 | 7.0602 | 10.047 | **8.9872** | 0.7885 | 6.3974 | 0.2072 | 35.19 min |
| historical_average | 5.0922 | 9.0537 | 17.299 | **18.1262** | 0.483 | 5.7537 | 0.173 | 53.55 min |
| persistence | 3.7571 | 7.0281 | 9.998 | **8.3507** | 0.7993 | 6.5183 | 0.004 | 60.0 min |
| random_forest | 3.7457 | 6.9571 | 10.673 | **9.2326** | 0.7857 | 6.7625 | 0.2414 | 26.5 min |
| timesfm | 3.8134 | 7.5341 | 11.472 | **10.9043** | 0.7531 | 6.7178 | 0.1368 | 47.35 min |
| xgboost | 3.7487 | 6.9685 | 10.702 | **9.2993** | 0.7877 | 6.773 | 0.2455 | 28.07 min |

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

## PEMS-BAY — 325 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| DCRNN | 0.9833 | 1.8905 | 1.632 | **6.9569** | 0.7849 | 1.3777 | 0.7727 | 59.12 min |
| GWNet | 0.9939 | 1.9294 | 1.649 | **6.7705** | 0.7752 | 1.3508 | 0.8182 | 59.17 min |
| STID | 0.9701 | 1.8818 | 1.609 | **6.8029** | 0.755 | 1.3065 | 0.8182 | 56.94 min |
| chronos | 1.3335 | 2.5328 | 2.238 | **11.5912** | 0.6453 | 3.0748 | 0.1818 | 38.75 min |
| chronos2 | 1.3028 | 4.3408 | 2.325 | **20.5448** | 0.695 | 2.8993 | 0.4773 | 58.57 min |
| chronos2_mv | 1.1737 | 2.4753 | 2.033 | **13.7881** | 0.6257 | 2.4699 | 0.2045 | 26.67 min |
| historical_average | 1.6838 | 3.342 | 3.004 | **25.9181** | 0.0 | 2.1421 | 0.0227 | 60.0 min |
| persistence | 1.2527 | 2.4166 | 2.103 | **11.0297** | 0.6453 | 2.4183 | – | None min |
| random_forest | 1.2184 | 2.3955 | 2.054 | **11.4772** | 0.6134 | 2.3365 | 0.6136 | 47.59 min |
| timesfm | 1.226 | 2.5705 | 2.148 | **15.6202** | 0.4907 | 2.4332 | 0.0909 | 31.25 min |
| xgboost | 1.1978 | 2.3544 | 2.02 | **11.2945** | 0.6118 | 2.2886 | 0.6364 | 47.14 min |

## PEMS-BAY — 325 nodes, 120 test windows, seed 23

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| DCRNN | 0.9758 | 1.937 | 1.754 | **5.7342** | 0.8527 | 1.3798 | 0.2903 | 26.67 min |
| GWNet | 0.9684 | 1.9461 | 1.724 | **5.6974** | 0.8555 | 1.3252 | 0.2581 | 17.5 min |
| STID | 0.9619 | 1.9185 | 1.7 | **5.3826** | 0.8526 | 1.3043 | 0.2258 | 17.14 min |
| chronos | 1.0582 | 2.1091 | 1.875 | **5.8692** | 0.8177 | 1.6117 | 0.0968 | 30.0 min |
| chronos2 | 1.0309 | 2.1098 | 1.825 | **5.6797** | 0.8287 | 1.55 | 0.129 | 10.0 min |
| chronos2_mv | 1.0083 | 2.025 | 1.791 | **5.6128** | 0.8359 | 1.4981 | 0.0968 | 60.0 min |
| historical_average | 5.5993 | 9.2257 | 9.745 | **27.1128** | 0.0468 | 5.4718 | – | None min |
| persistence | 1.086 | 2.1254 | 1.886 | **5.036** | 0.8301 | 1.5746 | – | None min |
| random_forest | 1.081 | 2.1252 | 1.907 | **5.9285** | 0.8206 | 1.7659 | 0.3548 | 42.27 min |
| timesfm | 1.0192 | 2.0701 | 1.814 | **6.018** | 0.827 | 1.5096 | 0.0323 | 15.0 min |
| xgboost | 1.0794 | 2.1351 | 1.925 | **6.1344** | 0.814 | 1.7638 | 0.4516 | 35.36 min |

## PEMS-BAY — 325 nodes, 120 test windows, seed 37

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| DCRNN | 1.018 | 2.1717 | 1.797 | **7.5067** | 0.7714 | 1.1738 | 0.0789 | 20.0 min |
| GWNet | 1.0225 | 2.1699 | 1.79 | **6.586** | 0.8076 | 1.1439 | 0.0789 | 13.33 min |
| STID | 1.048 | 2.2509 | 1.97 | **9.3713** | 0.7136 | 1.0921 | 0.0526 | 17.5 min |
| chronos | 1.4413 | 2.9628 | 2.404 | **5.4345** | 0.7261 | 3.0109 | 0.1842 | 42.86 min |
| chronos2 | 1.2854 | 2.8332 | 2.164 | **5.1815** | 0.7228 | 2.4989 | 0.2632 | 34.0 min |
| chronos2_mv | 1.1813 | 2.6101 | 2.015 | **5.3094** | 0.7329 | 1.9081 | 0.0789 | 41.67 min |
| historical_average | 2.0334 | 3.9122 | 3.983 | **20.6023** | 0.2065 | 1.6731 | – | None min |
| persistence | 1.3399 | 2.9882 | 2.244 | **4.8158** | 0.7254 | 2.1571 | – | None min |
| random_forest | 1.2266 | 2.6283 | 2.098 | **5.7423** | 0.7524 | 2.0117 | 0.2105 | 21.88 min |
| timesfm | 1.2279 | 2.7986 | 2.079 | **5.1382** | 0.7321 | 1.9888 | 0.0789 | 35.0 min |
| xgboost | 1.2088 | 2.6022 | 2.095 | **6.0418** | 0.7392 | 1.9378 | 0.1316 | 14.0 min |

## PEMS-BAY — 80 nodes, 120 test windows, seed 11

Context 96 steps; chronological 70 / 10 / 20; a CONTIGUOUS block of consecutive windows from the TEST region, so onset transitions are real. Congestion: 0.6 x per-node free-flow (85th percentile of that node's TRAIN-split observed values). values of 0.0 are sensor outages and are excluded from every metric.

| model | MAE@15 | RMSE@15 | MAPE@15 | congestion MAE@15 | F1@15 | MAE@60 | onset detection | mean lead |
|---|---|---|---|---|---|---|---|---|
| GWNet | 0.9474 | 1.781 | 1.551 | **6.0992** | 0.7761 | 1.3607 | 1.0 | 60.0 min |
| STID | 0.9183 | 1.7278 | 1.514 | **6.7948** | 0.752 | 1.3322 | 1.0 | 55.0 min |
| chronos | 1.2749 | 2.4072 | 2.111 | **10.1907** | 0.6964 | 3.1181 | 0.1818 | 32.5 min |
| historical_average | 1.649 | 3.4088 | 2.966 | **26.8472** | 0.0 | 2.1533 | – | None min |
| persistence | 1.1805 | 2.2168 | 1.961 | **10.0209** | 0.6981 | 2.4422 | – | None min |
| random_forest | 1.146 | 2.1597 | 1.922 | **10.8487** | 0.6429 | 2.3926 | 0.5455 | 55.0 min |
| xgboost | 1.1291 | 2.1429 | 1.907 | **11.2382** | 0.6422 | 2.3254 | 0.9091 | 54.0 min |

Regenerate: `python -m app.forecasting.evaluation.evaluate_models --all`. Machine-readable: `model_comparison.json`.
