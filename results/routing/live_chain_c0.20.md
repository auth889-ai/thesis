# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:23:31.937214+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 20%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 202.0 | 1745 | 0 | 1457 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 206.8 | 1716 | 1 | 1457 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 212.8 | 1667 | 10 | 1457 |

Per-seed vehicle-hour change: [-5.14, -3.82, -0.22] (mean -3.06 %).

## Decision: **NO_ACTION**

teleports rise on average (+2.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
