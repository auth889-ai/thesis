# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-02T13:52:56.444827+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 36 edges congested above free flow; compliance 30%; scale 0.25; horizon 900s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| karwanbazar_to_shahbagh | 2.50 | x2.12 | 36 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 85.6 | 665 | 0 | 0 |
| reactive | 11 | 83.5 | 672 | 2 | 1398 |
| advised | 11 | 83.3 | 684 | 0 | 1058 |

Per-seed vehicle-hour change: [-2.71] (mean -2.71 %).

## Decision: **ACT**

advised improves total vehicle-hours on every paired seed without cost to arrivals or teleports

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11`.
