# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-02T13:51:06.534610+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 36 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| karwanbazar_to_shahbagh | 2.50 | x2.12 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 211.3 | 1689 | 0 | 0 |
| advised | 11 | 207.8 | 1679 | 8 | 2152 |
| unaware | 12 | 211.0 | 1705 | 2 | 0 |
| advised | 12 | 204.7 | 1719 | 6 | 2152 |
| unaware | 13 | 216.5 | 1673 | 10 | 0 |
| advised | 13 | 221.8 | 1612 | 19 | 2152 |

Per-seed vehicle-hour change: [-1.68, -2.99, 2.46] (mean -0.74 %).

## Decision: **NO_ACTION**

vehicle-hours improved on only 2/3 seeds; arrivals fall on average (-19.0); teleports rise on average (+7.0)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
