# Reference implementations — what was studied, what was borrowed, what is ours

Rule: a repository is inspected only in the phase it is assigned to; before integration a mini-report in the form at
the end of this file is written; code is never copied wholesale; concepts are re-implemented inside our architecture
unless a permissive licence and a clean interface make a dependency the better choice. Pins: `docs/life_os_pins.json`
(agent) and `upstream/UPSTREAM_PINS.yaml` (traffic, routing, control, V2X).

## The table

| Reference repo | Purpose | Files studied | Concept borrowed | Code reused? | License | Changes made | Citation / reference |
|---|---|---|---|---|---|---|---|
| tahodev/openmuse @ `e39abd6` | local-first personal-agent runtime with exact-action approvals and verifiable audit | `src/openmuse/{approvals,approval_service,policy,audit,audit_anchor,tasks}.py`, `docs/{approval-service,audit-anchoring}.md`, `examples/{e2e_demo,local_planner,verify_audit}.py`, README | approval bound to one exact action (hash of tool + arguments), one-time, expiring; pending approvals marked interrupted on restart; durable task checkpoints; hash-chained audit with signed checkpoints and an independent verifier | **no** — re-implemented in `backend/app/agent/approvals.py`, `audit.py` (`_checkpoint`, `verify`) | MIT | our hash is over (tool, arguments) and stored on the call; expiry 30 min; standing rules added; checkpoint after approval/summary/error | README and docs of the repository; `docs/life_os_pins.json` |
| openai/openai-agents-python @ `7b27134` | agent SDK; human-in-the-loop by interruptions and resumable run state | `docs/human_in_the_loop.md`, `src/agents/run_state.py` (`RunState.approve/reject/to_json`, `get_interruptions`), `src/agents/tool.py` (`needs_approval`), `src/agents/items.py` (`ToolApprovalItem`), `src/agents/run_internal/approvals.py`, `examples/agent_patterns/human_in_the_loop.py` | `needs_approval` as a flag or predicate per tool; `always_approve` / `always_reject`; `rejection_message` returned to the model as the tool output; serialised run state resumed later | **no** — `Tool.needs_approval` (`agent/tools.py`), `approvals.set_rule`, `orchestrator.approve(message=, always=)`; our durable goal document is the run state | MIT | predicate signature is `(user_id, arguments) -> reason or None`; rules persist per user and tool in SQLite | repository docs; `docs/life_os_pins.json` |
| CopilotKit/openmuse @ `4f3f7c7` | self-hosted personal agent: durable task worker, stored action review, receipts | `apps/server/src/engine/worker.ts` (lease claim, heartbeat, expiry of awaiting-review actions, interrupted vs failed), `packages/domain/src/{jev,agent}.ts`, README | plan visible before it runs; every consequential action reviewed; lease-based worker so one runner owns a task; no hidden retry after an uncertain external write | **no** — the proposal flow (`/api/agent/goals` start=false, `/start`) and Phase 1's worker lease | MIT | TypeScript design read, Python re-implementation | repository README; `docs/life_os_pins.json` |
| liyaguang/DCRNN, nnzhan/Graph-WaveNet, GestaltCogTeam/STID, XDZhelheim/STAEformer | Phase 4 | not yet inspected in this plan (earlier labs used them through BasicTS) | — | via BasicTS harness (Apache-2.0) | MIT · MIT-style · Apache-2.0 · **no licence file** | — | pinned in `UPSTREAM_PINS.yaml` |
| HKUDS/OpenCity, tsinghua-fib-lab/UniST, RWLinno/RAST | Phase 5 | not yet inspected | — | — | MIT · **no licence file** · MIT | — | pinned |
| liuxu77/LargeST | Phase 6 | not yet inspected | — | — | MIT | — | pinned |
| scikit-learn-contrib/MAPIE | Phase 7 | not yet inspected | — | — | BSD-3-Clause | — | pinned |
| MapMatching-research/Map-Matching, valhalla (Meili) | Phase 8 | not yet inspected | — | — | **no licence file** · MIT | — | pinned |
| opentripplanner/OpenTripPlanner, valhalla/valhalla, nilsnolde/docker-valhalla | Phase 10 | not yet inspected | — | infrastructure dependency, not code | LGPL-3.0 · MIT · MIT | — | pinned |
| eclipse-sumo/sumo | Phase 12 (already used unmodified in Lab 01 and the twin) | `tools/`, TraCI docs | official simulator as an experiment engine | dependency (`eclipse-sumo` pip) | EPL-2.0 | none | `MASTER_RESOURCE_INDEX.md` Lab 01 |
| sumo-rl, LibSignal, RL_signals_CityFlow, smart-traffic-rl | Phase 13 | not yet inspected in this plan | — | — | MIT · **no licence file** · **no licence file** · **no licence file** | — | pinned (originals, not the forks) |
| eclipse-mosaic/mosaic, sraddon/SUMO-V2X-… | Phase 15 (MOSAIC already bridged in `networking/mosaic`) | — | — | MOSAIC as a dependency | EPL-2.0 · MIT | — | pinned |

Repositories without a licence file grant no rights to copy: they are read for their method and used only for
benchmark comparison or through a licensed re-implementation (STAEformer is available inside BasicTS under Apache-2.0).

## Mini-reports (Phase 1)

### tahodev/openmuse

```text
Repository: https://github.com/tahodev/openmuse
Commit: e39abd62fc610be4987ee8eb3a554160ddba3bd3 (2026-09-28)
License: MIT (LICENSE)

What problem does it solve?
  A personal-agent host in which an untrusted planner proposes typed actions and a trusted host decides,
  approves exact actions once, executes with bounds, and writes a verifiable audit chain.

Which exact files/classes/functions matter?
  approvals.ApprovalAuthority.issue/verify (HMAC token over {id, tool, arguments, exp}; one-time; expired at now >= exp)
  approval_service.ApprovalService (SQLite requests; pending → interrupted on restart; decide() atomic, session-authenticated)
  policy.Policy.check (READ allow; WRITE needs a valid one-time approval)
  audit.AuditLog.append / verify_chain (flock, fsync, previous_hash chain, redaction of secret-like keys)
  audit_anchor.create_checkpoint / verify_checkpoint (HMAC over records.head_hash.created_at)
  tasks.TaskStore (checkpoint per step with a step budget; task_events sequence)

Which official example did we reproduce?
  examples/e2e_demo.py (pip `openmuse-agent==0.3.0a0` in a scratch venv, answered `y`) and examples/local_planner.py.

What result did we obtain?
  e2e: read_file completed → write_file blocked (approval_required) → approved exact action → write_file completed;
  verify_chain(.openmuse-demo/audit.jsonl) = (True, 3, None). The HEAD verify_audit.py raised KeyError 'arguments_sha256'
  against the 0.3.0a0 release: the example is newer than the published package. local_planner: 1 record, chain valid.

What concept will we borrow?
  Exact-action approval with expiry; interrupted-on-restart semantics for pending work; signed audit checkpoints.

Will we:
[ ] use it as a dependency
[ ] adapt a small component
[x] independently reimplement the idea
[ ] use only for benchmark comparison

What will remain uniquely ours?
  The typed risk classes with argument grounding, standing rules, tool predicates, the Bedrock planner, the goal
  document as the run state, and the whole mobility side.

How will it be cited?
  docs/references.json group "agent" (key openmuse2026); docs/life_os_pins.json; module docstrings name the file.
```

### openai/openai-agents-python

```text
Repository: https://github.com/openai/openai-agents-python
Commit: 7b27134b2da927c73ab9397100ad451eeead0f88
License: MIT (LICENSE)

What problem does it solve?
  A general agent SDK whose run loop can be interrupted for human approval, serialised, and resumed.

Which exact files/classes/functions matter?
  docs/human_in_the_loop.md; tool.py `needs_approval: bool | callable(ctx, params, call_id)`;
  items.ToolApprovalItem; run_state.RunState.get_interruptions/approve(always_approve)/reject(rejection_message)/to_json/from_json;
  run_internal/approvals.append_approval_error_output (the rejection becomes a tool output the model reads).

Which official example did we reproduce?
  None executed: every example needs an OpenAI API key, and the project's LLM is Amazon Bedrock. The example
  examples/agent_patterns/human_in_the_loop.py was read (dynamic approval predicate on "Oakland").

What result did we obtain?
  Read-only study; the semantics were confirmed in our own tests (backend/tests/test_approvals.py).

What concept will we borrow?
  Per-tool approval predicate; standing approve/reject decisions; rejection message to the model; resumable state.

Will we:
[ ] use it as a dependency
[ ] adapt a small component
[x] independently reimplement the idea
[ ] use only for benchmark comparison

What will remain uniquely ours?
  Bedrock remains the runtime; the durable goal document is the state; the permission engine's typed classes.

How will it be cited?
  docs/references.json (key openai2026agents); docs/life_os_pins.json.
```

### CopilotKit/openmuse

```text
Repository: https://github.com/CopilotKit/openmuse
Commit: 4f3f7c765dcf5e3e098c645030d91e0c474f58a4 (HEAD at clone; 6151b4e… one hour earlier)
License: MIT (LICENSE)

What problem does it solve?
  A self-hosted personal agent product (Expo + Hono) with a durable task worker and stored action review.

Which exact files/classes/functions matter?
  apps/server/src/engine/worker.ts: claim with leaseId/leaseUntil, heartbeat at leaseMs/3, expiry of awaiting-review
  actions, interrupted vs failed on abort, no retry of an uncertain external write; packages/domain/src/agent.ts, jev.ts.

Which official example did we reproduce?
  None: the quick start needs Node 24, pnpm 11 and a CopilotKit Intelligence project key. Read-only study.

What result did we obtain?
  Design only.

What concept will we borrow?
  Lease-owned execution so one worker runs a goal; interrupted state after a restart; the reviewable plan.

Will we:
[ ] use it as a dependency
[ ] adapt a small component
[x] independently reimplement the idea
[ ] use only for benchmark comparison

What will remain uniquely ours?
  Everything below the pattern: Python worker inside the FastAPI process, SQLite lease rows, our audit.

How will it be cited?
  docs/references.json (key copilotkit2026openmuse); docs/life_os_pins.json.
```
