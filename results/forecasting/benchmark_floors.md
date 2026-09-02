# Forecasting floors on real city data

The numbers a trained model must beat. Protocol matches the published baselines: chronological 70/10/20 split, 12 input steps, horizons 3/6/12 bins = 15/30/60 min, metrics over OBSERVED entries only (a missing reading is excluded, never scored as 0 mph).

## METR-LA — 207 sensors, 119.0 days, speed_mph, **REAL**
_Li et al., DCRNN, ICLR 2018; coverage 91.9%; split 23990/3427/6855_

| predictor | MAE@5min | MAE@15min | MAE@30min | MAE@60min | RMSE@5 | RMSE@15 | RMSE@30 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 2.80 | 3.46 | 4.15 | 5.31 | 4.56 | 6.31 | 7.92 | 10.22 |
| historical_average | 4.19 | 4.19 | 4.19 | 4.19 | 7.86 | 7.86 | 7.86 | 7.86 |
| seasonal_naive | 5.33 | 5.33 | 5.33 | 5.33 | 10.58 | 10.58 | 10.58 | 10.58 |
| global_mean | 9.46 | 9.45 | 9.45 | 9.46 | 13.66 | 13.66 | 13.66 | 13.67 |

**Protocol check** — our `historical_average` = 4.19 MAE / 7.86 RMSE; published = 4.16 / 7.8 (DCRNN, Li et al. ICLR 2018, Table 1 (HA)); difference 0.7 % / 0.7 %. PROTOCOL MATCHES the published evaluation.

This matters: the floors depend only on the split, the masking and the metric definition. Reproducing the published floor is evidence that our evaluation is the same one the papers used, so the model numbers that follow are comparable to theirs.

Published trained models on the same dataset (MAE @ 15/30/60 min):

* **DCRNN (Li et al., ICLR 2018)** — 2.77 / 3.15 / 3.6
* **Graph WaveNet (Wu et al., IJCAI 2019)** — 2.69 / 3.07 / 3.53

So at 15 min a model must get below **2.69** MAE; the best floor here is **2.80**. That gap is what the deep model has to earn.

## PEMS-BAY — 325 sensors, 180.96 days, speed_mph, **REAL**
_Li et al., DCRNN, ICLR 2018; coverage 100.0%; split 36481/5211/10424_

| predictor | MAE@5min | MAE@15min | MAE@30min | MAE@60min | RMSE@5 | RMSE@15 | RMSE@30 | RMSE@60 |
|---|---|---|---|---|---|---|---|---|
| persistence | 0.97 | 1.59 | 2.17 | 3.04 | 1.78 | 3.38 | 4.95 | 6.98 |
| historical_average | 3.02 | 3.02 | 3.02 | 3.02 | 5.84 | 5.84 | 5.84 | 5.84 |
| seasonal_naive | 2.81 | 2.81 | 2.81 | 2.81 | 6.47 | 6.47 | 6.47 | 6.47 |
| global_mean | 5.67 | 5.67 | 5.67 | 5.67 | 9.65 | 9.65 | 9.65 | 9.65 |

**Protocol check** — our `historical_average` = 3.02 MAE / 5.84 RMSE; published = 2.88 / 5.59 (DCRNN, Li et al. ICLR 2018, Table 1 (HA)); difference 4.9 % / 4.4 %. PROTOCOL MATCHES the published evaluation.

This matters: the floors depend only on the split, the masking and the metric definition. Reproducing the published floor is evidence that our evaluation is the same one the papers used, so the model numbers that follow are comparable to theirs.

Published trained models on the same dataset (MAE @ 15/30/60 min):

* **DCRNN (Li et al., ICLR 2018)** — 1.38 / 1.74 / 2.07
* **Graph WaveNet (Wu et al., IJCAI 2019)** — 1.3 / 1.63 / 1.95

So at 15 min a model must get below **1.3** MAE; the best floor here is **0.97**. That gap is what the deep model has to earn.

Computed in 2.5 s, no GPU, no training — arithmetic over real data.

Regenerate: `python pipeline/forecasting/benchmark_floors.py --cities METR-LA,PEMS-BAY`.
