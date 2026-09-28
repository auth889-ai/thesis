# Project structure — target and rules

One Python package, one web application, one place for experiments, one place for evidence.
Every module has one responsibility and stays under ~400 lines; a file that grows past that is split
by responsibility, never by "part 1 / part 2". The layout is enforced by
`tests/platform/test_repo_architecture.py`.

```
traffictwin/                      the library (installed as `traffictwin`, lives in src/traffictwin)
  data/          datasets (METR-LA, PEMS-BAY, PEMS04/08, uploads), recorded corridor history, provenance
  forecasting/   models (Graph WaveNet, DCRNN, STID, STAEformer via BasicTS; Chronos, OpenCity pretrained),
                 baselines (persistence, historical average, XGBoost, RandomForest), training jobs,
                 evaluation (held-out error, skill vs persistence), checkpoint registry
  routing/       edge costs from forecasts, route optimizer, local router (no external API), trip analysis
  networking/    simulated V2X channel, latency/loss profiles from Eclipse MOSAIC, online state correction,
                 MOSAIC penetration sweeps
  digital_twin/  SUMO scenarios from OSM, runtime (TraCI), identical-state forks, metrics, incident injection
  control/       closed-loop controller: rounds, budget, admission, recommendations
  protocols/     the research protocols: oracle gate, stress calibration, scenario A/B, controller gate,
                 statistics (paired t interval, bootstrap, Wilcoxon), report generators
  nlp/           incident classifier (Dabiri traffic tweets)
  research_status.py, paths.py, configuration.py

backend/app/                      FastAPI application — thin routers, no science
  main.py, config.py, credentials.py
  api/           one router per page or resource (system, predictions, routing, simulation, v2x,
                 experiments, stress, references, research, training, cities, live_reference)
  services/      request-scoped orchestration that calls traffictwin (trip analysis jobs, training jobs,
                 execution jobs); no algorithm lives here

frontend/                         browser application (ES modules, no build step)
  index.html, app.js (hash router)
  pages/         one file per page: home, prediction, control_room, results, references, system, models,
                 city, live, network, advisor, twin
  components/    shared widgets (map, cards, tables, tickers)
  services/      api client, basemap, streaming
  styles/

experiments/                      CLI entry points only (argparse + call into traffictwin.protocols)
configs/                          YAML settings per subsystem
tests/                            mirrors the packages: tests/traffictwin, tests/backend, tests/frontend, tests/platform
docs/                             structure, methodology, references (generated), reports
results/                          generated evidence; only small summaries are versioned (see .gitignore)
data/                             datasets and built scenarios (not versioned)
archive/                          frozen labs (paper_labs), legacy code — kept for provenance, never imported
upstream/                         pins and manifests of official third-party code (no clones)
```

## Migration from the current tree

`src/pipeline` (183 files, 27 000 lines, 13 sub-packages) is the old research code. It is migrated
into `traffictwin` one sub-package at a time, each step leaving the suite green:

| step | from `src/pipeline/…` | to `traffictwin/…` | notes |
|---|---|---|---|
| 1 | routing/ (oracle_gate, learned_gate, stats, decision_guard, forecast_to_costs, chains) | protocols/, routing/ | protocols get the gates and statistics; routing keeps cost building |
| 2 | v2x/ (closed_loop, stress_*, controller_gate, phase/stress reports, corridor_diversity, route_headroom, network_assignment) | control/, protocols/ | closed_loop is already duplicated in traffictwin.orchestration — keep one |
| 3 | forecasting/ (basicts_train, aws_train, evaluate_models, benchmark_floors, adapters, opencity_*, chronos, federated_forecast, live_to_edges) | forecasting/ | split training / evaluation / adapters / federated |
| 4 | city/ (sumo_scenario, sensor_map, coverage_rescue, datasets) | digital_twin/scenarios, data/ | |
| 5 | networking/, nlp/, federated/ | networking/mosaic, nlp/, forecasting/federated | |
| 6 | core/, adapters/, audit/, results/, upstream/, live/ | archive/ or folded where still used | perception/tracking adapters are off the canonical path |
| 7 | `src/dashboard/backend` alias shims | removed | once nothing imports the old flat names |

Then: `backend/app/simulation/runtime.py` and `backend/app/routing/trip_analysis.py` split into services;
frontend `pages/legacy/*` retired or promoted to `pages/` one file each; `legacy/`, `paper_labs/`
moved to `archive/`; root `main.py` becomes `traffictwin/cli.py`.

## Rules the test enforces

- no module over 400 lines outside `archive/`
- nothing outside `src/traffictwin` imports `pipeline.*` once its step is done
- `backend/app/api/*` import only `traffictwin`, `backend.app.services`, FastAPI and stdlib
- `frontend/pages/*.js` import only `../components` and `../services`
- `archive/` is never imported
