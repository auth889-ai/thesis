# RQ1 forecasting — summary

- Los Angeles (METR-LA): at 60 minutes the best is D2STGNN at 3.779 mph mean absolute error, against 6.506 for persistence; the best zero-shot model is Chronos-2, all roads together (zero-shot) at 6.343.
- San Francisco Bay Area (PEMS-BAY): at 60 minutes the best is STID at 1.234 mph mean absolute error, against 2.05 for persistence; the best zero-shot model is Chronos-2, all roads together (zero-shot) at 1.959.
- Dhaka (DhaTraX, three camera sites, one day each), the best model other than persistence: at 15 minutes Chronos-Bolt-small (zero-shot) 2.225 km/h against persistence 2.385 (better); at 30 minutes Chronos-2 (zero-shot) 2.41 km/h against persistence 2.623 (better); at 60 minutes Chronos-2 (zero-shot) 2.877 km/h against persistence 2.717 (not better).

**Unseen city.** XGBoost trained on METR-LA (Los Angeles) and run unchanged on PEMS-BAY (San Francisco Bay Area) scores 2.76 mph at 60 minutes, against 2.35 when trained on PEMS-BAY itself: moving cities costs 17.4 %. The six graph models cannot move at all: each is fixed to METR-LA's 207 sensors.

**Why Dhaka differs.** Dhaka's speeds jump: 6.5-13.1 % of 5-minute steps change by more than 30 % of free-flow, against 0.7 % on a median METR-LA sensor-day and 0.0 % on PEMS-BAY. 2 of 3 sites vary more than a median Los Angeles sensor-day (coefficient of variation BM 0.51, BS 0.19, INT 0.49 against 0.229, and 0.1621 in the Bay Area); 3 of 3 remember less an hour ahead (autocorrelation at 60 minutes 0.08-0.3 against 0.3572 and 0.5766). So what a model learns from Los Angeles's smooth roads does not carry: XGBoost trained on METR-LA is 72.7 % worse than persistence in Dhaka at 60 minutes, while moving it to the Bay Area costs 17.4 %. And the models that win in Los Angeles (D2STGNN 3.779 against persistence 6.506 at 60 minutes) learned months of each sensor's history; a Dhaka camera site has one recorded day, so there is nothing to train them on, and only zero-shot models can be used.

## Los Angeles — METR-LA (mph, mean ± sd over seeds)

| Model | 15 min MAE | 30 min MAE | 60 min MAE | 60 min RMSE | 60 min MAPE % |
|---|---|---|---|---|---|
| D2STGNN | 2.938 ± 0.245 | 3.351 ± 0.252 | 3.779 ± 0.415 | 7.506 ± 0.95 | 11.669 ± 2.208 |
| STAEformer | 3.063 ± 0.212 | 3.447 ± 0.266 | 3.878 ± 0.53 | 7.709 ± 1.163 | 12.095 ± 2.636 |
| MegaCRN | 2.994 ± 0.251 | 3.452 ± 0.279 | 3.965 ± 0.494 | 7.926 ± 1.026 | 12.172 ± 2.209 |
| DCRNN | 3.046 ± 0.282 | 3.527 ± 0.331 | 4.091 ± 0.515 | 8.222 ± 1.064 | 12.889 ± 2.197 |
| STID | 3.291 ± 0.318 | 3.774 ± 0.396 | 4.22 ± 0.576 | 8.389 ± 1.158 | 14.273 ± 2.943 |
| GWNet | 3.183 ± 0.331 | 3.7 ± 0.403 | 4.249 ± 0.629 | 8.279 ± 1.39 | 13.83 ± 2.843 |
| Historical average (time of day + weekday) | 4.886 ± 0.46 | 4.893 ± 0.478 | 4.878 ± 0.566 | 8.469 ± 0.909 | 17.001 ± 2.883 |
| Historical average (time of day) | 5.706 ± 0.654 | 5.712 ± 0.541 | 5.723 ± 0.46 | 9.704 ± 0.373 | 21.845 ± 1.435 |
| Chronos-2, all roads together (zero-shot) | 3.72 ± 0.246 | 4.683 ± 0.197 | 6.343 ± 0.247 | 11.779 ± 0.406 | 19.492 ± 2.907 |
| Persistence | 4.031 ± 0.315 | 4.946 ± 0.272 | 6.506 ± 0.372 | 11.853 ± 0.48 | 18.954 ± 2.523 |
| TimesFM 2.5 (zero-shot) | 3.975 ± 0.227 | 5.03 ± 0.152 | 6.719 ± 0.156 | 12.317 ± 0.16 | 21.572 ± 2.831 |
| Random forest | 4.008 ± 0.343 | 5.101 ± 0.356 | 6.743 ± 0.433 | 11.013 ± 0.643 | 22.788 ± 2.04 |
| XGBoost | 4.022 ± 0.366 | 5.119 ± 0.343 | 6.766 ± 0.468 | 11.145 ± 0.649 | 22.902 ± 2.094 |
| Chronos-2 (zero-shot) | 3.909 ± 0.205 | 5.016 ± 0.096 | 6.947 ± 0.098 | 12.953 ± 0.184 | 20.917 ± 2.274 |
| Chronos-Bolt-small (zero-shot) | 4.143 ± 0.3 | 5.348 ± 0.298 | 7.35 ± 0.509 | 12.769 ± 0.493 | 22.149 ± 2.305 |

## San Francisco Bay Area — PEMS-BAY (mph, mean ± sd over seeds)

| Model | 15 min MAE | 30 min MAE | 60 min MAE | 60 min RMSE | 60 min MAPE % |
|---|---|---|---|---|---|
| STID | 0.993 ± 0.048 | 1.135 ± 0.033 | 1.234 ± 0.123 | 2.598 ± 0.333 | 2.271 ± 0.437 |
| GWNet | 0.995 ± 0.027 | 1.15 ± 0.014 | 1.273 ± 0.113 | 2.743 ± 0.278 | 2.326 ± 0.418 |
| DCRNN | 0.992 ± 0.023 | 1.156 ± 0.018 | 1.31 ± 0.118 | 2.981 ± 0.145 | 2.43 ± 0.458 |
| Historical average (time of day + weekday) | 1.833 ± 0.373 | 1.807 ± 0.363 | 1.773 ± 0.381 | 3.225 ± 0.824 | 3.23 ± 1.028 |
| Chronos-2, all roads together (zero-shot) | 1.121 ± 0.098 | 1.433 ± 0.18 | 1.959 ± 0.488 | 4.792 ± 1.457 | 3.877 ± 1.752 |
| TimesFM 2.5 (zero-shot) | 1.158 ± 0.12 | 1.468 ± 0.2 | 1.977 ± 0.462 | 4.833 ± 1.453 | 3.911 ± 1.656 |
| XGBoost | 1.162 ± 0.072 | 1.487 ± 0.109 | 1.997 ± 0.267 | 4.245 ± 0.77 | 3.741 ± 1.08 |
| Random forest | 1.175 ± 0.082 | 1.512 ± 0.128 | 2.038 ± 0.286 | 4.283 ± 0.758 | 3.796 ± 1.092 |
| Persistence | 1.226 ± 0.129 | 1.543 ± 0.198 | 2.05 ± 0.432 | 4.93 ± 1.24 | 3.862 ± 1.366 |
| Chronos-2 (zero-shot) | 1.206 ± 0.152 | 1.6 ± 0.288 | 2.316 ± 0.693 | 6.687 ± 3.439 | 4.538 ± 2.12 |
| Chronos-Bolt-small (zero-shot) | 1.278 ± 0.198 | 1.722 ± 0.37 | 2.566 ± 0.827 | 5.834 ± 2.072 | 4.676 ± 1.79 |
| Historical average (time of day) | 3.105 ± 2.167 | 3.091 ± 2.139 | 3.096 ± 2.071 | 5.569 ± 3.119 | 5.634 ± 3.441 |

## Dhaka — DhaTraX (km/h, mean ± sd over 3 sites)

| Model | 15 min | 30 min | 60 min |
|---|---|---|---|
| Persistence | 2.385 ± 0.558 | 2.623 ± 0.514 | 2.717 ± 0.674 |
| Chronos-2 (zero-shot) | 2.301 ± 0.323 | 2.41 ± 0.31 | 2.877 ± 0.43 |
| Chronos-Bolt-small (zero-shot) | 2.225 ± 0.333 | 2.422 ± 0.444 | 2.878 ± 0.552 |
| TimesFM 2.5 (zero-shot) | 2.328 ± 0.117 | 2.628 ± 0.334 | 2.948 ± 0.544 |
| random_forest (trained on METR-LA) | 2.465 ± 0.232 | 3.074 ± 0.238 | 4.157 ± 0.565 |
| xgboost (trained on METR-LA) | 2.523 ± 0.219 | 3.226 ± 0.236 | 4.691 ± 0.453 |

## Figures

- `results/forecasting/rq1/figures/rq1_error_vs_horizon.png`
- `results/forecasting/rq1/figures/rq1_unseen_city.png`
- `results/forecasting/rq1/figures/rq1_why_dhaka.png`
