# Project structure — target and rules

One Python package, one web application, one place for experiments, one place for evidence.
Every module has one responsibility and stays under ~400 lines; a file that grows past that is split
by responsibility, never by "part 1 / part 2". The layout is enforced by
`tests/platform/test_repo_architecture.py`.

```
apps/
  api/                         FastAPI service — HTTP only
    app/main.py                application assembly
    app/api/router.py          the one aggregating router
    app/api/routes/            platform/ forecasting/ routing/ twin/ evidence/   (one module per resource)
    app/api/deps.py            request dependencies
    app/schemas.py             response contracts (Pydantic)
    app/core/                  settings.py, middleware.py
    app/services/              readers that turn evidence files into response models
    tests/
  web/                         browser app (ES modules): index.html, app.js, pages/, components/, services/, styles/, tests/
packages/
  traffictwin/                 the domain library (src layout, own pyproject.toml, tests/)
    src/traffictwin/
      data/                    datasets, uploads, city model, recorded history, live_providers/
      forecasting/             training/ evaluation/ live/ opencity/ adapters/ federated/ operations/ (registry, jobs) + service.py
      optimization/            edge costs, route optimizer, forecast costs, local router, trip analysis, network assignment, decision guard
      networking/              simulated V2X channel, state correction, v2x bus, mosaic/
      digital_twin/            SUMO runtime, scenario builder, sensor map, forks, metrics, live/ (live twin, comparisons, jobs)
      orchestration/           closed-loop controller and execution jobs
      protocols/               gates, statistics, stress calibration/experiment, reports, diagnostics/, chains/, evidence/
      control/  perception/    signal-control benchmark · detection subsystem (off the canonical path)
      interfaces/  common/     subsystem contracts · shared vocabulary (reality labels, units, registries, credentials, evidence paths)
      nlp/  tools/             incident classifier · upstream fetch, reproduction records
research/                      protocol runners: closed_loop/ routing/ networking/ · reports/ (results builders) · notebooks/
infra/                         api.Dockerfile, docker-compose.yml, service.yaml
scripts/                       download_assets.sh
docs/                          methodology, experiments, evaluation guide, references (generated), this file
data/                          datasets and built scenarios (not versioned, except data/cities/dhaka_r1 gzip networks + manifest)
results/                       generated evidence; only small summaries are versioned
tests/platform/                cross-cutting architecture and platform tests
upstream/                      pins and manifests of official third-party code (no clones)
```

## Migration status

Done (2026-09-28): steps 1–6c. Remaining: retire or promote the ten `apps/web/pages/legacy/*` pages; give the web app a `package.json` with Vite and Vitest and move it to TypeScript page by page; split `digital_twin/live/runtime.py` (664 lines) and `optimization/trip_analysis.py` (593 lines).

## Rules the test enforces

- no module over 400 lines outside `archive/`
- the library (`packages/traffictwin`) never imports the application (`app.*`)
- `apps/api/app/api/*` import only `traffictwin`, `app.services`, FastAPI and stdlib
- `apps/web/pages/*.js` import only `../components` and `../services`
- `archive/` is never imported
