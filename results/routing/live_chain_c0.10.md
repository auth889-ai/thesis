# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:23:05.140720+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 10%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 213.1 | 1672 | 14 | 723 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 212.4 | 1681 | 8 | 723 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 208.5 | 1740 | 1 | 723 |

Per-seed vehicle-hour change: [0.05, -1.19, -2.23] (mean -1.13 %).

## Decision: **NO_ACTION**

vehicle-hours improved on only 2/3 seeds; teleports rise on average (+6.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
