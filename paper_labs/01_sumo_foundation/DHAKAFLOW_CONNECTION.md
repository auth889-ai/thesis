# DHAKAFLOW_CONNECTION — what Lab 01 graduates into the platform

Lab 01 is a reproduction/validation capsule; the *capabilities* it proved are
what move into the permanent `dhakaflow/` platform. Nothing here changes Lab 01's
frozen numbers — this document defines the interface debt for Sprint A.

## Graduating capabilities → target platform module

| Lab 01 capability (validated) | Where it proved out | Graduates to | Interface it will satisfy |
|---|---|---|---|
| Deterministic SUMO run lifecycle (argv, seed, outputs, teardown) | `src/dhakaflow_lab01/runner.py::run_one`; 15/15 clean runs | `dhakaflow/simulation/` | `TrafficScenario` (scenario id, net, routes, seed, duration) |
| TraCI session handling (`start → step → close`, tool discovery across install layouts) | `runner.py::_import_traci`; Colab + local | `dhakaflow/simulation/` | `DigitalTwin.step()` backend |
| Per-step observation extraction (halting counts, queue ratios, running/arrived) | `runner.py` step loop → `step_metrics.csv` | `dhakaflow/simulation/` + `dhakaflow/evaluation/` | `TrafficObservation` |
| Signal action interface (extend / terminate green, phase bookkeeping) | `controllers/base.py`, `max_pressure.py`, `actuated.py` | `dhakaflow/control/` | `TrafficController.act() → SignalAction` |
| Safety guards (min-green, max-green, yellow preserved, no all-green) | pre-decision guards + `test_scenario_xml.py`; 0 collisions | `dhakaflow/safety/` | `SafetyShield.filter(action)` |
| Metric aggregation (travel time, p95, waiting, queue mean/p95/max, throughput, proxies) | `metrics.py`; independently recomputed | `dhakaflow/evaluation/` | `TrafficMetrics` |
| Fair multi-seed benchmark harness (identical demand across arms) | `scripts/run_matrix.py`; 5 seeds × 3 controllers | `benchmarks/` | benchmark runner contract |
| Evidence/provenance collection (manifests, checksums, upstream integrity guard) | `run_bologna_unmodified.sh`, run manifests, `evidence_lab01.zip` | `dhakaflow/common/` | artifact manifest schema |
| Figure generation from real artifacts | `scripts/make_figures.py` | `dhakaflow/visualization/` | figure contract (`FIG/NN_name.png`) |

## Explicitly identified but NOT exercised here

- **SUMO sublane model** (ITSC §IX-C: *"model heterogeneous traffic and reduced
  lane discipline"*) — the officially supported mechanism for Dhaka's mixed
  rickshaw/CNG/bus/motorcycle flow. Recorded as the intended tool for **Lab 13**
  Bangladesh vTypes. Lab 01 deliberately keeps the plain lane model.
- **Calibration/validation criteria** from ITSC §VII (RMSE; ">85 % of counts
  within 15 %"; simulated-vs-measured scatter) — adopted as the acceptance form
  for **Lab 13**, not evaluated in Lab 01.
- **Detector-based measurement** (Bologna's 636 induction loops) — the analogue
  of our future camera-derived sensors (**Lab 06**).

## Downstream dependency chain

```
Lab 01 (this)  →  Lab 02 real Dhaka network  →  Lab 13 calibrated Dhaka twin
                                                      │
        ┌─────────────────────────────────────────────┴──────────────┐
        ▼                                                            ▼
Lab 14 network-scale Max-Pressure (the serious classical benchmark)   Lab 22 routing
        ▼
Labs 15–19  SUMO-RL/PPO → PressLight → FRAP → CoLight → MAPPO
        ▼
Lab 20  Forecast-Aware MAPPO  (main original contribution)
        ▼
Lab 21  safety shield + robustness/sim2real      Lab 23 priority control
```

Every one of those labs consumes Lab 01's runner, action interface, safety
guards, metrics and benchmark harness. **None of them is implemented or
integrated here** — that is the point of the freeze.
