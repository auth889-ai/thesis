# PatchSTG on LargeST — the authors' code, their split (6/2/2), their metric, 12-step average

| region | sensors | weights | MAE | RMSE | MAPE % | published MAE / RMSE / MAPE % | MAE gap | device | time |
|---|---|---|---|---|---|---|---|---|---|
| SD | 716 | authors' released checkpoint | 16.8506 | 29.5653 | 11.0075 | 16.9 / 29.27 / 11.23 | -0.29 % | cpu | 86.5 s |

Regenerate: `python -m app.forecasting.training.patchstg_official --region <SD|GBA|GLA|CA> [--mode train]`.
