# core/simulation — the SUMO digital twin, routing, signals, closed-loop control

Everything that runs in Eclipse SUMO or plans routes:
- the city twin built from OpenStreetMap;
- the routers (SUMO network, Valhalla);
- signal control;
- the forecast-aware closed-loop routing study (**RQ2**).

The ambulance study (**RQ3**) has its own README in `ambulance/`.

## Papers and official repositories
From `third_party/SOURCES.md` (first table, "Ambulance alert phase", "Whole-city routing", "Works with weak signal").

| Source (venue) | Version | Licence |
|---|---|---|
| Eclipse SUMO: Lopez et al., "Microscopic Traffic Simulation using SUMO", IEEE ITSC 2018 | tag `v1_27_1`, commit `7717f2379d9e314a0c81c5cec748444de06a2a91` | EPL-2.0 |
| OpenStreetMap through Overpass (roads, buildings) | `osm_base` date in each `evidence/cities/<city_id>/build.json` | ODbL 1.0 |
| Valhalla routing engine (no paper) | release 3.9.0 | MIT |
| Geofabrik extracts (Bangladesh, SoCal) | dates and sha256 in `evidence/routing/` | ODbL 1.0 |
| adaptive-traffic-signal-rl (no paper): emergency override and phase state machine | `b62436b5d5fb1e5d07008d6f486f1a06a09ff64a` | MIT |
| Bartendr (ACM MobiCom 2010): track-based signal prediction | paper | © ACM; method only |
| MAPPO, Max-Pressure, SUMO DUE/DSO tools (signals and routing arms) | not recorded in third_party/SOURCES.md (MAPPO pinned in `upstream/UPSTREAM_PINS.yaml`) | not recorded in third_party/SOURCES.md |

## Which file implements which part
| Folder / file | Part |
|---|---|
| `twin/scenario_builder.py`, `twin/city_pipeline.py` | Any city with a config: OSM roads → `netconvert` (with `--tls.guess`, and `--lefthand` for a left-driving city) → `randomTrips` demand; buildings from OSM. |
| `twin/calibration.py`, `twin/sensor_map.py`, `twin/sensor_graph.py` | Counts become SUMO edge data; published detector ids snapped to edges. |
| `twin/live/` | The live twin: SUMO stepping in a thread, every vehicle on the map, counterfactual jobs. |
| `routing/valhalla.py` | Client of our own Valhalla server: routes, isochrones, the time matrix, map matching. |
| `routing/forecast_costs.py`, `routing/edge_costs.py`, `routing/route_optimizer.py` | A forecast becomes future edge travel times; candidates; capacity-aware admission. |
| `routing/network_assignment.py`, `routing/graph_router.py`, `routing/demand.py` | Network-level assignment and the system-optimal rule; multi-OD demand. |
| `routing/signal.py` | Where a route may have weak signal, after Bartendr's per-heading track (used by RQ5). |
| `routing/trip/` | One trip analysed: places, candidate routes, forecast pricing, a stated choice. |
| `signals/preemption/` | The reused emergency override and safety state machine (`emergency.py`, `phases.py`, copied with a credit header and one import line changed) and our SUMO adapter. |
| `signals/sumo_marl_env.py`, `signals/train_sumo_signals.py`, `signals/eval_policy.py` | A 17-agent SUMO signal environment in MAPPO's contract, training and evaluation. |
| `signals/signal_baselines.py`, `signals/run_control_baselines.py` | Fixed-time and Max-Pressure baselines. |
| `closed_loop/control/closed_loop.py` | RQ2's loop: real traffic state → validated forecast → SUMO edge costs → route optimiser → V2X → vehicles. |
| `closed_loop/protocols/oracle_gate.py`, `learned_gate.py`, `controller_gate.py`, `statistics.py` | RQ2's outcome gates on paired seeds, and the computed controller status. |
| `closed_loop/protocols/chains/` | End-to-end experiment chains (forecast-quality ablation, impairment, incident, real-demand arms, DUE vs DSO). |

## Substitutions and why
- **netconvert options:** `--tls.guess --tls.guess.threshold 30` and `--lefthand` are added (documented options) and recorded in each build's evidence.
- **Valhalla on our own server** instead of a hosted API, so routes, reach and the map app use one graph. Its default speeds are not measured traffic.
- **Demand is generated** (randomTrips, labelled SYNTHETIC / not calibrated) unless a study says it is matched to counts.
- **RQ2 ran in Los Angeles (METR-LA) only.** It was not run in Dhaka, which has no comparable sensor feed.

## Tests
| File | What it checks |
|---|---|
| `backend/tests/city/test_city_pipeline.py`, `test_city_layer.py`, `test_add_city.py` | Any city with a config can be built; nothing names a city; a city cannot claim what it lacks. |
| `backend/tests/city/test_calibration.py` | Counts become edge data; a miss is reported as a miss. |
| `backend/tests/routing/test_valhalla.py` | Valhalla answers read faithfully; recorded stretches re-timed and labelled; honest refusals. |
| `backend/tests/rebuild/test_route_optimizer.py`, `test_network_assignment.py` | Forecast → edge costs → candidates → admission; diverse candidates really differ. |
| `backend/tests/rebuild/test_oracle_gate.py`, `test_learned_gate.py`, `test_v2x_closed_loop.py` | Gate statistics and protocol identity; a delivered route recommendation changes a vehicle's route on a small grid. |
| `backend/tests/signals/test_preemption_adapter.py` | Preemption drives a junction only through its own programme's phases. |
| `tests/platform/test_p0_vertical_slice.py`, `test_route_decision_guard.py` | The routing graph, alternatives, the honesty gates and the acceptance guard. |

## Results
- **RQ2:** `results/v2x/controller_status.json`, current arm `predictive_corrected_v2x`, run `results/v2x/closed_loop/la_c4_central_wide_prepeak_ideal_p30_…`.
  - status: `TRAFFIC_BENEFIT_NOT_ESTABLISHED`;
  - `FUTURE_INFORMATION_VALUE`: `ESTABLISHED`;
  - oracle against reactive: mean −1.83 % (95 % CI −3.52 to −0.14), "HELPED";
  - predictive against reactive: −0.91 % (CI −2.15 to 0.33), "INCONCLUSIVE";
  - 5 evaluation seeds.
- Stress scenarios: `results/v2x/STRESS_REPORT.md`. Twin builds: `evidence/cities/`.
