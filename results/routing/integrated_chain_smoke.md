# Integrated chain — forecast to control, measured

Generated 2026-09-04T03:39:14.598580+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. 79/79 mapped SUMO edges priced from its numeric output.

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 52 edges slowed to reproduce the observed state in EVERY arm; compliance 30%; horizon 900 s; seeds [11].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 85.61 | +0.00 % | 319.9 | +0.00 % | 488.0 | 11555 | +0.00 % | 77.5 | 669.0 | 0.0 | 0.0 | 0.0 |
| **reactive** | 83.87 | -2.03 % | 310.8 | -2.84 % | 474.0 | 12064 | +4.41 % | 76.7 | 673.0 | 0.0 | 1179.0 | 0.0 |
| **prediction_aware** | 83.4 | -2.58 % | 309.6 | -3.22 % | 474.0 | 10933 | -5.38 % | 75.4 | 673.0 | 0.0 | 930.0 | 1128.0 |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11 --v2x ideal`.
