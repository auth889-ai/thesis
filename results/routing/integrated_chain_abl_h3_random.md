# Integrated chain — forecast to control, measured

Run `chain_20260904T120730Z_abl_h3_random_fdb37b`, generated 2026-09-04T12:08:51.528535+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** random, horizon 15 min, a BASELINE. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint, propagated 3 hops).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 30%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 214.57 | -1.91 % | 360.7 | -1.10 % | 640.8 | 64317 | +12.42 % | 60.6 | 106.0 | 1701.4 | 5.8 | 3044.6 | 0.0 |
| **prediction_aware** | 219.01 | +0.12 % | 357.2 | -2.06 % | 636.8 | 58783 | +2.75 % | 81.69 | 102.6 | 1640.6 | 14.6 | 1900.8 | 2273.2 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-2.93, -4.85, -4.45, 7.34, -4.58] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [-3.16, -2.69, 3.22, 3.91, -0.72] | 3/5 | **NOT_ESTABLISHED** — only 3 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
