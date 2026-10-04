# Trained baselines on real cities (AWS GPU, official BasicTS configs, unmodified)

`ours` vs `published` is the reproduction check: the evaluation protocol was validated independently first (see benchmark_floors.md, our HA floor matches DCRNN's to 0.7 %), so a close match here means the training pipeline is correct too.

| model | dataset | horizon | MAE | published MAE | diff | RMSE | MAPE % | published MAPE % |
|---|---|---|---|---|---|---|---|---|
| D2STGNN | METR-LA | 5 min | 2.084 | – | – | 3.627 | 4.92 | – |
| D2STGNN | METR-LA | 15 min | 2.563 | 2.56 | +0.1 % | 4.932 | 6.51 | 6.48 |
| D2STGNN | METR-LA | 30 min | 2.914 | 2.90 | +0.5 % | 5.954 | 7.89 | 7.78 |
| D2STGNN | METR-LA | 60 min | 3.355 | 3.35 | +0.1 % | 7.074 | 9.60 | 9.40 |
| DCRNN | METR-LA | 5 min | 2.176 | – | – | 3.773 | 5.18 | – |
| DCRNN | METR-LA | 15 min | 2.672 | 2.77 | -3.5 % | 5.176 | 6.86 | 7.30 |
| DCRNN | METR-LA | 30 min | 3.078 | 3.15 | -2.3 % | 6.313 | 8.41 | 8.80 |
| DCRNN | METR-LA | 60 min | 3.572 | 3.60 | -0.8 % | 7.558 | 10.34 | 10.50 |
| DCRNN | PEMS-BAY | 5 min | 0.848 | – | – | 1.532 | 1.63 | – |
| DCRNN | PEMS-BAY | 15 min | 1.310 | 1.38 | -5.1 % | 2.755 | 2.73 | 2.95 |
| DCRNN | PEMS-BAY | 30 min | 1.655 | 1.74 | -4.9 % | 3.775 | 3.75 | 3.97 |
| DCRNN | PEMS-BAY | 60 min | 1.972 | 2.07 | -4.7 % | 4.616 | 4.74 | 4.74 |
| GWNet | METR-LA | 15 min | 2.719 | 2.69 | +1.1 % | 5.183 | 7.02 | 6.90 |
| GWNet | METR-LA | 30 min | 3.111 | 3.07 | +1.3 % | 6.225 | 8.45 | 8.37 |
| GWNet | METR-LA | 60 min | 3.595 | 3.53 | +1.8 % | 7.423 | 10.05 | 10.01 |
| GWNet | PEMS-BAY | 5 min | 0.855 | – | – | 1.547 | 1.64 | – |
| GWNet | PEMS-BAY | 15 min | 1.308 | 1.30 | +0.6 % | 2.744 | 2.70 | 2.73 |
| GWNet | PEMS-BAY | 30 min | 1.638 | 1.63 | +0.5 % | 3.693 | 3.63 | 3.67 |
| GWNet | PEMS-BAY | 60 min | 1.945 | 1.95 | -0.2 % | 4.460 | 4.55 | 4.63 |
| MegaCRN | METR-LA | 5 min | 2.141 | – | – | 3.705 | 5.08 | – |
| MegaCRN | METR-LA | 15 min | 2.631 | 2.52 | +4.4 % | 5.049 | 6.73 | 6.44 |
| MegaCRN | METR-LA | 30 min | 3.018 | 2.93 | +3.0 % | 6.124 | 8.23 | 7.96 |
| MegaCRN | METR-LA | 60 min | 3.476 | 3.38 | +2.8 % | 7.298 | 10.04 | 9.72 |
| STAEformer | METR-LA | 5 min | 2.267 | – | – | 3.970 | 5.51 | – |
| STAEformer | METR-LA | 15 min | 2.674 | – | – | 5.167 | 6.96 | – |
| STAEformer | METR-LA | 30 min | 2.985 | – | – | 6.068 | 8.25 | – |
| STAEformer | METR-LA | 60 min | 3.350 | – | – | 7.063 | 9.82 | – |
| STID | METR-LA | 15 min | 2.825 | – | – | 5.563 | 7.69 | – |
| STID | METR-LA | 30 min | 3.214 | – | – | 6.665 | 9.55 | – |
| STID | METR-LA | 60 min | 3.593 | – | – | 7.646 | 11.31 | – |
| STID | PEMS-BAY | 5 min | 0.857 | – | – | 1.572 | 1.64 | – |
| STID | PEMS-BAY | 15 min | 1.318 | – | – | 2.789 | 2.77 | – |
| STID | PEMS-BAY | 30 min | 1.644 | – | – | 3.738 | 3.75 | – |
| STID | PEMS-BAY | 60 min | 1.920 | – | – | 4.409 | 4.55 | – |

Compare against `results/forecasting/benchmark_floors.md` (the floors these must beat) and the published numbers cited there.

Regenerate: `python -m app.forecasting.training.aws_train --launch` then `--collect`.
