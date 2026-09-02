# Trained baselines on real cities (AWS GPU, official BasicTS configs, unmodified)

`ours` vs `published` is the reproduction check: the evaluation protocol was validated independently first (see benchmark_floors.md, our HA floor matches DCRNN's to 0.7 %), so a close match here means the training pipeline is correct too.

| model | dataset | horizon | MAE | published MAE | diff | RMSE | MAPE % | published MAPE % |
|---|---|---|---|---|---|---|---|---|
| GWNet | METR-LA | 15 min | 2.719 | 2.69 | +1.1 % | 5.183 | 7.02 | 6.90 |
| GWNet | METR-LA | 30 min | 3.111 | 3.07 | +1.3 % | 6.225 | 8.45 | 8.37 |
| GWNet | METR-LA | 60 min | 3.595 | 3.53 | +1.8 % | 7.423 | 10.05 | 10.01 |
| GWNet | PEMS-BAY | 5 min | 0.855 | – | – | 1.547 | 1.64 | – |
| GWNet | PEMS-BAY | 15 min | 1.308 | 1.30 | +0.6 % | 2.744 | 2.70 | 2.73 |
| GWNet | PEMS-BAY | 30 min | 1.638 | 1.63 | +0.5 % | 3.693 | 3.63 | 3.67 |
| GWNet | PEMS-BAY | 60 min | 1.945 | 1.95 | -0.2 % | 4.460 | 4.55 | 4.63 |
| STID | METR-LA | 15 min | 2.825 | – | – | 5.563 | 7.69 | – |
| STID | METR-LA | 30 min | 3.214 | – | – | 6.665 | 9.55 | – |
| STID | METR-LA | 60 min | 3.593 | – | – | 7.646 | 11.31 | – |
| STID | PEMS-BAY | 5 min | 0.857 | – | – | 1.572 | 1.64 | – |
| STID | PEMS-BAY | 15 min | 1.318 | – | – | 2.789 | 2.77 | – |
| STID | PEMS-BAY | 30 min | 1.644 | – | – | 3.738 | 3.75 | – |
| STID | PEMS-BAY | 60 min | 1.920 | – | – | 4.409 | 4.55 | – |

Compare against `predict/results/benchmark_floors.md` (the floors these must beat) and the published numbers cited there.

Regenerate: `python predict/aws_train.py --launch` then `--collect`.
