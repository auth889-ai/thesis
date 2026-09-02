# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:21:54.268268+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 217.2 | 1651 | 15 | 2152 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 207.9 | 1676 | 10 | 2152 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 221.2 | 1627 | 13 | 2152 |

Per-seed vehicle-hour change: [2.0, -3.31, 3.72] (mean 0.81 %).

## Decision: **NO_ACTION**

vehicle-hours improved on only 1/3 seeds; arrivals fall on average (-45.3); teleports rise on average (+11.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
