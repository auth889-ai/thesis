# Phase 1 — traffic prediction: floors vs trained models vs published

## Where our results sit in the published field

Published 15-min MAE from STAEformer (CIKM 2023) Table 1, which retrained every baseline under one protocol. Note the field is saturated: four years moved the best METR-LA number from 2.69 to 2.65 (1.5 %), and ten architectures from 2018-2023 sit inside 2.67-2.85 — a spread plausibly within seed and hyperparameter noise.

| our model | dataset | our MAE@15 | band | gap to SOTA | published models it beats |
|---|---|---|---|---|---|

## Phase-1 gate: **NOT YET MET**

| check | ok | detail |
|---|---|---|
| G1_both_cities | NO |  |
| G2_floors | yes |  |
| G3_models | yes |  |
| G4_models_beat_floors | yes | every trained model beats every floor |
| G5_gwnet_reproduces_published | NO | no comparison |
| G6_checkpoint_inference | NO | none yet |

Regenerate: `python pipeline/forecasting/comparison_table.py`. Machine-readable: `phase1_comparison.json` / `.csv`.
