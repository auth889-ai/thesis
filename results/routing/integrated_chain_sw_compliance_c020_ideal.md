# Integrated chain — forecast to control, measured

Run `chain_20260904T061315Z_sw_compliance_c020_ideal_c001e8`, generated 2026-09-04T06:14:31.756748+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 20%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 214.77 | -1.81 % | 358.6 | -1.67 % | 592.8 | 56525 | -1.20 % | 59.79 | 100.9 | 1681.8 | 4.6 | 2032.4 | 0.0 |
| **prediction_aware** | 212.71 | -2.76 % | 358.1 | -1.81 % | 602.0 | 57555 | +0.60 % | 55.75 | 101.3 | 1700.4 | 6.4 | 1249.6 | 1543.4 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [1.14, -3.5, -2.22, -1.91, -2.46] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [-1.02, -3.86, -2.54, -1.2, -5.1] | 5/5 | **IMPROVES** — every paired seed improved |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
