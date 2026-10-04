# PatchSTG on LargeST — the authors' code, their split (6/2/2), their metric, 12-step average

| region | sensors | weights | MAE | RMSE | MAPE % | published MAE / RMSE / MAPE % | MAE gap | device | time |
|---|---|---|---|---|---|---|---|---|---|
| SD | 716 | authors' released checkpoint | 16.8506 | 29.5653 | 11.0075 | 16.9 / 29.27 / 11.23 | -0.29 % | cpu | 86.5 s |
| GBA | 2352 | authors' released checkpoint | 19.5658 | 33.0628 | 14.8939 | 19.5 / 33.16 / 14.64 | +0.34 % | cpu | 479.7 s |
| GLA | 3834 | authors' released checkpoint | 18.8908 | 31.9988 | 11.3391 | 18.96 / 32.33 / 11.44 | -0.36 % | cpu | 358.3 s |
| CA | 8600 | authors' released checkpoint | 17.6439 | 29.9393 | 12.3514 | 17.35 / 29.79 / 12.79 | +1.69 % | cpu | 1178.9 s |

Regenerate: `python -m app.forecasting.training.patchstg_official --region <SD|GBA|GLA|CA> [--mode train]`.
