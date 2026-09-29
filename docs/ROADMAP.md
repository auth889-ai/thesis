# LIFE OS × TrafficTwin — roadmap in controlled phases

Companion to `ARCHITECTURE.md` (what exists), `WORKFLOW.md` (the core loop), `EXPERIMENT_PROTOCOL.md` (the research
contract) and `REFERENCE_IMPLEMENTATIONS.md` (what each phase studies). One phase at a time; a phase ends only when
it works end-to-end with tests and evidence, and is committed. Reference repositories are inspected only in their phase.

## 1. The stack, and why each piece

| Layer | Technology | Why |
|---|---|---|
| API | FastAPI, one app organised by domain (`backend/app/<domain>`), Pydantic contracts, OpenAPI export | small files with one responsibility; the web and mobile clients are typed from the same document |
| Forecasting | PyTorch models trained with the official BasicTS harness on AWS GPU (g5); Chronos and OpenCity zero-shot; ONNX export planned for serving | official implementations are the algorithmic source of truth; the harness gives a single evaluation protocol |
| Live roads | Amazon Location Service Routes (HERE); OpenStreetMap Overpass for transit; the frozen OSM/SUMO network as the fallback | any city, real geometry, traffic where covered, and an honest fallback that says what it is |
| Recorded traffic | the project's own corridor recordings (5-minute bins), the recorder's congestion bands | the only Dhaka history that exists; used for the empirical on-time probability, never for model training |
| Digital twin | SUMO with TraCI, the simulated V2X channel, Eclipse MOSAIC for the ITS-G5 reference runs | the same network and demand for every arm; every reroute is a logged SUMO action |
| Assistant | Amazon Bedrock (Converse API: Claude Haiku 4.5, Nova Lite fallback); the tool registry; the typed permission engine; hash-chained JSONL audit | plans over real tools only; asks before irreversible actions; every step verifiable |
| Agents | MCP server (Streamable HTTP, 2025-11-25) at `/mcp` | Alexa+ and any MCP client call the same tools, under the same audit |
| Web | Vite, React 19, TypeScript, TanStack Query, MapLibre, Chart.js, Vitest | one feature folder per page; files under 200 lines by test; every number from the API |
| Mobile | Expo / React Native, typed from the same OpenAPI document | one API, two clients |
| Storage | SQLite for goals, tasks, reminders, commutes, reports; JSONL for the audit; run files under `results/` for evidence | small now; the schema moves to Postgres unchanged when accounts arrive |
| Cloud | AWS: EC2 GPU for training, S3 for artefacts and job logs, Bedrock, Location, SNS for reminders, Cognito for accounts, ECS for the API | one credential, one bill, the AWS Builder track |

## 2. Data flow on one request ("leave when?")

```
client ──POST /api/commute/plan──▶ commute.service.plan
      places.resolve_place ──▶ known place | OSM geocoder (bounded to the city)
      live.provider() ──▶ Amazon Location: K routes, geometry, free-flow, traffic where covered
      corridor polylines ──▶ which recorded corridors each route runs along (runs_along)
      for every candidate departure: distribution of travel time = free-flow × recorded band of the worst corridor
      on-time probability = share of that distribution meeting the deadline − buffer
      recommended = latest departure with ≥ 80 %
      transit.service.plan ──▶ OSM rail lines within walking reach: walk · wait · ride · walk
◀── one answer with its provenance sentence (provider, coverage, model, what is estimated)
```

Everything runs when asked. There is no stored answer; a fresh model pass and fresh provider calls every time.

## 3. Phases

Status on 2026-09-29. **done** = works end-to-end with tests; **partial** = exists but misses listed deliverables; **—** = not started.

| # | Phase | Studies | Deliverables | Status |
|---|---|---|---|---|
| 0 | Repository and architecture audit | our code | `ARCHITECTURE`, `WORKFLOW`, `ROADMAP`, `REFERENCE_IMPLEMENTATIONS`, `THIRD_PARTY_LICENSES`, `EXPERIMENT_PROTOCOL` | done (this commit) |
| 1 | LIFE OS agent core | tahodev/openmuse, CopilotKit/openmuse, openai-agents-python | persistent Goal/Step, states, durable background execution with a lease, resume after restart, cancel, approvals, activity feed, tests | done (see phase log) |
| 2 | Consumer LIFE OS shell | (CopilotKit UI patterns if useful) | Today · Agent · Goals · Activity · You; no research internals in the consumer UI | done (see phase log) |
| 3 | Life Twin | — (our own) | structured twin; feasibility engine: feasible / risky / impossible, conflicts, free windows, buffers; unit tests | partial |
| 4 | Core forecasting reproducibility | DCRNN, Graph WaveNet, STID, STAEformer (one at a time, after persistence and historical average) | full run records on METR-LA and PEMS-BAY, then PEMS | partial (GWNet and STID trained via BasicTS; records incomplete) |
| 5 | Cross-city / foundation models | OpenCity, UniST, RAST | local vs zero-shot vs few-shot; days-of-data curve; validation gate before any advice | partial (OpenCity zero-shot exists) |
| 6 | Large-scale evaluation | LargeST | dataset manifests and cards; SD region first | — |
| 7 | Calibrated uncertainty | MAPIE | conformal intervals for ETA and departure; coverage, width, drift; reliability only from validated intervals | — |
| 8 | Probe data and map matching | Map-Matching, Valhalla Meili | consented phone observations → segment speeds; never called live traffic until real observations exist | — |
| 9 | Sensor fusion | — (our own) | interpretable baseline, then weighted / Kalman / learned; provenance per fused state | — |
| 10 | Multimodal routing | OpenTripPlanner, Valhalla, docker-valhalla | car / walk / transit / mixed candidates from infrastructure; our contribution sits above | partial (Amazon Location + OSM transit) |
| 11 | Future-aware routing and departure optimisation | — (ours) | segment entry times → forecast → cost distribution → reliability; latest departure meeting the target; baselines incl. oracle | partial (`commute/`, `routing/forecast_costs.py`) |
| 12 | SUMO digital twin | eclipse-sumo | paired scenarios, versioned configs, the metric set | partial (oracle-first protocol exists) |
| 13 | Traffic signal control | sumo-rl, LibSignal, RL_signals_CityFlow, smart-traffic-rl | fixed → actuated → max pressure → published RL → ours only if justified | partial (`signals/` benchmark) |
| 14 | Learned rerouting | — | policy over forecast in the twin vs reactive / forecast-aware / oracle | partial (`protocols/learned_gate.py`) |
| 15 | V2X research | eclipse-mosaic, SUMO-V2X example | penetration / latency / loss / interval sweeps | partial (`networking/`) |
| 16 | LIFE OS × TrafficTwin integration | — | the interview workflow end-to-end with real tool results | partial |
| 17 | Calendar / email / files / tasks | — | connectors as tools under the same permission engine | partial (calendar ICS, tasks) |
| 18 | Event-driven monitoring | — | triggers; recompute only affected goals | partial (polling monitor) |
| 19 | Outcome learning | — | outcome records and personal calibration; no silent global retraining | partial (`plan/outcomes.py`) |
| 20 | Domain workflows | — | study, job, travel, errands on the same engine | — |
| 21 | Research lab | — | `/lab/{datasets,models,forecasting,routing,digital-twin,v2x,experiments,references}` | partial |
| 22 | Scale architecture | — | accounts, Postgres, workers, queues, S3, ECS, observability, shards; freshness fields on every result | — |
| 23 | Alexa+ / hackathon | — | MCP tools executed for real from Alexa+; one plan-changing event | partial (MCP server live) |

## 4. Rules that hold in every phase
- Nothing on a page is typed in; every number comes from a file the pipeline wrote or a computation for this request.
- A provider is a live external reference, never a training target.
- A model drives advice only after the gate.
- Irreversible actions pause for approval; every decision is in the audit chain.
- One file, one responsibility; official implementations unchanged; each phase's evidence in the lab.
- Amazon Bedrock stays the LIFE OS model unless a documented technical reason changes it; TrafficTwin stays the thesis core.
- Commit after each completed phase; never continue because the UI looks complete.

## 5. Phase log

| Phase | Date | What was verified | Evidence |
|---|---|---|---|
| 0 | 2026-09-29 | the six documents written from the code as it is | commit `adca7e36` |
| 1 | 2026-09-29 | goals run on a background worker under a lease (`agent/worker.py`); the API answers at once and the page polls; a goal left running by a killed process is recovered at the next start or reaper pass with its in-flight call marked interrupted; cancel stops a running goal at its next step and a paused goal at once; approvals bound to the exact action with expiry, standing rules, rejection reason; signed audit checkpoints | `backend/tests/test_worker.py` (8), `test_approvals.py` (8), `test_agent.py`, `test_life_twin.py`; full suite 558 passed, 5 skipped; live: API killed with `kill -9` 1.5 s after a submit, restarted, the goal finished with audit kinds `intent, interrupted, decision, result, decision, result, summary` and an intact chain; a second goal cancelled after two steps with summary "stopped by you" |
| 2 | 2026-09-29 | five consumer pages on one sidebar: Today (stats row, timeline, at-risk with reasons, suggestions, goals in progress, updates), Agent (the conversation, recent goals, yours, standing decisions, activity), Goals (grouped by what they need; overview with counted progress, next action, risks, what the goal created), Activity (audit and replans merged, filters, chain status), You (memory by kind with forget, permissions policy and tools, standing decisions, calendar and connectors, privacy with export and confirmed erasure); Plan and City stay reachable from Today; the lab is untouched | `backend/tests/test_you.py` (3), web `today/hooks.test.ts`, `goals/GoalOverview.test.ts`; full suite 561 passed, 5 skipped; web 27 passed; every page rendered in the browser against the live server |
