# Does worse communication cause higher network delay?

Generated 2026-09-02T10:28:04.725327+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (the feed supplies congestion state, never demand). Compliance 30%; horizon 1800 s; delivery model: official 1 Hz DENM repeat.

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
| ideal (seed 14) | 0 ms | 0 % | 0.8568 | 2295/2655 | 1863 | 209.8 | 62548 | 1670 |
| good (seed 14) | 0 ms | 10 % | 0.8503 | 2261/2655 | 1822 | 213.1 | 64778 | 1670 |
| degraded (seed 14) | 500 ms | 30 % | 0.7972 | 2093/2655 | 1699 | 208.3 | 58596 | 1694 |
| bad (seed 14) | 5000 ms | 30 % | 0.7776 | 2048/2655 | 1632 | 216.8 | 72181 | 1665 |
| ideal (seed 15) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1832 | 209.2 | 57243 | 1671 |
| good (seed 15) | 0 ms | 10 % | 0.8503 | 2271/2655 | 1827 | 211.3 | 71503 | 1701 |
| degraded (seed 15) | 500 ms | 30 % | 0.7972 | 2144/2655 | 1747 | 203.7 | 59029 | 1748 |
| bad (seed 15) | 5000 ms | 30 % | 0.7776 | 2048/2655 | 1655 | 218.8 | 63380 | 1617 |
| ideal (seed 16) | 0 ms | 0 % | 0.8568 | 2250/2655 | 1823 | 215.8 | 67375 | 1654 |
| good (seed 16) | 0 ms | 10 % | 0.8503 | 2244/2655 | 1827 | 201.4 | 47877 | 1741 |
| degraded (seed 16) | 500 ms | 30 % | 0.7972 | 2103/2655 | 1711 | 219.5 | 82043 | 1698 |
| bad (seed 16) | 5000 ms | 30 % | 0.7776 | 2053/2655 | 1666 | 207.6 | 64399 | 1720 |
| ideal (seed 17) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1854 | 212.3 | 61052 | 1663 |
| good (seed 17) | 0 ms | 10 % | 0.8503 | 2274/2655 | 1850 | 215.1 | 64564 | 1657 |
| degraded (seed 17) | 500 ms | 30 % | 0.7972 | 2153/2655 | 1749 | 211.7 | 67791 | 1682 |
| bad (seed 17) | 5000 ms | 30 % | 0.7776 | 2093/2655 | 1703 | 215.3 | 57931 | 1640 |
| ideal (seed 18) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1839 | 205.8 | 59461 | 1718 |
| good (seed 18) | 0 ms | 10 % | 0.8503 | 2251/2655 | 1839 | 216.0 | 75082 | 1688 |
| degraded (seed 18) | 500 ms | 30 % | 0.7972 | 2156/2655 | 1755 | 203.8 | 53107 | 1719 |
| bad (seed 18) | 5000 ms | 30 % | 0.7776 | 2071/2655 | 1682 | 208.3 | 63328 | 1700 |
| ideal (seed 19) | 0 ms | 0 % | 0.8568 | 2246/2655 | 1820 | 214.8 | 69410 | 1653 |
| good (seed 19) | 0 ms | 10 % | 0.8503 | 2243/2655 | 1814 | 215.2 | 66533 | 1661 |
| degraded (seed 19) | 500 ms | 30 % | 0.7972 | 2099/2655 | 1707 | 210.6 | 70013 | 1713 |
| bad (seed 19) | 5000 ms | 30 % | 0.7776 | 2068/2655 | 1661 | 213.6 | 73001 | 1682 |
| ideal (seed 20) | 0 ms | 0 % | 0.8568 | 2262/2655 | 1829 | 211.4 | 73968 | 1706 |
| good (seed 20) | 0 ms | 10 % | 0.8503 | 2256/2655 | 1828 | 213.3 | 71082 | 1700 |
| degraded (seed 20) | 500 ms | 30 % | 0.7972 | 2126/2655 | 1738 | 244.3 | 111954 | 1572 |
| bad (seed 20) | 5000 ms | 30 % | 0.7776 | 2016/2655 | 1629 | 219.6 | 84684 | 1668 |

## Paired change vs `ideal` (the best-communication condition)

| condition | delivery | advisories delivered | veh-h % per seed | mean veh-h % | mean waiting % | seeds worse |
|---|---|---|---|---|---|---|
| good | 0.8503 | 2255.4 | [-1.15, 1.34, -1.85, 1.57, 1.03, -6.69, 1.32, 4.95, 0.17, 0.93] | **0.16 %** | 0.51 % | 7/10 |
| degraded | 0.7972 | 2119.8 | [-1.38, 0.58, 2.54, -0.74, -2.6, 1.71, -0.29, -0.99, -1.97, 15.58] | **1.24 %** | 9.52 % | 4/10 |
| bad | 0.7776 | 2063.4 | [-3.02, 7.4, 8.88, 3.32, 4.59, -3.82, 1.41, 1.19, -0.57, 3.9] | **2.33 %** | 10.48 % | 7/10 |

A positive percentage means the condition is WORSE than the baseline: degrading the link raised network delay.

## Verdict: **SUGGESTIVE_ONLY**

Worst condition `bad`: mean vehicle-hours 2.33 %, 7/10 paired seeds agree; means monotone in link quality: True.

only 7 of 10 paired seeds are worse under `bad`; the direction of the means is consistent but the seeds do not establish it. More seeds, or a wider delivery spread (--single-shot), are needed before this is stated as a causal result.

Regenerate: `python pipeline/routing/impairment_chain.py --seeds 11,12,13,14,15,16,17,18,19,20 --levels karwanbazar_to_shahbagh=3,farmgate_to_shahbagh=2,karwanbazar_to_banglamotor=3`.
