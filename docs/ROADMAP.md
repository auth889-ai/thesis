# TrafficTwin — how it works and how it is built, phase by phase

Companion to `WORKFLOW.md` (what happens on one request) and `BUILD_PLAN.md` (the research contract).
This document is the engineering plan: the stack, the data flow, and the phases with their deliverables
and the evidence each one must produce before the next starts.

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

Each phase ends with something a person can use and something a reviewer can check.

### Phase 0 — the two surfaces (done)
App (`/today`, `/plan`, `/city`) for commuters; lab (`/lab/*`) for evidence. Fresh inference on every forecast.
Live roads for any city, rail option, the city map, the assistant in plain words, MCP. Evidence: the test
suite, the lab pages, `WORKFLOW.md`.

### Phase 1 — data foundation
- Loaders with manifests and hashes for METR-LA, PEMS-BAY, PEMS03/04/07/08, LargeST, UTD19; one interface (`app.data.datasets`).
- Phone-reported speeds: `POST /api/probe/speeds` from the mobile app (consented, anonymised, batched), stored per road segment; this is the non-provider history a city model may be trained on.
- Crowdsourced reports: `POST /api/reports` (incident, waterlogging, closure, strike), shown on the Plan map, and a route warning when a report lies on a route.
- Evidence: dataset cards in the lab (rows, nodes, span, hash), a probe count per city.

### Phase 2 — the model campaign
- Train GWNet, STID, STAEformer, DCRNN, D2STGNN on the benchmarks with the official configs on AWS; BigST/PatchSTG for LargeST scale; Chronos, TimesFM, OpenCity zero-shot.
- One protocol: chronological split, MAE/RMSE/MAPE at 15/30/60, skill vs persistence, a card per model per dataset, the eligibility gate.
- A first city model on probe data once a city has enough of it (the gate decides when).
- Evidence: the lab's Models page with every card and checkpoint hash; `results/forecasting/benchmark.md`.

### Phase 3 — serving any city
- City onboarding: name → OSM network → SUMO net → sensor or probe mapping → candidate models → gate → the city appears.
- Inference service: the eligible model runs on request per city; ONNX export where it cuts latency.
- Evidence: an onboarding log per city; latency per request on the lab's System page.

### Phase 4 — the consumer product
- Accounts (Cognito), saved commutes, reminders delivered by SNS at the recomputed departure, per-person calibration of the on-time probability from actual arrivals, data deletion.
- Monitoring and replanning: a saved goal is re-priced when the forecast or an incident changes it materially; the person gets the reason.
- Memory for the assistant: preferences and recurring patterns (buffer before interviews, reliability over speed), retrieved per goal.
- Mobile release (EAS build, privacy policy, data-safety form).
- Evidence: outcome records (recommended vs actual departure and arrival), the audit chain, crash-free sessions.

### Phase 5 — the city and business products
- Incident alerts for traffic police from probe speeds (the detector already in the twin).
- Signal-timing recommendations from the twin, in the Green Light style: per intersection, applied with existing hardware.
- What-if runs as a service: a closure, a bus lane, staggered hours, tested before spending.
- Fleet ETA API for delivery and courier operators.
- Evidence: a twin run per recommendation with its confidence interval; API latency and accuracy per fleet.

### Phase 6 — scale
- Stateless API on ECS behind a CDN, Postgres with Timescale for series, Redis only for sessions, S3 for artefacts, per-city shards, load tests published.
- Per-request inference stays; GPUs scale with request rate, and same-second requests may share one forward pass (disclosed).
- Evidence: load-test report, cost per city per day.

### Phase 7 — research extensions
- Coverage expansion (more roads priced), a learned reroute controller, federated training across the simulated V2X channel, the oracle-first protocol on a second city.
- Evidence: the same gates, computed, on new runs.

## 4. Rules that hold in every phase
- Nothing on a page is typed in; every number comes from a file the pipeline wrote or a computation for this request.
- A provider is a live external reference, never a training target.
- A model drives advice only after the gate.
- Irreversible actions pause for approval; every decision is in the audit chain.
- One file, one responsibility; official implementations unchanged; each phase's evidence in the lab.
