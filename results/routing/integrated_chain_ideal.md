# Integrated chain — forecast to control, measured

Generated 2026-09-04T03:40:58.271436+00:00.

```
CITY -> TRAFFIC DATA -> ML/DL FORECAST -> FUTURE ROUTE COST -> ROUTING -> SUMO
```

**Forecast.** Chronos-Bolt (checkpoint `amazon/chronos-bolt-small`), horizon 15 min, a trained/pretrained model. 79/79 mapped SUMO edges priced from its numeric output.

**V2X condition.** `ideal` — 0 ms added latency, 0 % loss, delivery fraction **0.8568** read from results/networking/latency.csv (Eclipse MOSAIC ITS-G5, SIMULATED).

**Scenario.** Network dhaka_r1.net.xml; demand DHAKA_SIMULATED_DEMAND; 52 edges slowed to reproduce the observed state in EVERY arm; compliance 30%; horizon 1800 s; seeds [11, 12, 13, 14, 15].

## Before / after

| arm | veh-h | vs base | mean TT s | vs base | p95 TT s | waiting s | vs base | time loss s | arrived | teleports | reroutes | advisories |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **baseline** | 212.9 | +0.00 % | 357.8 | +0.00 % | 601.4 | 61634 | +0.00 % | 103.7 | 1703.2 | 1.6 | 0.0 | 0.0 |
| **reactive** | 208.76 | -1.94 % | 345.9 | -3.33 % | 572.2 | 55484 | -9.98 % | 98.9 | 1689.6 | 12.0 | 2970.6 | 0.0 |
| **prediction_aware** | 207.8 | -2.40 % | 348.0 | -2.74 % | 587.4 | 59479 | -3.50 % | 100.7 | 1708.8 | 7.2 | 1909.4 | 2273.2 |

## Does it actually help?

| arm | per-seed veh-h % | seeds improved | claim |
|---|---|---|---|
| reactive | [-0.85, -1.31, -2.26, -1.99, -3.27] | 5/5 | **IMPROVES** — every paired seed improved |
| prediction_aware | [3.34, -0.89, -6.1, -3.52, -4.58] | 4/5 | **NOT_ESTABLISHED** — only 4 of 5 paired seeds improved; a mean that the seeds do not support is not a result |

All numbers are a **SIMULATED COUNTERFACTUAL** on the calibrated Dhaka twin, not a measurement of the real road. The live feed supplies the congestion state; the demand is the project's calibrated synthetic demand.

Regenerate: `python pipeline/routing/integrated_chain.py --seeds 11,12,13,14,15 --v2x ideal`.
