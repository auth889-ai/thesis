# Integrated chain — forecast to control, measured

Run `chain_20260904T121011Z_abl_h8_random_10e9fe`, generated 2026-09-04T12:11:31.564624+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** random, horizon 15 min, a BASELINE. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint, propagated 8 hops).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 30%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 214.57 | -1.91 % | 360.7 | -1.10 % | 640.8 | 64317 | +12.42 % | 60.6 | 106.0 | 1701.4 | 5.8 | 3044.6 | 0.0 |
| **prediction_aware** | 214.99 | -1.71 % | 354.2 | -2.88 % | 597.6 | 55232 | -3.46 % | 69.57 | 100.5 | 1664.4 | 11.2 | 1957.0 | 2273.2 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-2.93, -4.85, -4.45, 7.34, -4.58] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [-0.4, 3.64, -5.55, -0.88, -5.44] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
