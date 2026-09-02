# Congestion-aware forecasting metrics

Average MAE is dominated by free-flow bins. These are the numbers a routing system depends on: error *during congestion*, whether congestion is detected at all, and how early it is flagged.

Congestion = speed below a per-sensor threshold (a share of that sensor's own free-flow speed, taken as the 85th percentile of its TRAIN-split observed speed). Sensor outages (encoded 0.0) are excluded from every metric.


## METR-LA

Threshold rule: 0.6 x per-sensor free-flow (85th pct of TRAIN-split observed speed); per-sensor cut 21.73-42.0 mph (median 39.82). 11.2% of observed bins are congested.

| model | horizon | MAE | congestion MAE | free-flow MAE | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| GWNet | 5 min | 2.2394 | **4.6003** | 1.9423 | 0.9002 | 0.9021 | **0.9012** |
| GWNet | 15 min | 2.7115 | **6.9204** | 2.1818 | 0.8722 | 0.8299 | **0.8505** |
| GWNet | 30 min | 3.0954 | **8.8997** | 2.365 | 0.843 | 0.7731 | **0.8065** |
| GWNet | 60 min | 3.5589 | **11.5042** | 2.5596 | 0.8151 | 0.6953 | **0.7504** |
| STID | 5 min | 2.3247 | **5.3088** | 1.9492 | 0.9083 | 0.8723 | **0.8899** |
| STID | 15 min | 2.8261 | **7.9737** | 2.1784 | 0.8779 | 0.7877 | **0.8303** |
| STID | 30 min | 3.2053 | **10.3234** | 2.3095 | 0.8591 | 0.7173 | **0.7818** |
| STID | 60 min | 3.572 | **12.4166** | 2.4595 | 0.8286 | 0.658 | **0.7335** |

### Congestion warning lead time

First warning = the earliest horizon that flags the onset. Sustained = the warning must hold at every horizon from 5 min up to it, so one lucky long-range flag cannot be reported as an hour of notice.

| model | onsets | warned | detection rate | mean first warning | median first | mean SUSTAINED | max possible |
|---|---|---|---|---|---|---|---|
| GWNet | 10757 | 7604 | 0.7069 | **47.45 min** | 60.0 min | 35.81 min | 60 min |
| STID | 10757 | 6546 | 0.6085 | **48.32 min** | 60.0 min | 40.86 min | 60 min |

## PEMS-BAY

Threshold rule: 0.6 x per-sensor free-flow (85th pct of TRAIN-split observed speed); per-sensor cut 37.32-43.32 mph (median 40.74). 5.2% of observed bins are congested.

| model | horizon | MAE | congestion MAE | free-flow MAE | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| GWNet | 5 min | 0.8553 | **2.046** | 0.7901 | 0.9414 | 0.9495 | **0.9454** |
| GWNet | 15 min | 1.3083 | **4.4348** | 1.1372 | 0.8839 | 0.8704 | **0.8771** |
| GWNet | 30 min | 1.6377 | **6.6528** | 1.3632 | 0.8405 | 0.7981 | **0.8188** |
| GWNet | 60 min | 1.9454 | **8.7381** | 1.5736 | 0.8098 | 0.7289 | **0.7673** |
| STID | 5 min | 0.8572 | **2.1032** | 0.789 | 0.9432 | 0.9439 | **0.9435** |
| STID | 15 min | 1.3182 | **4.8013** | 1.1276 | 0.8926 | 0.8445 | **0.8679** |
| STID | 30 min | 1.6439 | **7.3411** | 1.332 | 0.8599 | 0.7607 | **0.8073** |
| STID | 60 min | 1.9202 | **9.045** | 1.5302 | 0.8263 | 0.718 | **0.7683** |

### Congestion warning lead time

First warning = the earliest horizon that flags the onset. Sustained = the warning must hold at every horizon from 5 min up to it, so one lucky long-range flag cannot be reported as an hour of notice.

| model | onsets | warned | detection rate | mean first warning | median first | mean SUSTAINED | max possible |
|---|---|---|---|---|---|---|---|
| GWNet | 9990 | 7348 | 0.7355 | **38.71 min** | 50.0 min | 14.94 min | 60 min |
| STID | 9990 | 7005 | 0.7012 | **40.77 min** | 55.0 min | 11.31 min | 60 min |

Regenerate: `python pipeline/forecasting/congestion_metrics.py --all`. Machine-readable: `congestion_metrics.json`.
