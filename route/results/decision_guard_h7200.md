# Routing Decision Guard, Horizon 7200 s

Source: `/Users/jannatulferdouseva/thesis/route/results/arms_h7200.json`.
Reference arm: `reactive`.
Decision: **ACT**.
Selected deployable arm: `predictive_persistence`.

Acceptance rule: minimum 3 paired seeds; total vehicle-hours, arrivals, and teleports must all improve on every paired seed.

| arm | n | accepted | mean total-vehicle-hours benefit | mean arrivals benefit | mean teleports benefit | reason |
|---|---:|---|---:|---:|---:|---|
| predictive_persistence | 3 | True | 32.4% | 8.5% | 83.4% | improves total vehicle-hours, arrivals, and teleports on every paired seed |

Offline benchmarks, not runtime actions:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| due | 3 | True | 46.7% |

Upper bounds, not deployable real forecasts:

| arm | n | accepted by metrics | mean total-vehicle-hours benefit |
|---|---:|---|---:|
| predictive_oracle | 3 | True | 25.4% |

Honesty label: `DHAKA_SIMULATED_SENSOR_GRAPH`.
