# Live Dhaka congestion — arithmetic floors (REAL_LIVE, no model)

1020 captures -> 132 bins x 6 corridors over 11.0 h, coverage 73%; target = derived congestion level 0-3 (FREE_FLOW..SEVERE); chronological 70/30 split; gaps masked, never imputed.

| horizon | persistence MAE | historical-avg MAE | global-mean MAE | n pairs |
|---|---|---|---|---|
| 5 min | 0.093 | 0.162 | 0.162 | 216 |
| 15 min | 0.137 | 0.172 | 0.172 | 204 |
| 30 min | 0.182 | 0.213 | 0.213 | 192 |
| 60 min | 0.244 | 0.263 | 0.263 | 156 |

## How to read these numbers

The target is heavily imbalanced: **95 % of the 582 observations are FREE_FLOW** (FREE_FLOW 551, SLOW 22, CONGESTED 8, SEVERE 1). On a series that is mostly one class a constant predictor already scores a small MAE, so the absolute values above are NOT evidence of skill on their own -- the comparison between them is. Persistence beating the historical average at every horizon says short-term congestion is autocorrelated; both being small says Dhaka was mostly free-flowing here.

Only 31 readings (5 %) were SLOW or worse, so a learned model has few congestion events to learn from yet. Recording through more rush hours is what makes this dataset worth training on.

A learned forecaster must beat these on the same masked test region to be worth reporting.
Regenerate: `python pipeline/forecasting/live_state.py --report`.
