# Phase 1 — traffic prediction: floors vs trained models vs published

## METR-LA

| model | kind | MAE@5min | MAE@15min | MAE@30min | MAE@60min | published MAE@15 | diff |
|---|---|---|---|---|---|---|---|
| **global_mean** | floor | 9.456 | 9.451 | 9.450 | 9.457 | – | – |
| **historical_average** | floor | 4.189 | 4.189 | 4.189 | 4.189 | – | – |
| **persistence** | floor | 2.795 | 3.460 | 4.147 | 5.308 | – | – |
| **seasonal_naive** | floor | 5.329 | 5.329 | 5.329 | 5.329 | – | – |
| **GWNet** | trained | – | 2.719 | 3.111 | 3.595 | 2.69 | +1.1 % |
| **STAEformer** | trained | 2.267 | 2.674 | 2.985 | 3.350 | – | – |
| **STID** | trained | – | 2.825 | 3.214 | 3.593 | – | – |

## PEMS-BAY

| model | kind | MAE@5min | MAE@15min | MAE@30min | MAE@60min | published MAE@15 | diff |
|---|---|---|---|---|---|---|---|
| **global_mean** | floor | 5.666 | 5.666 | 5.666 | 5.666 | – | – |
| **historical_average** | floor | 3.021 | 3.021 | 3.021 | 3.021 | – | – |
| **persistence** | floor | 0.971 | 1.590 | 2.170 | 3.040 | – | – |
| **seasonal_naive** | floor | 2.812 | 2.812 | 2.812 | 2.812 | – | – |
| **GWNet** | trained | 0.855 | 1.308 | 1.638 | 1.945 | 1.30 | +0.6 % |
| **STID** | trained | 0.857 | 1.318 | 1.644 | 1.920 | – | – |

## Where our results sit in the published field

Published 15-min MAE from STAEformer (CIKM 2023) Table 1, which retrained every baseline under one protocol. Note the field is saturated: four years moved the best METR-LA number from 2.69 to 2.65 (1.5 %), and ten architectures from 2018-2023 sit inside 2.67-2.85 — a spread plausibly within seed and hyperparameter noise.

| our model | dataset | our MAE@15 | band | gap to SOTA | published models it beats |
|---|---|---|---|---|---|
| **GWNet** | METR-LA | 2.719 | respectable published baseline | +2.6 % | STGCN (IJCAI 2018), GTS (ICLR 2021), GMAN (AAAI 2020), STNorm (KDD 2021), STID (CIKM 2022) +3 more |
| **STAEformer** | METR-LA | 2.674 | respectable published baseline | +0.9 % | Graph WaveNet (IJCAI 2019), MTGNN (KDD 2020), STGCN (IJCAI 2018), GTS (ICLR 2021), GMAN (AAAI 2020) +5 more |
| **STID** | METR-LA | 2.825 | respectable published baseline | +6.6 % | PDFormer (AAAI 2023), AGCRN (NeurIPS 2020), HI (naive) (-) |
| **GWNet** | PEMS-BAY | 1.308 | state of the art | +0.6 % | STAEformer (CIKM 2023), DCRNN (ICLR 2018), HI (naive) (-) |
| **STID** | PEMS-BAY | 1.318 | respectable published baseline | +1.4 % | DCRNN (ICLR 2018), HI (naive) (-) |

## Phase-1 gate: **PASS**

| check | ok | detail |
|---|---|---|
| G1_both_cities | yes | METR-LA, PEMS-BAY |
| G2_floors | yes | METR-LA/global_mean, METR-LA/historical_average, METR-LA/persistence, METR-LA/seasonal_naive, PEMS-BAY/global_mean, PEMS-BAY/historical_average, PEMS- |
| G3_models | yes | METR-LA/GWNet, METR-LA/STAEformer, METR-LA/STID, PEMS-BAY/GWNet, PEMS-BAY/STID |
| G4_models_beat_floors | yes | every trained model beats every floor |
| G5_gwnet_reproduces_published | yes | METR-LA@15min +1.1 %, METR-LA@30min +1.3 %, METR-LA@60min +1.8 %, PEMS-BAY@15min +0.6 %, PEMS-BAY@30min +0.5 %, PEMS-BAY@60min -0.2 % |
| G6_checkpoint_inference | yes | STID/PEMS-BAY, GWNet/PEMS-BAY, GWNet/METR-LA, STID/METR-LA |

Regenerate: `python src/pipeline/forecasting/comparison_table.py`. Machine-readable: `phase1_comparison.json` / `.csv`.
