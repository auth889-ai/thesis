# Routing Decision Guard, Horizon 7200 s

Source: `/Users/jannatulferdouseva/thesis/route/results/arms_h7200.json`.
Reference arm: `reactive`.
Decision: **NO_SAFE_ROUTING_ACTION**.
Selected deployable arm: `none`.

Acceptance rule: minimum 3 paired seeds; total vehicle-hours, arrivals, and teleports must all improve on every paired seed.

| arm | n | accepted | mean total-vehicle-hours benefit | mean arrivals benefit | mean teleports benefit | reason |
|---|---:|---|---:|---:|---:|---|
| predictive_persistence | 10 | False | 13.2% | 4.3% | 35.1% | rejected: does not improve all required network-wide metrics on every paired seed |

Offline benchmarks, not runtime actions:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| due | 10 | False | 38.1% |

Upper bounds, not deployable real forecasts:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| predictive_oracle | 10 | False | 16.4% |

Honesty label: `DHAKA_SIMULATED_SENSOR_GRAPH`.
