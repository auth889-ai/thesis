# Forecast-quality ablation — 11,12,13,14,15, compliance 30%, V2X ideal

| forecast | meaning | veh-h (pred. arm) | vs baseline mean | per seed | seeds improved | claim |
|---|---|---|---|---|---|---|
| **oracle** | the truth: this seed's own baseline edge travel times — the ceiling | 214.04 | -2.16 % | [-3.47, -1.94, -6.0, -3.7, 4.31] | 4/5 | NOT_ESTABLISHED |
| **Chronos-Bolt** | the registry's model (or --model), run over real recorded history | 217.44 | -0.59 % | [1.77, 2.09, -3.03, -0.03, -3.74] | 3/5 | NOT_ESTABLISHED |
| **persistence** | the registry's model (or --model), run over real recorded history | 221.04 | +1.06 % | [3.11, -1.17, 8.01, 0.83, -5.46] | 2/5 | NOT_ESTABLISHED |
| **random** | uniform random congestion level per corridor, seeded — the floor | 217.44 | -0.59 % | [1.77, 2.09, -3.03, -0.03, -3.74] | 3/5 | NOT_ESTABLISHED |

Reactive (no forecast) vs baseline: -1.89 % mean, 4/5 seeds improved.

## Did the forecast reach the router? (seed 11)

| forecasts compared | vehicles routed differently |
|---|---|
| oracle vs Chronos-Bolt | 896 |
| oracle vs persistence | 975 |
| oracle vs random | 896 |
| Chronos-Bolt vs persistence | 426 |
| Chronos-Bolt vs random | 0 |
| persistence vs random | 426 |

**Reading.** the real model and RANDOM noise produced identical routes: the forecast's numbers never reached the router. With only the mapped corridor edges priced, the route decision is insensitive to forecast magnitude in the plausible range, so no accuracy gain could change the outcome — pricing COVERAGE is the bottleneck, not the model.

SIMULATED COUNTERFACTUAL on the calibrated Dhaka twin. Every number in this table was measured by SUMO in the runs listed in the JSON.
