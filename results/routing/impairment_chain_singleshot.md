# Does worse communication cause higher network delay?

Generated 2026-09-02T10:24:52.166407+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (the feed supplies congestion state, never demand). Compliance 30%; horizon 1800 s; delivery model: single DENM.

The equipped set is identical in every condition. Conditions differ only in whether the advisory **arrived before the driver's decision point**; an undelivered advisory leaves that vehicle on its original route, which is what a missed advisory actually means.

Delivery fractions are read from `results/networking/latency.csv`, never interpolated. **SIMULATED (Eclipse MOSAIC ITS-G5), not hardware-measured.**

| condition | added latency | loss | delivery fraction | advisories delivered | routes changed | veh-h | waiting s | arrived |
|---|---|---|---|---|---|---|---|---|
| ideal (seed 11) | 0 ms | 0 % | 0.8568 | 2263/2655 | 1831 | 206.8 | 61256 | 1706 |
| good (seed 11) | 0 ms | 10 % | 0.7705 | 2043/2655 | 1662 | 203.6 | 52486 | 1731 |
| degraded (seed 11) | 500 ms | 30 % | 0.558 | 1507/2655 | 1234 | 211.0 | 58437 | 1699 |
| bad (seed 11) | 5000 ms | 30 % | 0.544 | 1455/2655 | 1181 | 204.4 | 53298 | 1745 |
| ideal (seed 12) | 0 ms | 0 % | 0.8568 | 2252/2655 | 1827 | 202.5 | 51350 | 1726 |
| good (seed 12) | 0 ms | 10 % | 0.7705 | 2059/2655 | 1686 | 202.7 | 49748 | 1729 |
| degraded (seed 12) | 500 ms | 30 % | 0.558 | 1485/2655 | 1211 | 203.9 | 49760 | 1726 |
| bad (seed 12) | 5000 ms | 30 % | 0.544 | 1454/2655 | 1185 | 209.6 | 57013 | 1705 |
| ideal (seed 13) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1857 | 208.1 | 64298 | 1696 |
| good (seed 13) | 0 ms | 10 % | 0.7705 | 2033/2655 | 1654 | 208.8 | 59003 | 1712 |
| degraded (seed 13) | 500 ms | 30 % | 0.558 | 1478/2655 | 1203 | 205.7 | 58684 | 1745 |
| bad (seed 13) | 5000 ms | 30 % | 0.544 | 1445/2655 | 1187 | 206.7 | 57423 | 1727 |
| ideal (seed 14) | 0 ms | 0 % | 0.8568 | 2295/2655 | 1863 | 209.8 | 62548 | 1670 |
| good (seed 14) | 0 ms | 10 % | 0.7705 | 2057/2655 | 1657 | 208.2 | 64893 | 1698 |
| degraded (seed 14) | 500 ms | 30 % | 0.558 | 1505/2655 | 1224 | 204.8 | 51367 | 1741 |
| bad (seed 14) | 5000 ms | 30 % | 0.544 | 1443/2655 | 1145 | 207.2 | 54655 | 1717 |
| ideal (seed 15) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1832 | 209.2 | 57243 | 1671 |
| good (seed 15) | 0 ms | 10 % | 0.7705 | 2074/2655 | 1664 | 216.9 | 66489 | 1635 |
| degraded (seed 15) | 500 ms | 30 % | 0.558 | 1517/2655 | 1234 | 210.5 | 60510 | 1706 |
| bad (seed 15) | 5000 ms | 30 % | 0.544 | 1427/2655 | 1150 | 212.3 | 64219 | 1690 |
| ideal (seed 16) | 0 ms | 0 % | 0.8568 | 2250/2655 | 1823 | 215.8 | 67375 | 1654 |
| good (seed 16) | 0 ms | 10 % | 0.7705 | 2034/2655 | 1666 | 212.1 | 70633 | 1702 |
| degraded (seed 16) | 500 ms | 30 % | 0.558 | 1494/2655 | 1203 | 210.4 | 63166 | 1697 |
| bad (seed 16) | 5000 ms | 30 % | 0.544 | 1442/2655 | 1166 | 227.1 | 90810 | 1625 |
| ideal (seed 17) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1854 | 212.3 | 61052 | 1663 |
| good (seed 17) | 0 ms | 10 % | 0.7705 | 2078/2655 | 1683 | 222.0 | 58269 | 1600 |
| degraded (seed 17) | 500 ms | 30 % | 0.558 | 1516/2655 | 1232 | 215.9 | 76025 | 1679 |
| bad (seed 17) | 5000 ms | 30 % | 0.544 | 1455/2655 | 1185 | 209.6 | 55203 | 1707 |
| ideal (seed 18) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1839 | 205.8 | 59461 | 1718 |
| good (seed 18) | 0 ms | 10 % | 0.7705 | 2071/2655 | 1695 | 207.7 | 62569 | 1701 |
| degraded (seed 18) | 500 ms | 30 % | 0.558 | 1494/2655 | 1219 | 211.6 | 59264 | 1689 |
| bad (seed 18) | 5000 ms | 30 % | 0.544 | 1459/2655 | 1180 | 207.7 | 55222 | 1730 |
| ideal (seed 19) | 0 ms | 0 % | 0.8568 | 2246/2655 | 1820 | 214.8 | 69410 | 1653 |
| good (seed 19) | 0 ms | 10 % | 0.7705 | 2029/2655 | 1646 | 210.0 | 62870 | 1676 |
| degraded (seed 19) | 500 ms | 30 % | 0.558 | 1514/2655 | 1234 | 211.6 | 65057 | 1710 |
| bad (seed 19) | 5000 ms | 30 % | 0.544 | 1418/2655 | 1146 | 215.0 | 63454 | 1672 |
| ideal (seed 20) | 0 ms | 0 % | 0.8568 | 2262/2655 | 1829 | 211.4 | 73968 | 1706 |
| good (seed 20) | 0 ms | 10 % | 0.7705 | 2032/2655 | 1653 | 205.5 | 64058 | 1719 |
| degraded (seed 20) | 500 ms | 30 % | 0.558 | 1491/2655 | 1209 | 207.5 | 64977 | 1728 |
| bad (seed 20) | 5000 ms | 30 % | 0.544 | 1438/2655 | 1170 | 204.9 | 60748 | 1752 |

## Paired change vs `ideal` (the best-communication condition)

| condition | delivery | advisories delivered | veh-h % per seed | mean veh-h % | mean waiting % | seeds worse |
|---|---|---|---|---|---|---|
| good | 0.7705 | 2051.0 | [-1.54, 0.11, 0.36, -0.76, 3.69, -1.73, 4.56, 0.93, -2.26, -2.77] | **0.06 %** | -2.31 % | 5/10 |
| degraded | 0.558 | 1500.1 | [2.05, 0.71, -1.11, -2.4, 0.62, -2.53, 1.67, 2.79, -1.49, -1.81] | **-0.15 %** | -2.91 % | 5/10 |
| bad | 0.544 | 1443.6 | [-1.18, 3.52, -0.67, -1.25, 1.51, 5.21, -1.3, 0.91, 0.09, -3.08] | **0.38 %** | -2.15 % | 5/10 |

A positive percentage means the condition is WORSE than the baseline: degrading the link raised network delay.

## Verdict: **SUGGESTIVE_ONLY**

Worst condition `bad`: mean vehicle-hours 0.38 %, 5/10 paired seeds agree; means monotone in link quality: False.

only 5 of 10 paired seeds are worse under `bad`; the direction of the means is consistent but the seeds do not establish it. More seeds, or a wider delivery spread (--single-shot), are needed before this is stated as a causal result.

Regenerate: `python pipeline/routing/impairment_chain.py --seeds 11,12,13,14,15,16,17,18,19,20 --levels karwanbazar_to_shahbagh=3,farmgate_to_shahbagh=2,karwanbazar_to_banglamotor=3`.
