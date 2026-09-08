# V2X ablation — penetration · la_c4_central_wide · peak · seeds [101, 102, 103]

| profile | latency ms | loss | penetration | connected | downlink tx/rx/drop | PDR | lat med / p95 ms | reroutes | veh-h pred vs base % | 95 % CI | W/L/T | label | p95 tt % | waiting % | queue % | arrived % | pred vs reactive % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ideal | 0.0 ± 0.0 | 0.0 | 0.0 | 0.0 | 0.0/0.0/0.0 | None | None / None | 0 | 0.0 | [0.0, 0.0] | 0/0/3 | **INCONCLUSIVE** | 0.0 | 0.0 | 0.0 | 0.0 | None |
| ideal | 0.0 ± 0.0 | 0.0 | 0.1 | 88 | 6.666666666666667/6.666666666666667/0.0 | 1.0 | 0.0 / 0.0 | 20 | 0.05 | [-0.49, 0.59] | 1/2/0 | **INCONCLUSIVE** | 0.08 | 0.35 | 0.29 | -0.04 | 0.14 |
| ideal | 0.0 ± 0.0 | 0.0 | 0.3 | 259 | 18.0/18.0/0.0 | 1.0 | 0.0 / 0.0 | 54 | -0.24 | [-1.16, 0.69] | 2/1/0 | **INCONCLUSIVE** | -0.96 | 0.27 | -0.21 | 0.31 | 0.11 |
| ideal | 0.0 ± 0.0 | 0.0 | 0.5 | 440 | 36.0/36.0/0.0 | 1.0 | 0.0 / 0.0 | 108 | -0.58 | [-1.87, 0.71] | 3/0/0 | **INCONCLUSIVE** | -0.93 | -0.3 | -0.6 | 0.04 | -0.19 |
| ideal | 0.0 ± 0.0 | 0.0 | 0.7 | 612 | 44.666666666666664/44.666666666666664/0.0 | 1.0 | 0.0 / 0.0 | 134 | -0.34 | [-0.76, 0.08] | 3/0/0 | **INCONCLUSIVE** | 0.35 | 0.42 | 0.67 | -0.04 | 0.23 |
| ideal | 0.0 ± 0.0 | 0.0 | 1.0 | 900 | 65.0/65.0/0.0 | 1.0 | 0.0 / 0.0 | 195 | -0.5 | [-2.12, 1.12] | 2/1/0 | **INCONCLUSIVE** | 0.44 | 1.28 | 0.96 | 0.23 | 0.06 |

Every row is a full closed-loop execution on the same seeds; baseline/reactive arms reused only where identical (same city, moment, seed, network, routing config, penetration). Development seeds: these curves are diagnostics, not the frozen final result.
