# Live chain — Dhaka live congestion to a routing decision

Generated 2026-09-03T02:04:56.237468+00:00. Source: **SYNTHETIC_WHAT_IF**. Network: real Dhaka R1. Demand: DHAKA_SIMULATED_DEMAND (live feed supplies congestion state, never demand). 0 edges congested above free flow; compliance 30%; scale 0.25; horizon 1800s.

| corridor | level | multiplier | edges |
|---|---|---|---|
| shahbagh_to_farmgate | 0.00 | x1.08 | 26 |

## Decision: **NO_ACTION**

every monitored corridor is at free flow — nothing to route around; acting would be intervention without evidence

Rule: no congestion observed -> no intervention

Regenerate: `python pipeline/routing/live_chain.py --seeds 11,12,13`.
