# LIFE OS · Life Twin · AccessTwin · TrafficTwin — roadmap in controlled phases

Companion to `PROBLEM.md` (the frozen problem, entities, hypothesis, metrics), `ARCHITECTURE.md` (what exists), `WORKFLOW.md`,
`EXPERIMENT_PROTOCOL.md` and `REFERENCE_IMPLEMENTATIONS.md` (what each phase studies). One phase at a time; a phase ends only when
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

## 3. Phases (frozen 2026-09-30; one at a time; a phase ends only with its exit condition, tests and a commit)

| # | Phase | Exit condition | Studies | What exists already |
|---|---|---|---|---|
| 0 | Problem freeze | `PROBLEM.md`: Person, Commitment, Travel Edge; the system can answer YES / RISKY / NO for one day | Conveyal R5, SPOTAR literature, OR-Tools, MATSim (read) | done |
| 1 | Static Life Twin | calendar, tasks, deadlines, places, travel requirements, dependencies, free windows; a constraint check with static travel times; "your 11:30 class cannot be reached after your 11:00 meeting" | — | profile, calendar, tasks, free windows, feasibility grades, conflicts (partial: travel is from the planner, not a static edge; dependencies missing) |
| 2 | Real multimodal travel | A → B gives car, transit, walk, mixed with real routes; edges are real, no traffic ML | OpenTripPlanner / R5, Valhalla | car via the routing provider, rail via OSM (partial) |
| 3 | Whole-day optimiser | fixed events + flexible tasks + deadlines + edges → a feasible day, deterministic | OR-Tools CP-SAT / Timefold | — |
| 4 | TrafficTwin baseline | persistence, historical average, one Graph WaveNet; now / +15 / +30 / +60 with reproducible records | Graph WaveNet via BasicTS | GWNet trained; records incomplete |
| 5 | Uncertainty | every edge has an expected time and a calibrated interval, in any city | MAPIE, Namma Commute | — (the empirical probability exists only where corridor history exists) |
| 6 | Reliable reachability | P(arrive before deadline) per departure and mode; latest reliable departure | SPOTAR | partial (empirical, Dhaka only) |
| 7 | Reachability risk | every Today item shows LOW / MEDIUM / HIGH from the model and the constraints | — | partial (grades from the empirical probability) |
| 8 | Automatic day repair | a change recomputes only downstream nodes; "I repaired 3 parts of your day" | — | monitor + one-shot recovery (partial) |
| 9 | Disruption engine | accident, closure, cancellation, weather, flooding as one abstraction that changes edges | — | — |
| 10 | Accessibility | mobility profile; accessible vs fastest; the accessibility gap measured | — | — |
| 11 | Opportunity explorer | "which internships can I reliably reach while keeping my schedule?" over jobs, hospitals, universities, services | R5 cumulative accessibility | — |
| 12 | What-if simulator | leave later, rain, metro stops, take this job, move here; one simulation underneath | — | departure what-if (partial) |
| 13 | TrafficTwin advanced models | DCRNN, STID, STAEformer one at a time; judged by reachability decisions, not MAE | official repos via BasicTS | STID trained |
| 14 | Access research metrics | Access Success Rate, Access Regret, Buffer Waste, Recovery Rate, Opportunity Reachability computed from runs | — | outcomes store (partial) |
| 15 | Sparse-data research | sensors at 100 / 75 / 50 / 25 / 10 %: forecast error → reachability error → access success | — | node subsampling exists |
| 16 | Cross-city | OpenCity, UniST: useful reachability decisions with little local history | OpenCity, UniST | OpenCity zero-shot exists |
| 17 | Digital twin | same people, destinations, congestion: reactive navigation vs AccessTwin decisions; late arrivals, waiting, queues, access success | SUMO | oracle-first protocol exists |
| 18 | Population-level simulation | 1 000 to 10 000 agents; does predictive access planning raise city-wide opportunity accessibility | MATSim | — |
| 19 | Emergency scenario | hospital reachability, future-aware route, signal priority, as an evaluation domain | — | — |
| 20 | V2X | vehicles as a sensing channel; how communication degradation affects access decisions | MOSAIC | channel and sweeps exist |
| 21 | LIFE OS agent | goal → planner → typed action → policy → approval → tool → audit over a mature AccessTwin | OpenMuse pattern | built (proposal, worker, approvals, audit) |
| 22 | Email, calendar, files | "I have an interview": find the mail, the event, the place, the CV; build the commitment | — | calendar ICS only |
| 23 | Consumer web app | Today · Plan · Agent · Explore · Activity · You; Today is the homepage, not a traffic map | — | Today · Agent · Goals · Activity · You built; Plan and Explore pending |
| 24 | Hackathon | one flagship scenario on Alexa+ with one injected disruption, three minutes | — | MCP server live |
| 25 | Growth | one daily loop: morning, before travel, during the day, evening; then the consented data flywheel and partners | — | — |

## 4. Rules that hold in every phase
- Nothing on a page is typed in; every number comes from a file the pipeline wrote or a computation for this request.
- A provider is a live external reference, never a training target; consented probe data is the only city history a model may learn from.
- A model drives a decision only after its validation gate; a probability is shown only when it comes from an evaluated method.
- Irreversible actions pause for approval; every decision is in the audit chain.
- One file, one responsibility; official implementations unchanged and used as dependencies or adapters when their licence allows; each phase's evidence in the lab.
- Amazon Bedrock stays the LIFE OS model; TrafficTwin predicts, AccessTwin decides, LIFE OS acts.
- Commit after each completed phase; never continue because the UI looks complete.

## 5. Phase log

Entries before 2026-09-30 refer to the earlier phase numbering; they are kept because the work is kept.

| Phase | Date | What was verified | Evidence |
|---|---|---|---|
| 0 | 2026-09-29 | the six documents written from the code as it is | commit `adca7e36` |
| 1 | 2026-09-29 | goals run on a background worker under a lease (`agent/worker.py`); the API answers at once and the page polls; a goal left running by a killed process is recovered at the next start or reaper pass with its in-flight call marked interrupted; cancel stops a running goal at its next step and a paused goal at once; approvals bound to the exact action with expiry, standing rules, rejection reason; signed audit checkpoints | `backend/tests/test_worker.py` (8), `test_approvals.py` (8), `test_agent.py`, `test_life_twin.py`; full suite 558 passed, 5 skipped; live: API killed with `kill -9` 1.5 s after a submit, restarted, the goal finished with audit kinds `intent, interrupted, decision, result, decision, result, summary` and an intact chain; a second goal cancelled after two steps with summary "stopped by you" |
| 2 | 2026-09-29 | five consumer pages on one sidebar: Today (stats row, timeline, at-risk with reasons, suggestions, goals in progress, updates), Agent (the conversation, recent goals, yours, standing decisions, activity), Goals (grouped by what they need; overview with counted progress, next action, risks, what the goal created), Activity (audit and replans merged, filters, chain status), You (memory by kind with forget, permissions policy and tools, standing decisions, calendar and connectors, privacy with export and confirmed erasure); Plan and City stay reachable from Today; the lab is untouched | `backend/tests/test_you.py` (3), web `today/hooks.test.ts`, `goals/GoalOverview.test.ts`; full suite 561 passed, 5 skipped; web 27 passed; every page rendered in the browser against the live server |
| 3.1 | 2026-09-29 | every gap between placed commitments is graded feasible (p ≥ 0.8 leaving as the first ends), risky (0.5 ≤ p < 0.8), impossible (p < 0.5) or unknown, from the commute planner's own on-time distribution scaled by the person's calibration; `buffer_min` says how long before the first ends one must leave; the Life Twin verdict follows the grades | `backend/tests/test_feasibility.py` (7); live with the real planner: Viva at Shahbagh → dentist at Uttara with a 20-minute gap graded impossible (journey about 24 min, 0 % on time, leave 12 min before the end); dentist → Farmgate two hours later feasible |
| 3.2 | 2026-09-29 | conflicts found from the twin's own facts: overlapping commitments, a task due during a commitment or during a journey, a risky or impossible gap; each with severity, the items, the time and one fix; the Today stats row shows upcoming trips, tasks remaining and conflicts (the four cards of screen 04, mail pending Phase 17) and the at-risk list carries each conflict with its fix | `backend/tests/test_conflicts.py` (5); web `today/hooks.test.ts`; full suite 573 passed, 5 skipped; rendered on Today against the live server |
| fix 1 | 2026-09-30 | the audit found the consumer path fixed to one person (`demo`), one city (`dhaka`), fixed places (Farmgate, Shahbagh) and a fixed +06:00 clock in nine backend modules and three pages. Now a person has a profile (`app/profile`): name, IANA timezone, city (typed or from the browser's location through OpenStreetMap's reverse geocoder), home, work, on-time target. The planner, day timeline, Life Twin, conflicts, what-if, monitor recovery, calendar import, the agent's tools and prompts all read the person's zone, city, home and target; the deployment defaults (`TRAFFICTWIN_DEFAULT_CITY`, `TRAFFICTWIN_DEFAULT_TZ`) apply only to a person with no profile and say so. The browser keeps one generated id per person until accounts arrive; Today opens with a welcome step and then a greeting in the person's local time | `backend/tests/test_profile.py` (6); live: a Los Angeles person located from a point, saved with `America/Los_Angeles`, her day and a what-if computed in her zone and city with no city argument; full suite 579 passed, 5 skipped; web 27 passed |
