# V2X ablation — loss · la_c4_central_wide · peak · seeds [101, 102, 103]

| profile | latency ms | loss | penetration | connected | downlink tx/rx/drop | PDR | lat med / p95 ms | reroutes | veh-h pred vs base % | 95 % CI | W/L/T | label | p95 tt % | waiting % | queue % | arrived % | pred vs reactive % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ideal | 0.0 ± 0.0 | 0.0 | 0.3 | 259 | 18.0/18.0/0.0 | 1.0 | 0.0 / 0.0 | 54 | -0.24 | [-1.16, 0.69] | 2/1/0 | **INCONCLUSIVE** | -0.96 | 0.27 | -0.21 | 0.31 | 0.11 |
| loss05 | 50.0 ± 20.0 | 0.05 | 0.3 | 259 | 17.0/16.666666666666668/0.3333333333333333 | 0.9762 | 52.5 / 67.47666666666667 | 50 | -0.06 | [-0.32, 0.21] | 2/1/0 | **INCONCLUSIVE** | -0.02 | 0.42 | 0.2 | 0.0 | 0.29 |
| loss10 | 50.0 ± 20.0 | 0.1 | 0.3 | 259 | 17.666666666666668/16.333333333333332/1.3333333333333333 | 0.9178666666666667 | 49.22666666666667 / 66.25 | 49 | -0.15 | [-0.72, 0.42] | 2/1/0 | **INCONCLUSIVE** | 0.29 | -0.27 | -0.15 | -0.11 | 0.2 |
| loss20 | 50.0 ± 20.0 | 0.2 | 0.3 | 259 | 19.333333333333332/16.333333333333332/3.0 | 0.8456333333333333 | 49.669999999999995 / 66.44 | 49 | -0.14 | [-0.72, 0.43] | 2/1/0 | **INCONCLUSIVE** | -0.02 | 0.05 | -0.37 | 0.12 | 0.2 |
| degraded | 500.0 ± 100.0 | 0.3 | 0.3 | 259 | 20.333333333333332/14.333333333333334/6.0 | 0.7131333333333334 | 498.3533333333333 / 584.6533333333333 | 43 | -0.05 | [-0.18, 0.09] | 2/0/1 | **INCONCLUSIVE** | -0.56 | 0.0 | -0.17 | 0.08 | 0.31 |

Every row is a full closed-loop execution on the same seeds; baseline/reactive arms reused only where identical (same city, moment, seed, network, routing config, penetration). Development seeds: these curves are diagnostics, not the frozen final result.
