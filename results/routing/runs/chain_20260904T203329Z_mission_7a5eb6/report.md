# Integrated chain — forecast to control, measured

Run `chain_20260904T203329Z_mission_7a5eb6`, generated 2026-09-04T20:34:22.071060+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 30%; horizon 1800 s; seeds [11, 12, 13].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.69 | +0.00 % | 365.5 | +0.00 % | 609.0 | 58075 | +0.00 % | 58.13 | 102.8 | 1684.3 | 2.3 | 0.0 | 0.0 |
| **reactive** | 209.74 | -4.09 % | 355.3 | -2.79 % | 585.7 | 56707 | -2.36 % | 50.49 | 100.5 | 1723.3 | 4.7 | 2887.3 | 0.0 |
| **prediction_aware** | 219.27 | +0.27 % | 358.7 | -1.86 % | 639.7 | 62454 | +7.54 % | 84.39 | 105.3 | 1634.0 | 17.7 | 1838.3 | 2264.7 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-2.93, -4.85, -4.45] | 3/3 | **IMPROVES** — every paired seed improved |
| prediction_aware | [1.77, 2.09, -3.03] | 1/3 | **NOT_ESTABLISHED** — only 1 of 3 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
