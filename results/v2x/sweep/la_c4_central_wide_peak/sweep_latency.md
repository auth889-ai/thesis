# V2X ablation — latency · la_c4_central_wide · peak · seeds [101, 102, 103]

| profile | latency ms | loss | penetration | connected | downlink tx/rx/drop | PDR | lat med / p95 ms | reroutes | veh-h pred vs base % | 95 % CI | W/L/T | label | p95 tt % | waiting % | queue % | arrived % | pred vs reactive % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ideal | 0.0 ± 0.0 | 0.0 | 0.3 | 259 | 18.0/18.0/0.0 | 1.0 | 0.0 / 0.0 | 54 | -0.24 | [-1.16, 0.69] | 2/1/0 | **INCONCLUSIVE** | -0.96 | 0.27 | -0.21 | 0.31 | 0.11 |
| lat100 | 100.0 ± 20.0 | 0.0 | 0.3 | 259 | 17.333333333333332/17.333333333333332/0.0 | 1.0 | 102.5 / 117.47666666666667 | 52 | -0.06 | [-0.32, 0.21] | 2/1/0 | **INCONCLUSIVE** | -0.52 | 0.14 | 0.17 | -0.08 | 0.29 |
| lat500 | 500.0 ± 50.0 | 0.0 | 0.3 | 259 | 17.333333333333332/17.333333333333332/0.0 | 1.0 | 506.25 / 543.6899999999999 | 52 | -0.06 | [-0.32, 0.21] | 2/1/0 | **INCONCLUSIVE** | -0.52 | 0.14 | 0.17 | -0.08 | 0.29 |
| lat1000 | 1000.0 ± 100.0 | 0.0 | 0.3 | 259 | 17.666666666666668/17.666666666666668/0.0 | 1.0 | 1013.4200000000001 / 1092.2633333333333 | 53 | -0.08 | [-0.28, 0.12] | 3/0/0 | **INCONCLUSIVE** | -0.47 | 0.1 | 0.23 | -0.08 | 0.27 |
| lat5000 | 5000.0 ± 500.0 | 0.0 | 0.3 | 259 | 17.0/17.0/0.0 | 1.0 | 5067.09 / 5461.320000000001 | 49 | 0.23 | [-0.81, 1.28] | 1/2/0 | **INCONCLUSIVE** | 0.56 | 1.62 | 0.75 | 0.23 | 0.59 |

Every row is a full closed-loop execution on the same seeds; baseline/reactive arms reused only where identical (same city, moment, seed, network, routing config, penetration). Development seeds: these curves are diagnostics, not the frozen final result.
