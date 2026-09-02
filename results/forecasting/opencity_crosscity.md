# Cross-city generalization — OpenCity foundation model

Official `HKUDS/OpenCity` at the pinned SHA, evaluated with the authors' own commands and their released `OpenCity-plus` weights, used as published. No foundation model is pre-trained here.

## The distinction that decides whether this is a zero-shot claim at all

OpenCity's pre-training corpus is recorded in a commented-out `dataset_use` line in `conf/general_conf/pretrain.conf`, and it **includes METR_LA and PEMS_BAY**. Evaluating on those cities is therefore *not* zero-shot, however good the number looks. Only cities absent from that list support a zero-shot claim — which is why the authors' own README example evaluates on PEMS07M.

**This is the trap the plan for this chapter walked into:** two of the three cities originally named for the cross-city comparison are in OpenCity's training data.

## Arms

| arm | what it is |
|---|---|
| city-specific | Graph WaveNet / STID trained on that city by us (the strong baseline) |
| OpenCity zero-shot | released weights, `-mode test`, never shown this city |
| OpenCity fine-tuned | released weights, `-mode eval` — upstream freezes everything except `predictor.linear` and trains that head on the target city |

## Results

| dataset | exposure | arm | MAE | RMSE | MAPE | status |
|---|---|---|---|---|---|---|
| PEMS07M | **HELD OUT** | zero_shot | 4.5 | 8.21 | 12.1966 | OK |
| TrafficNJ | **HELD OUT** | zero_shot | – | – | – | CUDA_OOM |
| TrafficSH | **HELD OUT** | zero_shot | – | – | – | CUDA_OOM |
| TrafficTJ | **HELD OUT** | zero_shot | – | – | – | CUDA_OOM |

## Our city-specific models, for comparison

Trained by us on that city, MAE at 15 min. These are the numbers OpenCity has to beat to make cross-city pre-training worthwhile on a city where labelled history already exists.

| dataset | model | MAE@15min | in OpenCity's pre-training? |
|---|---|---|---|
| METR_LA | STAEformer | 2.6738 | YES — not zero-shot |
| METR_LA | GWNet | 2.719 | YES — not zero-shot |
| METR_LA | STID | 2.8247 | YES — not zero-shot |
| PEMS_BAY | GWNet | 1.3083 | YES — not zero-shot |
| PEMS_BAY | STID | 1.3183 | YES — not zero-shot |

**These two tables are not directly comparable and must not be presented as if they were.** OpenCity is scored on its own 288-step horizon under the authors' split; our models are scored at 15 minutes under the DCRNN protocol. A like-for-like comparison needs both models evaluated under one protocol on one city, which is a separate piece of work and is not claimed here.


Rows marked *seen in pre-training* are reported for completeness and must not be quoted as evidence of cross-city generalization.

Regenerate: `python pipeline/forecasting/opencity_crosscity.py --all-zeroshot`. Machine-readable: `opencity_crosscity.json`.
