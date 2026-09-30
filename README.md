# LIFE OS × TrafficTwin

**Can uncertainty-aware predictive mobility improve reliable access to time-critical commitments — and can an agent plan a person's day without ever inventing a number?**

Say what your day holds. LIFE OS compiles it into commitments, builds your Life Twin, asks the roads and the calendar whether the day can physically work, plans the departures, asks before anything it cannot undo, watches for change, and records what actually happened. TrafficTwin is the engine underneath: it predicts mobility and its uncertainty. AccessTwin decides whether a commitment is reachable. Nothing on a page is typed in.

```
UNDERSTAND → MODEL → PREDICT → PROVE FEASIBILITY → PLAN → ACT → MONITOR → REPAIR → VERIFY → LEARN
```

| | |
|---|---|
| The frozen problem, entities and hypothesis | [`docs/PROBLEM.md`](docs/PROBLEM.md) |
| The 31-phase plan and its packages | [`docs/PHASES.md`](docs/PHASES.md) · [`docs/ROADMAP.md`](docs/ROADMAP.md) (status and phase log) |
| How each step is built the production way (pattern copied, package, AWS home, evidence, test) | [`docs/PRODUCTION_WORKFLOW.md`](docs/PRODUCTION_WORKFLOW.md) |
| What exists, mapped to code and tests | [`docs/FEATURE_CODE_MAP.md`](docs/FEATURE_CODE_MAP.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| Data model (13 relational tables) | [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) |
| What was studied and borrowed, with licences | [`docs/REFERENCE_IMPLEMENTATIONS.md`](docs/REFERENCE_IMPLEMENTATIONS.md) · [`docs/RESEARCH_PIXY_BLACKBOX.md`](docs/RESEARCH_PIXY_BLACKBOX.md) · [`docs/THIRD_PARTY_LICENSES.md`](docs/THIRD_PARTY_LICENSES.md) |
| Research contract and metrics | [`docs/EXPERIMENT_PROTOCOL.md`](docs/EXPERIMENT_PROTOCOL.md) |
| What was tried and dropped | [`docs/GRAVEYARD.md`](docs/GRAVEYARD.md) |
| Next phase, designed and awaiting approval | [`docs/PHASE1_DESIGN.md`](docs/PHASE1_DESIGN.md) |

## Contents

[What it does](#what-it-does) · [Runs without a key](#runs-without-a-key) · [Setup](#setup) · [System architecture](#system-architecture) · [The core loop and its guarantees](#the-core-loop-and-its-guarantees) · [API endpoints](#api-endpoints) · [Database structure](#database-structure) · [Configuration](#configuration) · [Tests](#tests) · [Findings so far](#findings-so-far) · [How this maps to the references](#how-this-maps-to-the-references) · [Known gaps](#known-gaps) · [Planned work](#planned-work) · [Citation](#citation)

## What it does

| # | Feature | Where it lives | Status |
|---|---|---|---|
| 1 | Commitment compiler — text or an e-mail line becomes a validated Commitment (type, when, where, requirements) by rules or by the model | `backend/app/lifeos/compiler/` | built, evaluated |
| 2 | The seven contracts and their relational store — Person, Commitment, Constraint, TravelEdge, Outcome, Action, Event | `backend/app/lifeos/{entities,db,repo}.py`, `backend/alembic/` | built |
| 3 | Person profile — zone, city, home, work, on-time target; the city found from the browser's location | `backend/app/profile/` | built |
| 4 | Day timeline, Life Twin snapshot, feasibility grades, conflicts with fixes | `backend/app/plan/{day,life_twin,feasibility,conflicts}.py` | built (pre-plan; replaced by the OR-Tools check in the next phase) |
| 5 | Departure planning with an empirical on-time probability where recorded corridor history exists | `backend/app/commute/` | built; real only for Dhaka corridors |
| 6 | Live routes for any city; transit from OpenStreetMap and a published timetable | `backend/app/data/live_providers/`, `backend/app/transit/` | built |
| 7 | The agent — proposal before start, ReAct loop on Bedrock, typed permissions, exact-action approvals, standing rules, hash-chained audit with signed checkpoints, durable worker with lease and restart recovery, cancel | `backend/app/agent/` | built |
| 8 | Memory, calendar import (ICS), tasks, reminders, notifications, outcomes and personal calibration, export and erasure | `backend/app/agent/{memory,you}.py`, `backend/app/calendar/`, `backend/app/plan/{notifications,outcomes}.py` | built |
| 9 | MCP server exposing the same tools to Alexa+ and any MCP client | `backend/app/mcp/` | built |
| 10 | Consumer web app — Today, Plan, Goals, Messages, Map, City, Settings | `frontend/src/features/` | built |
| 11 | Research lab — evidence, control room, models, references, system | `frontend/src/features/{results,twin,forecast,references,system}` | built |
| 12 | TrafficTwin research engine — BasicTS training, held-out validation, SUMO closed loop with a simulated V2X channel, oracle-first protocol | `backend/app/{forecasting,routing,twin,networking,control,protocols}/` | built; see findings |
| 13 | OR-Tools feasibility with an independent verifier, seeded fixture, receipt | `backend/app/lifeos/{twin,travel,feasibility}/` | designed, not started ([`docs/PHASE1_DESIGN.md`](docs/PHASE1_DESIGN.md)) |

## Runs without a key

The compiler's rules path, the feasibility grades, the conflicts, the day timeline, the transit planner on a given line, the contracts, the store and the whole test suite run with no key, no network and no model. The language model (Amazon Bedrock) is an enhancement wherever it appears: the compiler falls back to rules and says so in `path`; the agent reports the reason when no model is reachable. Live routes need Amazon Location credentials; without them the local SUMO router answers for the frozen Dhaka network and labels itself.

## Setup

```bash
pip install -r backend/requirements.txt
python -m spacy download en_core_web_sm
PYTHONPATH=backend python -m uvicorn app.main:app --app-dir backend --port 8000     # API + built web app + /mcp
```

```bash
cd frontend && npm install && npm run build      # the API serves frontend/dist with an SPA fallback
cd frontend && npm run dev                       # or a dev server on :5173 proxying /api
```

Keys live only in `.env` (names in [Configuration](#configuration); values are never printed or committed). On start the core store is migrated to head (`alembic upgrade head` through `app.lifeos.db.init`).

## System architecture

```
                     POST /api/agent/goals (start=false)             POST /api/lifeos/compile
                              │                                               │
   ┌──────────────────────────▼───────────────────────┐   ┌───────────────────▼──────────────────────────┐
   │ agent/intent.py   the goal read into a record     │   │ lifeos/compiler/rules.py    day+clock patterns,│
   │ agent/router.py   proposal shown, nothing runs    │   │   dateparser, spaCy places, rapidfuzz snapping │
   └──────────────────────────┬───────────────────────┘   │ lifeos/compiler/model.py    Bedrock fills the  │
              /start          │                            │   contract; Pydantic validates; rules stand in │
   ┌──────────────────────────▼───────────────────────┐   └───────────────────┬──────────────────────────┘
   │ agent/worker.py   lease, heartbeat, reaper        │                       ▼
   │ agent/orchestrator.py  thought → one tool → obs.  │   ┌──────────────────────────────────────────────┐
   │ agent/permissions.py   allow / ask / refuse       │   │ lifeos/entities.py  the seven contracts       │
   │ agent/approvals.py     exact-action, expiry, rules│   │ lifeos/db.py + alembic/  13 relational tables │
   │ agent/audit.py         hash chain + signed ckpts  │   │ lifeos/repo.py       reads and writes         │
   └──────────────────────────┬───────────────────────┘   └──────────────────────────────────────────────┘
                              ▼ tools (agent/tools.py, domain TOOL_SPECS)
   ┌─────────────────┬─────────────────┬───────────────────┬──────────────────┬───────────────────────────┐
   │ commute/service │ plan/{day,      │ calendar/         │ agent/memory     │ plan/{whatif,outcomes,    │
   │ recorded bands, │ life_twin,      │ ics reader, store,│ facts by kind,   │ notifications, monitor}   │
   │ on-time prob.   │ feasibility,    │ overlap predicate │ recall to prompt │ what-if, calibration,     │
   │                 │ conflicts}      │                   │                  │ watch every 300 s         │
   └────────┬────────┴─────────────────┴───────────────────┴──────────────────┴───────────────────────────┘
            ▼
   ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐
   │ TrafficTwin   data/live_providers (Amazon Location → Google → local SUMO router)  · transit/ (OSM)  │
   │               forecasting/ (BasicTS, Chronos, OpenCity) · routing/ · twin/ (SUMO) · networking/ (V2X)│
   └────────────────────────────────────────────────────────────────────────────────────────────────────┘
   authoritative: results/live/lifeos.sqlite (13 tables) · pre-plan stores: agent, calendar, memory, notifications, outcomes (SQLite each)
   derived and rebuildable: goal proposals, day timelines, feasibility reports, notifications
```

Every step of a goal is written to the audit log before and after it runs; a goal left running by a killed process is recovered at the next start with its in-flight call marked interrupted; a paused approval is bound to the hash of its exact arguments and expires after 30 minutes.

## The core loop and its guarantees

```
Goal → Context → Life Twin → Feasibility → TrafficTwin → Plan → Permission → Tools → Action → Monitor → Replan → Outcome → Memory/Audit
```

Four properties the code enforces rather than the prompt:

1. **No invented facts.** Tool results are the only source of numbers; a travel edge carries the provider that produced it and whether it was live, typical, recorded or static; the model's output validates through the contracts or is discarded.
2. **Nothing consequential without permission.** Irreversible and external actions pause; the approval names the exact action; a changed action is not approved; money is refused.
3. **Every decision is verifiable.** The audit log is hash-chained and periodically signed by the server; `GET /api/agent/audit` returns the chain check with each read.
4. **Every answer states its provenance.** Recorded is labelled recorded, simulated is labelled simulated, a deployment default says "deployment default".

## API endpoints

Interactive docs at `/api/docs`. 147 routes; the LIFE OS ones:

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/lifeos/compile` | text → validated Commitment (rules or model), optional save |
| PUT | `/api/lifeos/{persons,commitments,constraints,travel-edges,outcomes,actions,events}` | create or replace one entity |
| GET · DELETE | `/api/lifeos/{kind}/{id}` · `/api/lifeos/{kind}?person_id=` | read, list (commitments by deadline window, events since), delete |
| GET | `/api/lifeos/schema` | JSON Schema of every contract |
| GET · PUT · POST | `/api/profile` · `/api/profile/locate` | who and where; the city at a point |
| POST | `/api/agent/goals` · `/{id}/start` · `/{id}/approve` · `/{id}/answer` · `/{id}/cancel` | propose, start, approve an exact action, answer a question, stop |
| GET | `/api/agent/goals` · `/{id}` · `/{id}/related` · `/api/agent/worker` | goals, one goal, what it created, the runner |
| GET · POST · DELETE | `/api/agent/approvals/rules` | standing decisions per tool |
| GET · DELETE | `/api/agent/memory` | what the assistant remembers; forget |
| GET | `/api/agent/audit` · `/api/agent/tools` · `/api/agent/tasks` | the verified log, the tool registry and policy, tasks and reminders |
| GET · POST | `/api/plan/day` · `/api/plan/twin` · `/api/plan/whatif` · `/api/plan/check` | timeline with departures, the Life Twin snapshot with grades and conflicts, a what-if, a monitor tick |
| GET · POST | `/api/notifications` · `/read` · `/api/outcomes` | the watch's messages; actual arrivals |
| POST · GET | `/api/calendar/import` · `/api/calendar/events` | ICS file or URL; events |
| POST · GET | `/api/commute/plan` · `/api/commute/profile` · `/api/transit/plan` · `/api/transit/lines` | leave-when, corridor profile, rail option |
| GET · DELETE | `/api/you/export` · `/api/you?confirm=<id>` | everything held about a person; erase it |
| — | `/mcp` | the same tools over the Model Context Protocol |

## Database structure

`results/live/lifeos.sqlite`, thirteen relational tables created by Alembic, foreign keys enforced, timestamps stored in UTC and read back aware. PostgreSQL by URL (`LIFEOS_DATABASE_URL`). Diagram and rules in [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md).

```
persons ──< places ──< commitments ──< commitment_requirements
   │            │            └──────< commitment_dependencies
   │            │            └──────< outcomes
   │            └──< travel_edges (origin, destination)
   ├──< constraints ──< constraint_params, constraint_targets
   ├──< actions        (arguments, result as JSON by nature)
   └──< events         (payload as JSON by nature)
```

The stores written before the plan (goals, tasks, reminders, commutes, approval rules, leases; calendar; memory; notifications; outcomes; profiles) are separate SQLite files and move onto these tables in Phase 2 of the plan.

## Configuration

Everything has a working default; keys are read from the environment first, then `.env`.

| Variable | Default | What it does |
|---|---|---|
| `LIFEOS_DATABASE_URL` | `sqlite:///results/live/lifeos.sqlite` | the core store; any SQLAlchemy URL |
| `TRAFFICTWIN_DEFAULT_CITY` · `TRAFFICTWIN_DEFAULT_TZ` | `Dhaka` · `Asia/Dhaka` | used only for a person with no profile, and labelled as such |
| `TRAFFICTWIN_AGENT_MODEL` | first available of Claude Haiku 4.5, Nova Lite | the Bedrock model |
| `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` · `AWS_SESSION_TOKEN` · `AWS_REGION` · `BEDROCK_REGION` · `AWS_LOCATION_REGION` | (empty) | Bedrock and Amazon Location; without them the model path and live routes are unavailable and say so |
| `SNS_TOPIC_ARN` · `SNS_REGION` | (empty) | notifications by SNS; otherwise stored only |
| `AUDIT_SIGNING_KEY` | a server-generated key file | signs audit checkpoints |
| `GOOGLE_MAPS_API_KEY` · `GOOGLE_ROUTES_DAILY_CAP` | (empty) · cap | the fallback route provider; never a training target |
| `DHAKAFLOW_NO_OBSERVATORY` | unset | set in tests: no live sampling, no monitor, no worker reaper |
| `SUMO_HOME` · `MOSAIC_HOME` · `DHAKAFLOW_WORKSPACE` | — | the simulator, the V2X reference runs, the external workspace of pinned upstream code |

## Tests

```bash
PYTHONPATH=backend python -m pytest -q --ignore=backend/tests/test_frontend_e2e.py     # 592 passed, 5 skipped, about 2 min, no key, no network
cd frontend && npx vitest run                                                          # 27 passed
```

The suite fakes only the language model (`Scripted` turns) and, in a few tests, the routing provider. Stores, migrations, the permission engine, the audit chain, the worker's lease and recovery, the compiler's rules, feasibility, conflicts and the HTTP surface all run for real against temporary databases.

| File | Covers | Phase |
|---|---|---|
| `test_lifeos_core.py` | the seven contracts, the relational round trip, foreign keys, migration rebuild, HTTP | P0 |
| `test_compiler.py` | rules path fields, deadline vs fixed, relative days, refusal without a time, validated model path and fallback, the person's zone, HTTP | P1 |
| `test_profile.py` · `test_you.py` | zone, city, home and target read everywhere; export and erasure of one person only | pre-plan |
| `test_agent.py` · `test_approvals.py` · `test_worker.py` | the loop on a scripted model, every approval rejection path, standing rules, signed checkpoints, lease, cancel, restart recovery | pre-plan (P13–P14 pattern) |
| `test_feasibility.py` · `test_conflicts.py` · `test_life_twin.py` · `test_life.py` | grades from the distribution, conflicts with fixes, the snapshot, calendar import, memory, timeline, monitor | pre-plan |
| `test_commute.py` · `test_transit.py` · `test_amazon_location.py` | the planner's honest labels, rail legs on a given line, provider record shape and coverage flag | pre-plan |
| `test_mcp.py` · `test_api.py` · `test_structure_migration.py` · `test_anti_hardcode.py` | the protocol, every page's endpoint shape, the 147-route fixture and file-size rules, inputs must change outputs | platform |
| `test_canonical_prediction.py` · `test_scientific_execution.py` · `test_live_twin.py` · `test_twin_test.py` · `test_model_registry.py` · `test_research_status.py` · `test_route_opt.py` · `test_user_datasets.py` · `test_configuration_boundaries.py` | the research engine: fresh inference per request, frozen protocols, a real SUMO run, the model gate, computed research gates | TrafficTwin |

## Findings so far

Numbers come from committed run files; each carries its caveat.

| Finding | Number | Where | Caveat |
|---|---|---|---|
| The commitment compiler's rules path on the evaluation set | type, when, location, requirements, flexibility, duration all 1.000; 4/4 sentences without a time refused | `results/lifeos/compiler.json` on `data/lifeos/commitments.jsonl` | 760 of 789 rows are templated and prove the patterns; the 25 hand-written rows are the honest part; the set must grow with real sentences |
| The model path, live | English interview sentence compiled with requirements; a Bangla hospital sentence to 09:00 Dhaka the next day; "Dinner with Rafi tomorrow" reported as missing its time | roadmap phase log P1 | three sentences, not an evaluation |
| Feasibility grading with the real planner | Viva at Shahbagh → dentist at Uttara, 20-minute gap: impossible (journey about 24 min, leave 12 min before the end); dentist → Farmgate two hours later: feasible | roadmap log 3.1 | the probability behind the grade exists only where recorded Dhaka corridor history exists |
| The closed-loop digital twin | perfect information beats reactive routing by −1.83 % vehicle-hours on the frozen corridor; the learned forecast does not yet beat no advice | `docs/WORKFLOW.md`, `results/current/closed_loop/` | one corridor; the ceiling is about 2 %, so gains must come from coverage, not a better model. A negative result, kept. |
| Restart recovery | a goal killed with `kill -9` 1.5 s after submit finished after restart with audit kinds intent, interrupted, decision, result, decision, result, summary and an intact chain | roadmap log P1 (agent) | one live run |

## How this maps to the references

Full traceability in [`docs/REFERENCE_IMPLEMENTATIONS.md`](docs/REFERENCE_IMPLEMENTATIONS.md). In summary:

| Reference | Taken | Deliberate substitution |
|---|---|---|
| tahodev/openmuse (MIT) | exact-action approval with expiry; signed audit checkpoints | re-implemented on our permission engine; no code |
| openai/openai-agents-python (MIT) | `needs_approval` predicates, always-approve/reject, rejection message; structured output through a forced tool | Bedrock instead of OpenAI; the goal document is the run state |
| CopilotKit/openmuse (MIT) | lease-owned task worker, plan visible before it runs | Python thread and SQLite lease rows |
| alejandro-publius/blackbox-datahub (Apache-2.0) | facts vs hypotheses vs actions, evidence gate, verification by full re-check, healthy control, bad-repair rejection, keyless judge check | applied to commitments and a solver instead of pipelines and a warehouse (next phase) |
| bitanath/pixy (Apache-2.0) | benchmark-first with a correctness column, profiling before optimising, graveyard, local privacy processing | patterns only |
| Namma Commute, Conveyal R5, the reliable-path literature (SPOTAR) | quantile plus conformal departure design; percentile accessibility; P(arrive before deadline) | later phases |
| Graph WaveNet, DCRNN, STID, STAEformer via BasicTS (Apache-2.0) | trained one at a time with the official harness | STAEformer and UniST have no licence file: read and benchmarked, never copied |

## Known gaps

- The on-time probability is empirical and exists only where recorded corridor history exists; elsewhere the risk card says "no estimate for this city yet". Calibrated intervals are Phases 9–10 of the plan.
- The feasibility check reads the commute planner, not travel edges from the store; the OR-Tools check with an independent verifier is designed and not started.
- No sign-in. One generated identity per browser; accounts come with the systems block.
- The monitor polls every five minutes and can flip a departure between two routes on successive checks; hysteresis belongs to the event-driven monitor.
- The compiler's rules path is English; Bangla goes to the model path.
- Mail and files are not connected; the calendar is ICS only.
- Eleven research modules exceed the 400-line rule and are split only when a phase touches them.
- Dhaka has no official GTFS feed, so transit there uses OpenStreetMap stops and the published metro timetable.

## Planned work

The plan in [`docs/PHASES.md`](docs/PHASES.md), six blocks, one phase at a time, each with its exit condition, tests, artifacts and commit:

- [x] Block A · P0 contracts and store · P1 compiler
- [ ] Block A · P1' OR-Tools feasibility with an independent verifier, seeded fixture, receipt, judge check ([`docs/PHASE1_DESIGN.md`](docs/PHASE1_DESIGN.md), awaiting approval)
- [ ] Block A · Life Twin on the store · real routing (Valhalla, OpenTripPlanner)
- [ ] Block B · weather · baselines · Graph WaveNet · uncertainty (MAPIE) · AccessTwin
- [ ] Block C · personal ML · risk engine · agent over mature tools · connectors · repair engine
- [ ] Block D · event bus · jobs · serving · observability
- [ ] Block E · SUMO · MATSim · ns-3/MOSAIC · edge · Flower · R5 · what-if
- [ ] Block F · six consumer pages · research lab · Alexa+

## Citation

```bibtex
@misc{lifeos-traffictwin-2026,
  title  = {LIFE OS x TrafficTwin: uncertainty-aware multimodal reachability and closed-loop replanning for time-critical commitments},
  author = {Jannatul Ferdouse},
  year   = {2026},
  note   = {Islamic University of Technology; code and evidence at this repository}
}
```

Licence: MIT (see `LICENSE`). Photographs by Unsplash photographers, credited in `frontend/public/photos/ATTRIBUTION.md`.
