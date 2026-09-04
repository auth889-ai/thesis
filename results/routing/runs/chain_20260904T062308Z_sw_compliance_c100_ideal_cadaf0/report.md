# Integrated chain — forecast to control, measured

Run `chain_20260904T062308Z_sw_compliance_c100_ideal_cadaf0`, generated 2026-09-04T08:25:03.094408+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 100%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 228.86 | +4.63 % | 340.4 | -6.66 % | 627.8 | 58608 | +2.44 % | 141.55 | 109.2 | 1481.4 | 21.4 | 11770.2 | 0.0 |
| **prediction_aware** | 243.2 | +11.18 % | 385.2 | +5.62 % | 838.6 | 100189 | +75.12 % | 174.41 | 155.2 | 1341.8 | 21.2 | 6235.6 | 7712.6 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-3.89, 7.48, -3.97, 3.29, 19.91] | 2/5 | **NOT_ESTABLISHED** — only 2 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [13.82, 2.85, 10.28, 18.97, 10.27] | 0/5 | **NOT_ESTABLISHED** — only 0 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
