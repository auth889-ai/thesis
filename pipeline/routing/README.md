# pipeline/routing/

Predictive route-optimization harness for the active thesis path.

Main command:

```bash
python pipeline/routing/run_arms.py --seeds 11,12,13 --horizon 3600
python pipeline/routing/stats.py
python pipeline/routing/decision_guard.py --horizon 3600 --reference reactive
```

Arms are static, reactive, predictive, DUE, and DSO. All arms must use the same
Dhaka R1 network, demand, seeds, and horizon; only the routing rule changes.

The decision guard is the runtime honesty rule: an intervention is accepted only
when network-wide metrics improve across paired seeds. DUE/DSO are offline
benchmarks, not live actions.


## Forecast → route optimization (Blocker #2, 2026-09-05)

Production path: `AnalysisRun` (stored raw prediction, verified by hash) → `edge_costs.py`
(continuous future edge travel time = length / bounded predicted speed, DIRECT on corridor edges,
DERIVED with recorded decay at 1–2 hops) → `route_optimizer.py` (K alternatives from `duarouter`,
generalized cost = forecast future travel time + BPR load penalty + overlap penalty, minimum-benefit
threshold, capacity/share/cooldown admission) → RoutingRun `rt_<id>` in provenance → the Digital
Twin's prediction-aware arm drives that exact selected route. Every coefficient lives in
`routing_config.json` and is copied into each run. Sensitivity before any SUMO outcome:
`r2_sensitivity.py` → `results/routing/r2_route_decisions.md`.

Official SUMO (eclipse-sumo `v1_27_1`, `7717f237`, local `~/.dhakaflow/upstream/sumo`) reused, never re-implemented:

| upstream file / function | what it does for us |
|---|---|
| `tools/traci/_simulation.py::findRoute` | the probe's current route in the twin (SUMO's router on the loaded network) |
| `tools/traci/_vehicle.py::rerouteTraveltime`, `setRoute`, `setAdaptedTraveltime` | reactive arm rerouting on current travel times; the selected route is applied as the vehicle's route |
| `tools/traci/_edge.py::adaptTraveltime` | how forecast edge costs can be pushed into a running simulation |
| `duarouter` (`--weight-files`, `--weight-attribute traveltime`, `--weights.expand`, `--weights.random-factor`, `--seed`, `--max-alternatives`) | candidate generation: run 0 exact forecast weights, runs 1..K-1 randomized weights = SUMO's documented route-diversification mechanism (`docs/web/docs/Simulation/Routing.md`, "Randomized travel times") |
| `docs/web/docs/Demand/Dynamic_User_Assignment.md`, `tools/assign/duaIterate.py` | the reference for route alternatives (`.rou.alt.xml`, `--max-alternatives`, Gawron/logit choice) that our K-candidate request follows |
| `docs/web/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.md` (`routeDistribution`) | the route-set format SUMO itself uses to hold alternatives |

What is ours (thin): the forecast-to-cost conversion, the cost evaluation of routes SUMO returned,
the threshold and the admission gates. No shortest-path code of our own.
