# Congestion-aware forecasting metrics

Average MAE is dominated by free-flow bins. These are the numbers a routing system depends on: error *during congestion*, whether congestion is detected at all, and how early it is flagged.

Congestion = speed below a per-sensor threshold (a share of that sensor's own free-flow speed, taken as the 85th percentile of its TRAIN-split observed speed). Sensor outages (encoded 0.0) are excluded from every metric.


## METR-LA

Threshold rule: 0.6 x per-sensor free-flow (85th pct of TRAIN-split observed speed); per-sensor cut 21.73-42.0 mph (median 39.82). 11.8% of observed bins are congested.

| model | horizon | MAE | congestion MAE | free-flow MAE | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| GWNet | 5 min | 2.2611 | **4.407** | 1.9746 | 0.8983 | 0.9066 | **0.9024** |
| GWNet | 15 min | 2.793 | **6.7833** | 2.2598 | 0.8657 | 0.8335 | **0.8493** |
| GWNet | 30 min | 3.2074 | **8.712** | 2.4713 | 0.8372 | 0.7781 | **0.8066** |
| GWNet | 60 min | 3.6419 | **10.6252** | 2.7173 | 0.8132 | 0.7215 | **0.7646** |

### Congestion warning lead time

First warning = the earliest horizon that flags the onset. Sustained = the warning must hold at every horizon from 5 min up to it, so one lucky long-range flag cannot be reported as an hour of notice.

| model | onsets | warned | detection rate | mean first warning | median first | mean SUSTAINED | max possible |
|---|---|---|---|---|---|---|---|
| GWNet | 464 | 337 | 0.7263 | **46.87 min** | 60.0 min | 32.3 min | 60 min |

Regenerate: `python pipeline/forecasting/congestion_metrics.py --all`. Machine-readable: `congestion_metrics.json`.
