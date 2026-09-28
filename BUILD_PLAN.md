# TrafficTwin: Feature Contract and Build Order

## Purpose

Can predicted future traffic, communicated through a V2X system, improve routing
compared with reactive traffic management?

The product is an executable research experiment, not a Google route-search clone.
Dynamic means a user action starts computation and returns traceable outputs. It
does not mean recorded observations are live, synthetic demand is measured traffic,
or an emulator is physical radio hardware.

## Folder Ownership

```text
backend/                   FastAPI application
  app/api/                 HTTP validation and response handling
  app/datasets/            Dataset upload and city-input adapters
  app/forecasting/          Web prediction/training adapters (migration pending)
  app/simulation/           Interactive simulation adapters
  app/routing/              Web route/trip adapters
  app/evidence/             Read-only evidence and causal-trace readers
  app/live/                 External reference providers
frontend/                  Browser application, served by FastAPI
  pages/                   System, Prediction, Control Room, Results
  components/              Reusable controls and panels
  services/                API client and browser services
  styles/                  Shared styles
src/
  traffictwin/             Shared scientific implementation
    data/                  Provenance
    forecasting/           ForecastService and canonical ModelRegistry
    optimization/          Future costs, route optimizer, coverage diagnostics
    networking/            Simulated V2X channel and state correction
    digital_twin/          SUMO runtime helpers
    orchestration/         Scientific controller and execution jobs
    configuration.py       Shared server-side credential lookup
  pipeline/                Existing research dependencies and compatibility code
experiments/               Executable protocols, diagnostics, sweeps, notebooks
data/                      Dataset/network inputs, not application source
configs/                   Non-secret settings; see configs/README.md
results/                   Generated logs, metrics, reports and preserved evidence
tests/                     Scientific and cross-package tests
backend/tests/             HTTP and web-adapter tests
legacy/                    Retired implementations, not the current application
paper_labs/                Frozen historical reproductions
upstream/                  External implementation pins
.env                       Optional local credentials; ignored and never exported
```

`src` is not another backend. Its algorithms serve both the API and experiments.
`data` holds inputs; `results` holds outputs. Separate folders are useful when each
has a clear owner. The old root `dhakaflow/` contained only a private `.env`, not
another app. Its file moves to root `.env`; the previous core `.env` remains a
compatibility fallback. Do not recreate a source package for secrets.

## Feature List

| Feature | User input -> computed output | Current state | Completion check |
| --- | --- | --- | --- |
| Data validation | Dataset/window -> shape, chronology, graph, missing-data and provenance checks | METR-LA path exists; generic uploads remain separate | Invalid shapes/graphs rejected; no silent dataset substitution |
| Traffic prediction (DL) | Observation window -> horizon forecasts and persistence comparison | Canonical Graph WaveNet service exists; web inference paths are not all unified | Fresh tensor/forecast hashes, checkpoint SHA, runtime, units, horizons and held-out error |
| Route optimization | Vehicle state and future costs -> candidates, admission and recommendation | Controller exists; mapping coverage is limited | Every chosen/rejected action explained from candidate and coverage logs |
| Computer networking | STATUS and ROUTE_RECOMMENDATION -> receipt/drop/expiry/application | SIMULATED V2X EMULATOR exists | Message IDs connect TX/RX/TTL/latency to the actual SUMO action |
| Digital twin | Frozen scenario, seed, information source -> stepping SUMO and metrics | Fresh Control Room execution exists | TraCI actions and measured logs, not decorative animation |
| Controlled comparison | Matched arms/seeds -> raw metrics, paired differences, CI and gates | Frozen evidence and tooling exist | Fresh/reused arms distinguished; gates computed; negative results retained |
| Causal inspection | Select vehicle -> observation, decision, message and route-change trace | Available for recorded and completed fresh runs | Exact persisted identifiers; missing evidence not invented |
| Dhaka external reference | Route/corridor -> external traffic-aware response | Separate deployment prototype | Provider status/time explicit; never labelled local DL validation |

One dataset does not make research weak, and four datasets do not make it valid.
Only METR-LA has the established Graph WaveNet validation here. More benchmarks
would be separate generalization experiments, not a prerequisite for fixing this
closed loop. Do not claim collected or trained datasets that are absent.

## Architecture Rules

1. Frontend calls HTTP; it never invents scientific results or opens local evidence.
2. Routers validate and dispatch. File parsing belongs to evidence readers; jobs
   belong to orchestration; scientific inference belongs to ForecastService.
3. Scientific modules must not import the backend or frontend.
4. Experiments own protocols, seeds and comparisons; algorithms do not run sweeps
   during import or own UI state.
5. Extract responsibilities, not arbitrary blocks just to meet a line limit. Use
   meaningful domain names and compatibility imports until callers migrate.
6. Do not move frozen paths without a move table, reference checks and content-hash
   verification. Never edit evidence to make the structure look clean.
7. `pipeline` dependencies are not all obsolete. Migrate dependency-by-dependency;
   do not delete this tree or wrap it in another unexplained folder.

## Seven Phases, in Order

### 1. Ownership and safe cleanup (in progress)

Consolidate credential lookup; remove the credentials-only root folder. Separate
causal evidence processing from the V2X router. Next extract responsibilities from
`backend/app/simulation/runtime.py` (catalog, lifecycle, stepping, serialization),
`src/traffictwin/orchestration/closed_loop.py` (protocol, demand, control, reporting),
and web prediction/training adapters. Resolve callers of the removed
`dashboard.backend` compatibility package in a dedicated migration; do not silently
restore deleted code or skip failing tests.

Exit: API contracts and focused tests pass; scientific evidence is unchanged;
remaining compatibility failures are listed explicitly.

### 2. One prediction path

Route scientific UI inference through the existing ForecastService/ModelRegistry.
Keep prototype adapters separate until migrated. Require dataset/window identity,
checkpoint, tensor/forecast hashes, shape, units, graph, horizon, timing and validation
evidence. Cached output must identify its originating inference. No new model and
no evaluation-seed tuning.

Exit: valid input triggers a checkpoint pass; incompatible input fails visibly;
the API and controller use the same forecast contract.

### 3. Route-relevant observability

Read the existing frozen coverage diagnostic before choosing an intervention.
Expose DIRECT/DERIVED/UNPRICED coverage and candidate-decision evidence. Retain full
oracle, coverage-limited oracle, persistence and GWNet comparisons. Distinguish
forecast/ranking error from missing coverage and control rejection. Do not invent
retrospective candidate logs or expand coverage to chase an outcome.

Exit: a proposed mapping/control intervention is justified by measured gap attribution.

### 4. Networking and simulation integration

Finish the event contract across STATUS, receipt, inference, recommendation,
delivery, expiry, rejection and TraCI application. Keep frozen networking unchanged;
latency/loss explorations are separately named diagnostics.

Vehicles can represent on-board units, and the server/channel can represent
communication infrastructure in software. This is system-level emulation, not
physical-device or radio-propagation validation.

Exit: selected-vehicle traces reconcile with TX/RX/PDR and applied-action counts.

### 5. Repeatable end-to-end jobs and results

Harden start/cancel/status, interrupted-worker recovery and provenance export.
Keep exploratory one-seed executions separate from predefined multi-seed evaluation.
Preserve all seeds, settings and failures.

Exit: one command produces report.json, summary.md, plots, vehicle_trace.json and
provenance.json from logs; identical inputs reproduce recorded behavior.

### 6. Four focused UI surfaces

Finish System (availability/provenance), Prediction (fresh forecast), Control Room
(execution/trace), and Results (matched comparison). Retire legacy navigation only
after useful workflows migrate. Show pending/failed/missing states. The fresh
Control Room already exists; this is integration, not a replacement app.

Exit: a judge can choose input, start computation, inspect an action, and see a
computed comparison; desktop/mobile browser tests cover that workflow.

### 7. Research release

Produce one reproduction guide and credential-screened evaluation bundle. Reconcile
documentation only after code and evidence agree. Report forecast validity,
future-information value, predictive control versus reactive, learned advantage
versus persistence, and Dhaka readiness as separate computed gates.

Exit: clean-environment setup, hashes, tests and limitations are available. GWNet
advantage over persistence remains NOT ESTABLISHED unless a new predefined,
independent evaluation establishes it. Dhaka remains a prototype.

## Start and Verify

```bash
python -m pip install -r requirements.txt
python -m pip install -r backend/requirements.txt
python -m pip install --no-deps -e .
DHAKAFLOW_NO_OBSERVATORY=1 make app PORT=8008
```

Frozen Scenario A needs prepared local data, the verified checkpoint, pinned model
implementation and SUMO, not Google/LLM API keys. Structural cleanup must not launch
AWS training or paid live sampling. Web dependencies are listed in backend/requirements.txt.

```bash
python -m pytest -q backend/tests/test_scientific_execution.py backend/tests/test_api.py
make canonical-package  # package existing evidence, not fresh execution
```

Fresh execution and recorded replay are distinct modes. A single-seed demo checks
mechanism/reproducibility; it is not new significance evidence.
