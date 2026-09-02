# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-02T13:54:33.457993+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 46 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| farmgate_to_shahbagh | 2.50 | x2.12 | 46 |

| arm | seed | total veh-h | arrived | teleports | routes changed |
|---|---|---|---|---|---|
| unaware | 11 | 209.9 | 1717 | 5 | 0 |
| reactive | 11 | 200.1 | 1741 | 1 | 3276 |
| advised | 11 | 206.1 | 1637 | 18 | 2149 |
| unaware | 12 | 210.0 | 1702 | 0 | 0 |
| reactive | 12 | 204.9 | 1711 | 6 | 3424 |
| advised | 12 | 205.0 | 1714 | 7 | 2149 |
| unaware | 13 | 213.9 | 1698 | 3 | 0 |
| reactive | 13 | 201.5 | 1741 | 0 | 3290 |
| advised | 13 | 207.5 | 1690 | 11 | 2149 |

Per-seed vehicle-hour change: [-1.79, -2.37, -2.96] (mean -2.37 %).

## Decision: **NO_ACTION**

arrivals fall on average (-25.3); teleports rise on average (+9.3)

Rule: ACT iff total vehicle-hours improves on EVERY paired seed and mean arrivals do not fall and mean teleports do not rise

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
