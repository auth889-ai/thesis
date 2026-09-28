# Backend

The FastAPI application lives in `app/`. Start it from the repository root:

```bash
python -m pip install -r backend/requirements.txt
make app
```

`app/main.py` assembles domain routers and serves `frontend/` at `/` and `/static`.
API documentation is at `/api/docs`. HTTP routes and contracts live in `app/api/`.

| Package | Responsibility |
| --- | --- |
| `app/api/` | Domain routers, request/response schemas, HTTP dependencies |
| `app/datasets/` | Uploads, dataset inputs, corridor definitions |
| `app/forecasting/` | Forecast/training jobs, road forecasts, prototype registry |
| `app/routing/` | Trip analysis and API-facing optimization adapter |
| `app/simulation/` | Simulation jobs, live runtime, comparisons, command handling |
| `app/live/` | Google external-reference client and observation service |
| `app/evidence/` | Forecast ledger and evidence readers |

Only app assembly, configuration, and credentials remain at the package root.
Shared scientific algorithms belong in `src/traffictwin/`, not the HTTP packages.
In particular, the canonical ForecastService/ModelRegistry and V2X controller stay
in that package; these web adapters do not create another scientific implementation.
Some existing adapters still need responsibility-level extraction; grouping them
does not assert that every class is already single-purpose.

Run API tests with `python -m pytest backend/tests` from the repository root.
Some old tests/callers still reference `dashboard.backend`, whose compatibility
package has been removed. Use canonical `backend.app` imports for new code;
remaining migration is tracked in [BUILD_PLAN.md](../BUILD_PLAN.md).

`app/evidence/vehicle_trace.py` reads causal run evidence; its V2X endpoint handles
HTTP only. Optional credentials use root `.env`, through
`traffictwin.configuration`, with legacy file fallback during migration.
