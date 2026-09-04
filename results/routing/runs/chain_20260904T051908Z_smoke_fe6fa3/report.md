# Integrated chain — forecast to control, measured

Run `chain_20260904T051908Z_smoke_fe6fa3`, generated 2026-09-04T05:19:30.923002+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. Input [525, 6] over 6 nodes, congestion_level_0_3, REAL_LIVE (recorded, replayed), up to 2026-09-03T11:45:00+00:00. 79/79 mapped SUMO edges priced from its numeric output (free-flow travel time x congestion-class band midpoint).

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 79 edges slowed to reproduce the observed state in EVERY arm (REAL_LIVE congestion classes observed at the forecast's as-of bin); compliance 30%; horizon 1800 s; seeds [11].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | queue veh | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 212.01 | +0.00 % | 360.3 | +0.00 % | 580.0 | 49478 | +0.00 % | 44.35 | 96.5 | 1730.0 | 1.0 | 0.0 | 0.0 |
| **reactive** | 205.79 | -2.93 % | 350.8 | -2.64 % | 548.0 | 51026 | +3.13 % | 42.84 | 95.6 | 1738.0 | 0.0 | 2749.0 | 0.0 |
| **prediction_aware** | 215.75 | +1.76 % | 354.6 | -1.58 % | 633.0 | 59871 | +21.01 % | 70.84 | 102.7 | 1659.0 | 13.0 | 1831.0 | 2263.0 |

One seed only: no per-seed agreement can be claimed from this run.


All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11 --horizon 1800 --v2x ideal --source recorded --as-of peak --levels observed`.
