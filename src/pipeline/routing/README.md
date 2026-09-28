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

## Learned-model outcome gate (Blocker #6, 2026-09-06)

`learned_gate.py` — FINAL_LEARNED_PROTOCOL_v1. Does the trained, validated Graph WaveNet checkpoint
(`566b97d97943`, held-out skill 0.26 vs persistence on `user:los_angeles`) improve actual SUMO outcomes
on the Los Angeles scenario? Four arms on identical paired scenarios per seed — baseline (no rerouting),
reactive (`rerouteTraveltime` on current times), persistence-predictive and learned-predictive (both through
the production `edge_costs` → `route_optimizer` chain, only the forecast differs). Every learned run is a
fresh forward pass at one held-out dataset moment per seed; the detectors' measured speeds after that moment
are replayed as lane speed caps on their mapped edges in every arm, so the forecast has something real to
anticipate. Provenance `an_lg_*`, `rt_lg_*`, `sim_lg_*` records; report under `results/routing/learned_gate/`;
read-only `GET /api/experiment/learned_gate`. The oracle arm (`--with-oracle`) is research-only and never the
headline. Dev seeds 101–103 only for smoke; final seeds 301–320 never used for tuning.
