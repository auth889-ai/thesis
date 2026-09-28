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
  interfaces/    abstract contracts of every subsystem
  common/        city model, reality labels, units, typed records, registries
  perception/    vehicle detection and tracking (RT-DETR, ByteTrack) — off the canonical path
  control/       signal-control baselines and RL arms — the control benchmark
  tools/         upstream fetch, reproduction records
  research_status.py, paths.py, configuration.py

apps/api/app/                      FastAPI application — thin routers, no science
  main.py, config.py, credentials.py
  api/           one router per page or resource (system, predictions, routing, simulation, v2x,
                 experiments, stress, references, research, training, cities, live_reference)
  services/      request-scoped orchestration that calls traffictwin (trip analysis jobs, training jobs,
                 execution jobs); no algorithm lives here

apps/web/                         browser application (ES modules, no build step)
  index.html, app.js (hash router)
  pages/         one file per page: home, prediction, control_room, results, references, system, models,
                 city, live, network, advisor, twin
  components/    shared widgets (map, cards, tables, tickers)
  services/      api client, basemap, streaming
  styles/

research/                      CLI entry points only (argparse + call into traffictwin.protocols)
configs/                          YAML settings per subsystem
tests/                            mirrors the packages: tests/traffictwin, tests/backend, tests/frontend, tests/platform
docs/                             structure, methodology, references (generated), reports
results/                          generated evidence; only small summaries are versioned (see .gitignore)
data/                             datasets and built scenarios (not versioned)
upstream/                         pins and manifests of official third-party code (no clones)
```

## Migration status

Done (2026-09-28). The old `src/pipeline` research package (183 modules) and the `src/dashboard`
compatibility shims are gone; every module lives in `traffictwin` and every script runs as
`python -m traffictwin.<module>`. The frozen paper labs, the legacy dashboard, the export bundles and the
archived datasets were moved outside the repository (`~/thesis_archive_<date>/`); the assets the
application reads from them are versioned in `data/cities/dhaka_r1` (gzip networks + manifest) and
`results/utd19`.

Additional layers that the migration surfaced: `traffictwin/interfaces` (subsystem contracts),
`traffictwin/common` (shared vocabulary: city model, reality labels, units, registries),
`traffictwin/perception` and `traffictwin/control` (the detection and signal-control subsystems, off the
canonical closed-loop path), `traffictwin/tools` (upstream fetch, reproduction records).

Still to do: split `apps/api/app/simulation/runtime.py` and `apps/api/app/routing/trip_analysis.py` into
services; retire or promote the ten `apps/web/pages/legacy/*` pages; give the frontend a `package.json`
with a dev server and a test runner (Vite + Vitest) and migrate it to TypeScript one page at a time.

## Rules the test enforces

- no module over 400 lines outside `archive/`
- nothing outside `src/traffictwin` imports `pipeline.*` once its step is done
- `apps/api/app/api/*` import only `traffictwin`, `app.services`, FastAPI and stdlib
- `apps/web/pages/*.js` import only `../components` and `../services`
- `archive/` is never imported
