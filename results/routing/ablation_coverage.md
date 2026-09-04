# Forecast-quality ablation — 11,12,13,14,15, compliance 30%, V2X ideal

| coverage (hops) | priced edges | forecast | veh-h (pred. arm) | vs baseline mean | per seed | seeds improved | claim |
|---|---|---|---|---|---|---|---|
| 0 | 79 | **Chronos-Bolt** | 217.44 | -0.59 % | [1.77, 2.09, -3.03, -0.03, -3.74] | 3/5 | NOT_ESTABLISHED |
| 0 | 79 | **random** | 217.44 | -0.59 % | [1.77, 2.09, -3.03, -0.03, -3.74] | 3/5 | NOT_ESTABLISHED |
| 3 | 441 | **Chronos-Bolt** | 217.68 | -0.48 % | [2.44, 4.0, -3.11, -4.23, -1.52] | 3/5 | NOT_ESTABLISHED |
| 3 | 441 | **random** | 219.01 | +0.11 % | [-3.16, -2.69, 3.22, 3.91, -0.72] | 3/5 | NOT_ESTABLISHED |
| 8 | 1324 | **Chronos-Bolt** | 216.6 | -0.95 % | [2.59, -3.19, -1.18, -2.74, -0.23] | 4/5 | NOT_ESTABLISHED |
| 8 | 1324 | **random** | 214.99 | -1.73 % | [-0.4, 3.64, -5.55, -0.88, -5.44] | 4/5 | NOT_ESTABLISHED |

Reactive (no forecast) vs baseline: -1.89 % mean, 4/5 seeds improved.

## Did the forecast reach the router? (seed 11)

| coverage (hops) | forecasts compared | vehicles routed differently |
|---|---|---|
| 0 | Chronos-Bolt vs random | 0 |
| 3 | Chronos-Bolt vs random | 286 |
| 8 | Chronos-Bolt vs random | 321 |

**Coverage.** growing the priced coverage to 8 hops (1324 edges) makes the router route 321 vehicles differently for the model than for noise, so coverage WAS the first bottleneck; with the forecast now reaching the road, the model's outcome is +0.78 pp relative to noise — it does NOT beat noise, consistent with its negative skill against persistence (E1): the second bottleneck is the model itself.

**Reading.** the real model and RANDOM noise produced identical routes: the forecast's numbers never reached the router. With only the mapped corridor edges priced, the route decision is insensitive to forecast magnitude in the plausible range, so no accuracy gain could change the outcome — pricing COVERAGE is the bottleneck, not the model.

SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin. Every number in this table was measured by SUMO in the runs listed in the JSON.
