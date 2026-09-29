# Architecture — LIFE OS × TrafficTwin

Audit date: 2026-09-29 (Phase 0). Every statement here was checked against the code on that date; line counts are
from `wc -l`. Companion documents: `WORKFLOW.md` (the core loop on one goal), `ROADMAP.md` (phases and gates),
`REFERENCE_IMPLEMENTATIONS.md` (what was studied and borrowed), `THIRD_PARTY_LICENSES.md`, `EXPERIMENT_PROTOCOL.md`.

## 1. Two products, one repository

| | LIFE OS | TrafficTwin |
|---|---|---|
| What it is | the consumer personal-operations system: goals, plans, permissions, tools, monitoring, memory, audit | the predictive physical-world engine LIFE OS calls: forecasting, routing, departure optimisation, digital twin, V2X |
| Who sees it | the person, in the app (`/today`, `/plan`, `/city`; target: Today, Agent, Goals, Activity, You) | examiners and reviewers, in the lab (`/lab/*`) |
| Where it lives | `backend/app/{agent,plan,calendar,transit,commute,mcp}`, `frontend/src/features/assistant` | `backend/app/{forecasting,routing,twin,networking,control,signals,protocols,data}`, `frontend/src/features/{forecast,mobility,twin,results,references,system}` |
| Runtime brain | Amazon Bedrock (Converse API; Claude Haiku 4.5 `us.` profile, Nova Lite fallback) — the primary LLM, not to be replaced | PyTorch models trained with the official BasicTS harness; Chronos and OpenCity zero-shot; SUMO with TraCI |

The trust boundary (borrowed as a principle from OpenMuse, see `REFERENCE_IMPLEMENTATIONS.md`): **the model proposes; the
host decides.** The model never executes anything; it emits a typed tool call, the permission engine decides, the
orchestrator executes, and the audit log records both before and after.

## 2. The core loop and where each stage lives

```
Goal → Context → Life Twin → Feasibility → TrafficTwin → Plan → Permission → Tools → Action → Monitor → Replan → Outcome → Memory/Audit
```

| Stage | Module | State on 2026-09-29 |
|---|---|---|
| Goal | `agent/models.py` (`Goal`, `Step`, `ToolCall`, `GoalStatus`), `agent/store.py` (SQLite, JSON document per goal) | done; statuses proposed · planning · running · waiting_approval · waiting_user · done · failed · cancelled |
| Context | `agent/intent.py` (structured intent by forced tool call, rules fallback), `agent/memory.py` (facts: preference / place / pattern / constraint; lexical + recency recall into the system prompt) | done |
| Life Twin | `plan/life_twin.py` (snapshot: commitments, deadlines, departures, free windows, routines, preferences, calibration) | partial — Phase 3 completes it |
| Feasibility | `plan/life_twin.feasibility` (travel between placed commitments vs the gap), `plan/whatif.py` (verdict for one departure) | partial — no risky / impossible grading, no conflicting-task detection |
| TrafficTwin | `commute/service.py` (departure with empirical on-time probability), `routing/trip/*`, `data/live_providers/*` (Amazon Location → Google → local SUMO router), `forecasting/*`, `transit/*` | done for the app path; the research gates are in `protocols/` |
| Plan | `agent/orchestrator.py` (ReAct loop over the tool registry; the intent's `plan` shown before start) | done |
| Permission | `agent/permissions.py` (typed risk classes → allow / ask / refuse; grounding of sensitive arguments), `agent/approvals.py` (exact-action hash, 30-minute expiry, standing rules), `Tool.needs_approval` predicates | done |
| Tools | `agent/tools.py` registry + domain `TOOL_SPECS` (calendar, memory, outcomes, what-if, notifications); `mcp/` exposes the same registry to Alexa+ and any MCP client | done |
| Action | `orchestrator._execute` (the handler runs; result or real error goes back to the model); `agent/worker.py` (background thread per goal under a lease, heartbeat, reaper, restart recovery, cancel) | done |
| Monitor | `plan/monitor.py` (thread, every 300 s: departure moved, probability dropped, route changed → notification; one recovery per reference) | done as polling; Phase 18 makes it event-driven |
| Replan | `plan/whatif.recovery`, `monitor._recover` | partial |
| Outcome | `plan/outcomes.py` (actual vs predicted; per-person calibration factor after 3 trips) | done |
| Memory / Audit | `agent/memory.py`; `agent/audit.py` (hash-chained JSONL per user, server-signed checkpoints, verifier) | done |

## 3. Backend layout (FastAPI, `PYTHONPATH=backend`, import name `app`)

| Domain | Files / lines | Responsibility |
|---|---|---|
| `agent/` | 13 / 1 160 | goals, orchestrator, permissions, approvals, audit, memory, intent, tools registry, LLM adapter, router |
| `plan/` | 8 / 534 | day timeline, Life Twin, feasibility, what-if, monitor, notifications, outcomes |
| `calendar/` | 5 / 245 | ICS reader, events store, calendar tools, import routes |
| `commute/` | 4 / 254 | "leave when?" with recorded corridor bands and on-time probability |
| `transit/` | 5 / 274 | OpenStreetMap stops and lines, published metro timetable, walk·wait·ride·walk |
| `mcp/` | 3 / 133 | MCP server (Streamable HTTP) over the tool registry |
| `routing/` | 27 / 4 193 | edge costs, optimiser, forecast-priced routing, trip analysis, local SUMO router |
| `forecasting/` | 67 / 10 256 | BasicTS training, evaluation, live inference, OpenCity, federated, operations |
| `twin/` | 27 / 3 844 | SUMO runtime, scenario builder, sensor map, live comparison |
| `networking/` | 16 / 1 525 | simulated V2X channel, state correction, MOSAIC bridge |
| `control/`, `signals/` | 6 / 782, 7 / 760 | closed-loop controller, signal-control benchmark |
| `protocols/` | 42 / 6 641 | gates, statistics, stress calibration, evidence, references, research status |
| `data/` | 28 / 4 579 | datasets, uploads, city model, recorded corridor history, live providers, city map |
| `perception/`, `nlp/`, `interfaces/`, `common/`, `tools/`, `platform/` | | detection, text, shared contracts, utilities, system routes |

Registered routes: 125 (fixture `backend/tests/fixtures/api_routes_pre_structure.json`, regenerated on every route
change). Tests: 22 files under `backend/tests` plus `tests/platform`; 550 passed, 5 skipped on 2026-09-29.

## 4. Frontend layout (Vite, React 19, TypeScript, TanStack Query, MapLibre)

- `src/app/` — `routes.tsx` (consumer `APP_NAV`, lab `LAB_NAV`, redirects), `AppShell.tsx` (sidebar), `LabShell.tsx`, `Hero`, `photos`.
- `src/features/<domain>/` — one folder per page; files ≤ 200 lines by test (`test_structure_migration.py`).
- Consumer: **Today · Agent · Goals · Activity · You** (`features/{today,assistant,goals,activity,you}`); `/plan` and `/city` are reached from Today and the Agent, not from the sidebar.
- Lab today: `/lab/{evidence,control-room,models,references,system}`. Lab target (Phase 21): `/lab/{datasets,models,forecasting,routing,digital-twin,v2x,experiments,references}`.
- The built bundle (`frontend/dist`) is served by the API with an SPA fallback; the mobile app (`mobile/`, Expo) uses the same API.

## 5. Storage and external services

| Store | Content |
|---|---|
| `results/live/agent/agent.sqlite` | goals (JSON documents), tasks, reminders, commutes, approval rules |
| `results/live/agent/audit/<user>.jsonl` + `.checkpoints.jsonl` | the audit chain and its signed checkpoints (`AUDIT_SIGNING_KEY` or a server key file) |
| calendar, memory, notifications, outcomes SQLite files under `results/live/` | per-domain stores, one file each |
| `results/**` run files | every experiment's evidence; the lab reads only these |
| Amazon Location (Routes), Google Routes (fallback), OpenStreetMap Overpass and Nominatim, Amazon Bedrock, Amazon SNS | external services; keys only in `.env` (names, never values, in docs) |

Rules that hold everywhere: nothing on a page is typed in; a provider is a live reference, never a training target
(no Google-derived history is ever trained on); a model drives advice only after its validation gate; recorded and
simulated data are labelled as such.

## 6. What exists against Phases 0–3

| Phase | Exists | Incomplete |
|---|---|---|
| 0 audit | this document set | — |
| 1 agent core | persistent Goal/Step/ToolCall; statuses; pause on approval and on question; resume by `run()`; background worker with lease, heartbeat, reaper and restart recovery; cancel; approvals bound to the exact action with expiry, standing rules, rejection reason; audit chain with signed checkpoints; consumer wording of every audit line (`words.ts`); tests (`test_worker.py`, `test_agent.py`, `test_approvals.py`, `test_life_twin.py`) | status name `done` where the specification says `COMPLETED` (kept: it is the wire contract of the web and mobile clients; `done` ≡ COMPLETED) |
| 2 consumer shell | the five pages on one sidebar; per-user export and erasure (`agent/you.py`), memory and related-item routes | Mail and files connectors (Phase 17); Plan and City folded further into Today when routing is multimodal (Phase 10) |
| 3 Life Twin | snapshot; free windows; feasibility between placed commitments; personal calibration; what-if verdict | feasible / risky / impossible grading with travel buffers; conflicting tasks and events; goal dependencies; routines learned from outcomes; unit tests per rule |

## 7. Technical debt (recorded, not hidden)

1. Eleven backend modules exceed the 400-line rule of `PROJECT_STRUCTURE.md` (largest: `routing/graph_router.py`, `protocols/chains/integrated_chain.py`, `protocols/learned_gate.py`, `forecasting/training/basicts_train.py`); they are split only when a phase touches them (rule 15).
2. The worker is a thread inside the API process; Phase 22 moves it to a separate worker service on the same lease table.
3. The monitor polls every 300 s instead of reacting to events (Phase 18).
4. Corridor traffic in Dhaka comes from recorded bands because no provider covers it; probe data (Phase 8) is the way out.
5. The on-time probability is empirical from recorded distributions, not a conformal interval (Phase 7).
6. Gmail and Google Calendar connectors need OAuth on a non-AWS provider; the person decides (Phase 17).
7. The monitor's 5-minute threshold lets a departure flip between two routes on successive checks (two "replanned" lines 5 min apart in Activity); hysteresis belongs to Phase 18.
