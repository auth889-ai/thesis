# Integrated chain — forecast to control, measured

Run `chain_20260904T061203Z_sw_compliance_c010_ideal_04d4de`, generated 2026-09-04T06:13:15.585482+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 10%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 215.07 | -1.68 % | 358.7 | -1.65 % | 580.8 | 50300 | -12.08 % | 56.67 | 97.6 | 1679.2 | 4.2 | 993.0 | 0.0 |
| **prediction_aware** | 213.83 | -2.24 % | 361.5 | -0.88 % | 594.8 | 55810 | -2.45 % | 50.67 | 100.7 | 1707.8 | 1.8 | 625.4 | 784.6 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-0.72, -4.07, 0.76, -1.62, -2.68] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [1.39, -4.7, -4.0, -2.19, -1.55] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
