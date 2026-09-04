# Integrated chain — forecast to control, measured

Run `chain_20260904T061725Z_sw_compliance_c080_ideal_82c96b`, generated 2026-09-04T06:23:08.330147+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 80%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 218.74 | +0.00 % | 364.7 | +0.00 % | 611.6 | 57210 | +0.00 % | 57.93 | 102.1 | 1684.6 | 1.8 | 0.0 | 0.0 |
| **reactive** | 214.0 | -2.17 % | 346.8 | -4.91 % | 610.8 | 59627 | +4.22 % | 92.91 | 107.5 | 1609.6 | 14.6 | 8717.8 | 0.0 |
| **prediction_aware** | 247.32 | +13.07 % | 367.1 | +0.66 % | 726.0 | 76943 | +34.49 % | 187.77 | 130.9 | 1345.2 | 31.8 | 4995.2 | 6169.4 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-1.15, 3.66, -7.73, 2.8, -8.46] | 3/5 | **NOT_ESTABLISHED** — only 3 of 5 paired seeds improved; a mean that the seeds do not support is not a result |
| prediction_aware | [14.35, 11.3, 10.03, 18.27, 11.49] | 0/5 | **NOT_ESTABLISHED** — only 0 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
