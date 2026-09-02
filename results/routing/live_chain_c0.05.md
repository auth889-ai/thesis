# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-01T16:22:38.646120+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 53 edges congested above free flow; compliance 5%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.00 | x1.75 | 46 |
| karwanbazar_to_banglamotor | 3.00 | x2.50 | 21 |
| karwanbazar_to_shahbagh | 3.00 | x2.50 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 213.0 | 1703 | 0 | 0 |
| advised | 11 | 208.5 | 1723 | 0 | 356 |
| unaware | 12 | 215.0 | 1685 | 0 | 0 |
| advised | 12 | 212.2 | 1703 | 1 | 356 |
| unaware | 13 | 213.2 | 1702 | 4 | 0 |
| advised | 13 | 209.1 | 1736 | 0 | 356 |

Per-seed vehicle-hour change: [-2.07, -1.28, -1.96] (mean -1.77 %).

## Decision: **ACT**

advised improves total vehicle-hours on every paired seed without cost to arrivals or teleports

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
