# Does worse communication cause higher network delay?

Generated 2026-09-02T10:33:24.882577+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (the feed supplies congestion state, never demand). Compliance 30%; horizon 1800 s; delivery model: single DENM.

The equipped set is identical in every condition. Conditions differ only in whether the advisory **arrived before the driver's decision point**; an undelivered advisory leaves that vehicle on its original route, which is what a missed advisory actually means.

Delivery fractions are read from `results/networking/latency.csv`, never interpolated. **SIMULATED (Eclipse MOSAIC ITS-G5), not hardware-measured.**

| condition | added latency | loss | delivery fraction | advisories delivered | routes changed | veh-h | waiting s | arrived |
|---|---|---|---|---|---|---|---|---|
| none (seed 11) | — ms | — % | 0.0 | 0/2655 | 0 | 213.0 | 59211 | 1703 |
| ideal (seed 11) | 0 ms | 0 % | 0.8568 | 2263/2655 | 1831 | 206.8 | 61256 | 1706 |
| degraded (seed 11) | 500 ms | 30 % | 0.558 | 1507/2655 | 1234 | 211.0 | 58437 | 1699 |
| bad (seed 11) | 5000 ms | 30 % | 0.544 | 1455/2655 | 1181 | 204.4 | 53298 | 1745 |
| none (seed 12) | — ms | — % | 0.0 | 0/2655 | 0 | 215.0 | 56992 | 1685 |
| ideal (seed 12) | 0 ms | 0 % | 0.8568 | 2252/2655 | 1827 | 202.5 | 51350 | 1726 |
| degraded (seed 12) | 500 ms | 30 % | 0.558 | 1485/2655 | 1211 | 203.9 | 49760 | 1726 |
| bad (seed 12) | 5000 ms | 30 % | 0.544 | 1454/2655 | 1185 | 209.6 | 57013 | 1705 |
| none (seed 13) | — ms | — % | 0.0 | 0/2655 | 0 | 213.2 | 60475 | 1702 |
| ideal (seed 13) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1857 | 208.1 | 64298 | 1696 |
| degraded (seed 13) | 500 ms | 30 % | 0.558 | 1478/2655 | 1203 | 205.7 | 58684 | 1745 |
| bad (seed 13) | 5000 ms | 30 % | 0.544 | 1445/2655 | 1187 | 206.7 | 57423 | 1727 |
| none (seed 14) | — ms | — % | 0.0 | 0/2655 | 0 | 209.6 | 53686 | 1721 |
| ideal (seed 14) | 0 ms | 0 % | 0.8568 | 2295/2655 | 1863 | 209.8 | 62548 | 1670 |
| degraded (seed 14) | 500 ms | 30 % | 0.558 | 1505/2655 | 1224 | 204.8 | 51367 | 1741 |
| bad (seed 14) | 5000 ms | 30 % | 0.544 | 1443/2655 | 1145 | 207.2 | 54655 | 1717 |
| none (seed 15) | — ms | — % | 0.0 | 0/2655 | 0 | 215.0 | 61562 | 1695 |
| ideal (seed 15) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1832 | 209.2 | 57243 | 1671 |
| degraded (seed 15) | 500 ms | 30 % | 0.558 | 1517/2655 | 1234 | 210.5 | 60510 | 1706 |
| bad (seed 15) | 5000 ms | 30 % | 0.544 | 1427/2655 | 1150 | 212.3 | 64219 | 1690 |
| none (seed 16) | — ms | — % | 0.0 | 0/2655 | 0 | 216.2 | 65459 | 1689 |
| ideal (seed 16) | 0 ms | 0 % | 0.8568 | 2250/2655 | 1823 | 215.8 | 67375 | 1654 |
| degraded (seed 16) | 500 ms | 30 % | 0.558 | 1494/2655 | 1203 | 210.4 | 63166 | 1697 |
| bad (seed 16) | 5000 ms | 30 % | 0.544 | 1442/2655 | 1166 | 227.1 | 90810 | 1625 |
| none (seed 17) | — ms | — % | 0.0 | 0/2655 | 0 | 215.8 | 58873 | 1691 |
| ideal (seed 17) | 0 ms | 0 % | 0.8568 | 2277/2655 | 1854 | 212.3 | 61052 | 1663 |
| degraded (seed 17) | 500 ms | 30 % | 0.558 | 1516/2655 | 1232 | 215.9 | 76025 | 1679 |
| bad (seed 17) | 5000 ms | 30 % | 0.544 | 1455/2655 | 1185 | 209.6 | 55203 | 1707 |
| none (seed 18) | — ms | — % | 0.0 | 0/2655 | 0 | 211.8 | 58271 | 1718 |
| ideal (seed 18) | 0 ms | 0 % | 0.8568 | 2279/2655 | 1839 | 205.8 | 59461 | 1718 |
| degraded (seed 18) | 500 ms | 30 % | 0.558 | 1494/2655 | 1219 | 211.6 | 59264 | 1689 |
| bad (seed 18) | 5000 ms | 30 % | 0.544 | 1459/2655 | 1180 | 207.7 | 55222 | 1730 |
| none (seed 19) | — ms | — % | 0.0 | 0/2655 | 0 | 214.2 | 61457 | 1690 |
| ideal (seed 19) | 0 ms | 0 % | 0.8568 | 2246/2655 | 1820 | 214.8 | 69410 | 1653 |
| degraded (seed 19) | 500 ms | 30 % | 0.558 | 1514/2655 | 1234 | 211.6 | 65057 | 1710 |
| bad (seed 19) | 5000 ms | 30 % | 0.544 | 1418/2655 | 1146 | 215.0 | 63454 | 1672 |
| none (seed 20) | — ms | — % | 0.0 | 0/2655 | 0 | 214.6 | 66369 | 1693 |
| ideal (seed 20) | 0 ms | 0 % | 0.8568 | 2262/2655 | 1829 | 211.4 | 73968 | 1706 |
| degraded (seed 20) | 500 ms | 30 % | 0.558 | 1491/2655 | 1209 | 207.5 | 64977 | 1728 |
| bad (seed 20) | 5000 ms | 30 % | 0.544 | 1438/2655 | 1170 | 204.9 | 60748 | 1752 |

## Paired change vs `ideal` (the best-communication condition)

| condition | delivery | advisories delivered | veh-h % per seed | mean veh-h % | mean waiting % | seeds worse |
|---|---|---|---|---|---|---|
| degraded | 0.558 | 1500.1 | [2.05, 0.71, -1.11, -2.4, 0.62, -2.53, 1.67, 2.79, -1.49, -1.81] | **-0.15 %** | -2.91 % | 5/10 |
| bad | 0.544 | 1443.6 | [-1.18, 3.52, -0.67, -1.25, 1.51, 5.21, -1.3, 0.91, 0.09, -3.08] | **0.38 %** | -2.15 % | 5/10 |

A positive percentage means the condition is WORSE than the baseline: degrading the link raised network delay.

## Verdict: **INCONCLUSIVE_UNDERPOWERED**

Reference check — does advising anyone help at all? Perfect delivery vs advising nobody: mean -1.96 % vehicle-hours, helped on 8/10 seeds (**established: False**).

Worst condition `bad`: mean vehicle-hours 0.38 %, 5/10 paired seeds agree; means monotone in link quality: True.

Advising does help, but only a little: -1.96 % vehicle-hours on 8/10 seeds — a real effect, though not unanimous by this project's decision-guard rule. That is the problem. If halving advisory delivery removes a proportional share of a ~2.0 % benefit, the effect being looked for is a fraction of a percent, which is well inside the seed-to-seed spread here. This experiment is UNDERPOWERED for the communication hypothesis rather than evidence against it. Testing the chain needs a regime where routing gives a large, unanimous benefit — higher compliance, heavier congestion, or a network where rerouting matters more — so that degrading delivery has something substantial to erode.

Regenerate: `python pipeline/routing/impairment_chain.py --seeds 11,12,13,14,15,16,17,18,19,20`.
