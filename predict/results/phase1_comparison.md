# Phase 1 — traffic prediction: floors vs trained models vs published

## METR-LA

| model | kind | MAE@5min | MAE@15min | MAE@30min | MAE@60min | published MAE@15 | diff |
|---|---|---|---|---|---|---|---|
| **global_mean** | floor | 9.456 | 9.451 | 9.450 | 9.457 | – | – |
| **historical_average** | floor | 4.189 | 4.189 | 4.189 | 4.189 | – | – |
| **persistence** | floor | 2.795 | 3.460 | 4.147 | 5.308 | – | – |
| **seasonal_naive** | floor | 5.329 | 5.329 | 5.329 | 5.329 | – | – |
| **GWNet** | trained | – | 2.719 | 3.111 | 3.595 | 2.69 | +1.1 % |
| **STID** | trained | – | 2.825 | 3.214 | 3.593 | – | – |

## PEMS-BAY

| model | kind | MAE@5min | MAE@15min | MAE@30min | MAE@60min | published MAE@15 | diff |
|---|---|---|---|---|---|---|---|
| **global_mean** | floor | 5.666 | 5.666 | 5.666 | 5.666 | – | – |
| **historical_average** | floor | 3.021 | 3.021 | 3.021 | 3.021 | – | – |
| **persistence** | floor | 0.971 | 1.590 | 2.170 | 3.040 | – | – |
| **seasonal_naive** | floor | 2.812 | 2.812 | 2.812 | 2.812 | – | – |

## Phase-1 gate: **NOT YET MET**

| check | ok | detail |
|---|---|---|
| G1_both_cities | yes | METR-LA, PEMS-BAY |
| G2_floors | yes | METR-LA/global_mean, METR-LA/historical_average, METR-LA/persistence, METR-LA/seasonal_naive, PEMS-BAY/global_mean, PEMS-BAY/historical_average, PEMS- |
| G3_models | NO | METR-LA/GWNet, METR-LA/STID |
| G4_models_beat_floors | yes | every trained model beats every floor |
| G5_gwnet_reproduces_published | yes | METR-LA@15min +1.1 %, METR-LA@30min +1.3 %, METR-LA@60min +1.8 % |
| G6_checkpoint_inference | yes | GWNet/METR-LA, STID/METR-LA |

Regenerate: `python predict/comparison_table.py`. Machine-readable: `phase1_comparison.json` / `.csv`.
