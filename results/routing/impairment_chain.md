# Does worse communication cause higher network delay?

Generated 2026-09-02T10:20:24.524364+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (the feed supplies congestion state, never demand). Compliance 30%; horizon 1800 s; delivery model: official 1 Hz DENM repeat.

The equipped set is identical in every condition. Conditions differ only in whether the advisory **arrived before the driver's decision point**; an undelivered advisory leaves that vehicle on its original route, which is what a missed advisory actually means.

Delivery fractions are read from `results/networking/latency.csv`, never interpolated. **SIMULATED (Eclipse MOSAIC ITS-G5), not hardware-measured.**

| condition | added latency | loss | delivery fraction | advisories delivered | routes changed | veh-h | waiting s | arrived |
|---|---|---|---|---|---|---|---|---|
| ideal (seed 11) | 0 ms | 0 % | 0.8568 | 2263/2655 | 1831 | 206.8 | 61256 | 1706 |
| good (seed 11) | 0 ms | 10 % | 0.8503 | 2244/2655 | 1822 | 204.4 | 52043 | 1725 |
| degraded (seed 11) | 500 ms | 30 % | 0.7972 | 2113/2655 | 1726 | 203.9 | 54565 | 1740 |
| bad (seed 11) | 5000 ms | 30 % | 0.7776 | 2065/2655 | 1679 | 200.5 | 49660 | 1739 |
| ideal (seed 12) | 0 ms | 0 % | 0.8568 | 2252/2655 | 1827 | 202.5 | 51350 | 1726 |
| good (seed 12) | 0 ms | 10 % | 0.8503 | 2255/2655 | 1838 | 205.2 | 57175 | 1715 |
| degraded (seed 12) | 500 ms | 30 % | 0.7972 | 2113/2655 | 1716 | 203.7 | 56434 | 1739 |
| bad (seed 12) | 5000 ms | 30 % | 0.7776 | 2077/2655 | 1702 | 217.5 | 69547 | 1639 |
| ideal (seed 13) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1857 | 208.1 | 64298 | 1696 |
| good (seed 13) | 0 ms | 10 % | 0.8503 | 2255/2655 | 1832 | 204.2 | 54822 | 1738 |
| degraded (seed 13) | 500 ms | 30 % | 0.7972 | 2098/2655 | 1691 | 213.3 | 80413 | 1704 |
| bad (seed 13) | 5000 ms | 30 % | 0.7776 | 2095/2655 | 1698 | 226.5 | 93585 | 1637 |

## Paired change vs `ideal` (the best-communication condition)

| condition | delivery | advisories delivered | veh-h % per seed | mean veh-h % | mean waiting % | seeds worse |
|---|---|---|---|---|---|---|
| good | 0.8503 | 2251.3 | [-1.15, 1.34, -1.85] | **-0.55 %** | -6.15 % | 1/3 |
| degraded | 0.7972 | 2108.0 | [-1.38, 0.58, 2.54] | **0.58 %** | 8.01 % | 2/3 |
| bad | 0.7776 | 2079.0 | [-3.02, 7.4, 8.88] | **4.42 %** | 20.69 % | 2/3 |

A positive percentage means the condition is WORSE than the baseline: degrading the link raised network delay.

Regenerate: `python pipeline/routing/impairment_chain.py --seeds 11,12,13 --levels karwanbazar_to_shahbagh=3,farmgate_to_shahbagh=2,karwanbazar_to_banglamotor=3`.
