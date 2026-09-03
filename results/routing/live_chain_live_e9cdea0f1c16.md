# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-03T05:19:41.587860+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 46 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 1.00 | x1.33 | 46 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 205.5 | 1735 | 0 | 0 |
| reactive | 11 | 204.2 | 1691 | 15 | 3383 |
| advised | 11 | 204.1 | 1717 | 1 | 2149 |
| unaware | 12 | 208.5 | 1720 | 1 | 0 |
| reactive | 12 | 204.9 | 1693 | 11 | 3436 |
| advised | 12 | 217.0 | 1643 | 19 | 2149 |
| unaware | 13 | 211.3 | 1701 | 0 | 0 |
| reactive | 13 | 195.3 | 1774 | 0 | 3145 |
| advised | 13 | 213.4 | 1624 | 27 | 2149 |

Per-seed vehicle-hour change: [-0.65, 4.1, 1.02] (mean 1.49 %).

## Decision: **NO_ACTION**

vehicle-hours improved on only 1/3 seeds; arrivals fall on average (-57.3); teleports rise on average (+15.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
