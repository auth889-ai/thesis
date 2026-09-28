# Project structure — target and rules

One Python package, one web application, one place for experiments, one place for evidence.
Every module has one responsibility and stays under ~400 lines; a file that grows past that is split
by responsibility, never by "part 1 / part 2". The layout is enforced by
`tests/platform/test_repo_architecture.py`.

```
backend/
  app/                         the application, organised by domain (one package per bounded context)
    main.py                    assembly only · router.py: every domain registers its router here
    config.py paths.py evidence_paths.py credentials.py dependencies.py middleware.py schemas.py   (global modules)
    data/                      datasets, uploads, city model, recorded history, live_providers/ · router.py
    forecasting/               training/ evaluation/ live/ opencity/ adapters/ federated/ operations/ service.py · routers/
    routing/                   edge costs, route optimizer, forecast costs, local router, trip analysis, assignment, decision guard · router.py
    networking/                channel, state correction, v2x bus, mosaic/ · router.py
    twin/                      SUMO runtime, scenario builder, sensor map, state, metrics, live/ · configs/ · router.py
    control/                   closed-loop controller, execution jobs, live controls, scenario
    protocols/                 gates, statistics, stress, reports, diagnostics/, chains/, evidence/, research_status · routers/
    platform/                  system router
    signals/  perception/      signal-control benchmark · detection subsystem (each with its configs/)
    interfaces/  common/  nlp/  tools/
  tests/                       grouped like the code (rebuild/, forecasting/, city/, federated/, live/, API tests)
  pyproject.toml  requirements.txt  README.md
frontend/                      web app (Vite, Vitest, TypeScript): index.html, src/{app.js, pages/, components/, services/, styles/}, dist/ when built
mobile/                        mobile app (Expo / React Native, TypeScript): App.tsx, src/api/client.ts — same API as the web app
research/                      protocol runners: closed_loop/ routing/ networking/ · reports/ (results builders) · notebooks/
infra/                         api.Dockerfile, docker-compose.yml, service.yaml
scripts/  docs/  data/  results/  tests/platform/  upstream/
```

## Migration status

Done (2026-09-28): steps 1–7. Remaining: retire or promote the ten `frontend/src/pages/legacy/*` pages; give the web app a `package.json` with Vite and Vitest and move it to TypeScript page by page; split `twin/live/runtime.py` (664 lines) and `routing/trip_analysis.py` (593 lines).

## Rules the test enforces

- no module over 400 lines (two known exceptions listed above)
- `router.py` / `routers/*` contain no algorithms: they call the domain's service code and return schemas
- every config lives next to the code that reads it (`<domain>/configs/`); no root `configs/`
- cross-domain imports use explicit module names (`from app.forecasting.operations import model_registry`)
- the application runs with `PYTHONPATH=backend`; nothing is pip-installed from this repository
