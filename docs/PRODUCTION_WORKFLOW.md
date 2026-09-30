# The production workflow — every step the way a company would ship it

Companion to `PROBLEM.md` (the frozen problem), `PHASES.md` (build order), `ROADMAP.md`, `WORKFLOW.md` (what runs today) and
`PHASE1_DESIGN.md` (the next phase). This document answers one question: **if Uber, Google Maps, Citymapper, Reclaim and an
MLOps team built "make my day actually work", what would each step look like, which technology would carry it, and what would
the person actually feel?** Every step names the company pattern it copies, the open-source package that implements it, the
AWS service it runs on inside our credit envelope, the evidence it must leave behind, and the *moment* the person sees.

Nothing here is built in one go. The order of building is still `PHASES.md`, one phase at a time. This is the target shape,
so that every phase is built the production way from the first commit.

## 0. Why the project still reads as "simple", and what changes it

The features exist, but three things that make a product feel *inevitable* are missing:

1. **A promise with a number.** Google Maps promises "leave by 8:12 and you will arrive by 9:00". We must promise
   "leave by 8:12 and you arrive by 9:00 at least 9 times in 10, *for you, in this city, this week*" and then show the
   scoreboard where that promise is checked against what actually happened.
2. **A guarantee you can hand to someone.** Reclaim and Motion re-solve the calendar silently. We solve it with a
   constraint solver **and** an independent checker that signs a certificate: "this day is feasible under these
   travel-time bounds; the earliest violated constraint is X". A plan the person can dispute is a plan they trust.
3. **A loop that never sleeps.** The value is not the first plan, it is the *repair at 07:41 when the metro stops*.
   That needs a durable worker, a live world feed, a re-check, an approval, a calendar write, and a receipt, in under a minute,
   surviving a process crash. That is infrastructure, not a feature, and it is what companies spend their money on.

The steps below build exactly those three things.

## 1. The loop, and who does each step at company scale

```
S1 CAPTURE ─ S2 LIFE TWIN ─ S3 WORLD FEED ─ S4 PREDICT ─ S5 PROVE ─ S6 PLAN/REPAIR ─ S7 ACT ─ S8 MONITOR ─ S9 LEARN
      │            │              │              │           │             │            │          │          │
   Bedrock       Postgres      Kafka-style     BasicTS     OR-Tools     OR-Tools     approvals   durable    outcomes
   forced tool   event-sourced streams +       + DeeprETA  CP-SAT +     min-change   + signed    worker +   + per-user
   + Pydantic    + outbox      Redis "now"     residual +  verifier     repair       audit +     GTFS-RT    conformal
                                 state         MAPIE       certificate               calendar    triggers   recalibration
                                                                                     + Alexa
            cross-cutting: S0 identity/tenancy · S10 observability · S11 release/evals · S12 research layers
```

| Step | Company pattern copied | Open-source implementation | AWS home | Evidence left behind |
|---|---|---|---|---|
| S0 Identity | per-tenant rows, PII masked in logs (Pixy) | Cognito JWT → `person_id`; Presidio for PII in traces | Cognito, KMS | test: no row readable across persons |
| S1 Capture | Bedrock forced tool + schema validation (openai-agents structured output) | Pydantic v2 contracts, dateparser, spaCy, rapidfuzz | Bedrock (Haiku 4.5 / Nova Lite) | `results/lifeos/compiler.json` scorecard |
| S2 Life Twin | calendar as *output* of planning (Motion); event-sourced state | Postgres + Alembic, outbox table, day versions | RDS Postgres (or SQLite in dev, same schema) | ER diagram, migration chain, replay test |
| S3 World feed | GTFS-RT → stream → dedupe → Redis "current delays" (transit pipelines) | `gtfs-realtime-bindings`, Redis Streams (Kinesis when scale demands), Valhalla / OTP2 sidecar | ECS sidecar, ElastiCache | feed freshness metric, replayable recordings |
| S4 Predict | routing-engine ETA + learned residual (Uber DeeprETA), offline/online feature parity (Michelangelo Palette) | BasicTS models, Feast feature store, MAPIE conformal | g5 GPU for training, ONNX on ECS for serving | coverage table p10/p50/p90 per city per week |
| S5 Prove | certified solving (SAT-competition independent checker) | OR-Tools CP-SAT + pure-Python verifier + signed certificate | ECS | `certificate.json`, fuzz test solver vs verifier |
| S6 Plan/Repair | Motion's priority hierarchy; BlackBox "repair verified by full re-check" | same CP-SAT model with minimal-change objective | ECS | before/after diff, the receipt `.ics` |
| S7 Act | exact-action approvals, signed audit (openmuse) | approvals hash + TTL, HMAC checkpoints, ICS / Google Calendar, MCP → Alexa+ | Bedrock, SNS, SES | verifiable audit chain |
| S8 Monitor | durable execution (Temporal-style replay) | lease worker now; Temporal (self-hosted) when goals outlive a process | ECS + EventBridge Scheduler | crash-recovery test (`kill -9`) |
| S9 Learn | outcome-driven recalibration; production trace sampling | outcomes table, per-person conformal quantiles, Access Success Rate | Athena over S3 outcomes | weekly scoreboard, calibration curve |
| S10 Observe | three pillars + LLM traces | OpenTelemetry → Prometheus / Loki / Tempo / Grafana; Langfuse for LLM spans | CloudWatch (or Grafana OSS on one ECS task) | SLO dashboard, error budget |
| S11 Release | canary behind flags, offline eval gate before deploy | OpenFeature + flagd, DeepEval/promptfoo in CI, shadow mode | CodePipeline / GitHub Actions → ECS | eval report per PR, canary record |
| S12 Research | population effects, sparse sensing, privacy | SUMO/MATSim herding, Flower federated calibration | g5 / Colab | thesis tables |

Sources for the patterns: Uber's [DeepETA](https://www.uber.com/us/en/blog/deepeta-how-uber-predicts-arrival-times/) and
[DeeprETA post-processing](https://arxiv.org/pdf/2206.02127) (routing-engine estimate corrected by a learned residual);
[Michelangelo](https://www.uber.com/us/en/blog/from-predictive-to-generative-ai/) and its
[feature store](https://www.zenml.io/mlops-database/uber-michelangelo-michelangelo-palette-feature-engineering-platform-for-consistent-offline-training-and-low-latency-onli)
(same features offline and online); GTFS-Realtime streaming pipelines such as
[GTFS-Realtime-Stream-Engine](https://github.com/EderGtz/GTFS-Realtime-Stream-Engine) and
[real-time-transport-analytics](https://github.com/minerva1404/real-time-transport-analytics) (poll → stream → dedupe →
Redis "source of truth");
[conformal prediction for train delays](https://link.springer.com/chapter/10.1007/978-3-032-15120-9_17) (a 90 % window
validated on 12.8 M records); [Motion vs Reclaim](https://reclaim.ai/blog/motion-vs-reclaim) (calendar as output of a
constraint solve, re-solved on every change); [Temporal for durable agents](https://intuitionlabs.ai/articles/agentic-ai-temporal-orchestration)
and the [durable-execution survey](https://zylos.ai/research/2026-04-27-durable-execution-agent-runtimes/);
[agent observability in 2026](https://www.braintrust.dev/articles/agent-observability-complete-guide-2026) and
[guardrails that survive production](https://amirteymoori.com/llm-guardrails-prompt-injection-pii-agents-production/);
[canary releases with feature flags](https://configcat.com/blog/how-to-implement-a-canary-release-with-feature-flags/);
the [OpenTelemetry + Grafana stack for FastAPI](https://github.com/blueswen/fastapi-observability).

## 2. The steps in detail

Each step: **what happens → how a company does it → what we reuse → the wow moment → the test that proves it.**

### S0 · Identity and tenancy (cross-cutting)

- **What happens.** Every request carries a verified person. Every table row has `person_id`. Logs never contain names,
  addresses or free text.
- **Company way.** Cognito issues the JWT; the API only trusts the token's subject. Postgres row-level security means a
  bug in a query still cannot leak another person's day. Traces are PII-masked before they leave the process (Pixy's rule).
- **We reuse.** Cognito hosted UI (free tier covers a thesis and a hackathon), `fastapi` dependency that resolves the
  subject, Microsoft Presidio for masking, our existing per-browser id becomes the anonymous tier.
- **Wow.** "Export everything about me" and "erase me" already exist; with tenancy they become a one-click, provable
  privacy story on the Settings screen.
- **Test.** A signed token for person A cannot read, list or delete any row of person B; the audit shows the refusal.

### S1 · Capture: a sentence becomes a contract

- **What happens.** Text, voice (Alexa+), a pasted email or an imported calendar line becomes a `Commitment` with a place,
  a window, a duration, what to bring, what it depends on.
- **Company way.** One forced tool call to the model, the result validated by a strict schema, a rules path that is
  measured against the same evaluation set and wins ties, and a refusal when the time is missing (never a guess).
- **We reuse.** Bedrock Converse with `commitment__record` as a forced tool, Pydantic v2, dateparser, spaCy, rapidfuzz.
  Already built; scorecard in `results/lifeos/compiler.json`.
- **Wow.** The person types in Bangla or English "Submit CV at IUT print shop before 9 am Friday, need the USB"; the
  screen shows the compiled commitment with every field explained and a **"not saved: which Friday?"** when it is ambiguous.
- **Test.** 789 lines of evaluation, 100 % on rules for all fields, 4/4 refusals; live Bedrock run recorded with model id.

### S2 · Life Twin: the day as a versioned structure

- **What happens.** Commitments, places, constraints, travel edges, outcomes, actions and events live in 13 relational
  tables. A day is never edited in place; a repair writes a *new version* and an event says why.
- **Company way.** Postgres with Alembic migrations; an **outbox** table so that every state change also becomes an event
  the worker and the notifier consume (no dual writes); daily snapshots to S3 for replay.
- **We reuse.** SQLAlchemy 2.0, Alembic (already in place, SQLite in dev, Postgres in production with the same
  migrations), the `events` table as the outbox.
- **Wow.** A **timeline slider** on the Plan screen: drag back to 07:40 and see the day as it was before the metro
  disruption, forward to the repaired version, with the event that caused each change.
- **Test.** Replaying the events of a day rebuilds the same final state byte for byte.

### S3 · World feed: what the city is doing right now

- **What happens.** Every city gets three inputs: the road network (OpenStreetMap), scheduled transit (GTFS), and live
  transit (GTFS-RT vehicle positions, trip updates, alerts). Road traffic where an API covers it (Amazon Location),
  our own recordings where it does not.
- **Company way.** A poller decodes GTFS-RT protobufs and appends to a stream; a consumer deduplicates and keeps
  "current delay per trip" in Redis with a TTL; routing runs in a sidecar (Valhalla for roads, OTP2 for multimodal)
  on a network built from the same OSM extract, rebuilt nightly. Freshness is a metric with an alert.
- **We reuse.** `gtfs-realtime-bindings`, Redis Streams (Kinesis if a city exceeds it), Valhalla and OTP2 official Docker
  images, MobilityDatabase for feed discovery, our existing recorder for cities without feeds.
- **Wow.** The City screen shows **"data age"** for every layer, per city, and a world map of which cities are live,
  typical or recorded. Nothing pretends.
- **Test.** A recorded 24 h of a real feed replays through the same consumer and produces the same delay table.

### S4 · Predict: travel time with a guaranteed window

- **What happens.** For every travel edge the person may need, TrafficTwin returns p10/p50/p90 and a freshness label.
- **Company way.** Uber does not replace the routing engine; DeeprETA predicts the *residual* between the routing ETA and
  reality. Michelangelo computes features once and serves the same values online and offline. Conformal calibration
  turns any model's point estimate into a window with a coverage guarantee.
- **We reuse.** Valhalla/OTP as the base estimate; BasicTS models (GWNet, STID, STAEformer) as the learned residual on
  sensor cities; Feast as the feature store (offline Parquet on S3, online Redis); MAPIE conformal quantiles; ONNX Runtime
  for serving. Google-Routes data is never used for training (standing rule).
- **Wow.** The route card says **"9 in 10 days you arrive by 8:52"**, and the person can tap it to see last month's
  actual coverage for their own trips.
- **Test.** Coverage table per city per week: the p90 must cover ≥ 90 % of held-out outcomes, else the model is
  flagged and persistence is served (the Chronos negative result already shows this discipline).

### S5 · Prove: feasibility with a certificate

- **What happens.** Given the Life Twin and the travel windows, the solver answers **feasible / risky / impossible**,
  names the first constraint that breaks, and an independent verifier re-checks the answer and signs it.
- **Company way.** SAT competitions accept a result only with a proof another program checks. Reclaim and Motion re-solve
  on every change; we add the proof.
- **We reuse.** OR-Tools CP-SAT (official example reproduced unchanged first), a pure-Python verifier that shares no code
  with the model builder, HMAC signature with the existing audit key.
- **Wow.** **"Why not?"** on any red commitment shows the exact chain: "CV print shop closes 17:00 → arrival p90 17:12 →
  because the 15:30 meeting ends 16:40". The certificate is downloadable and re-checkable offline.
- **Test.** 10 000 random days: solver and verifier never disagree; a deliberately corrupted certificate is rejected.

### S6 · Plan and repair: the smallest change that makes the day work

- **What happens.** When the day is infeasible, the same model is re-solved with a *minimal-change* objective:
  move as few commitments as possible, by as little as possible, respecting priority and flexibility.
- **Company way.** Motion's documented hierarchy (ASAP, hard deadline, soft deadline, priority, duration, chunking);
  BlackBox's rule that a repair counts only if the *full* re-check passes.
- **We reuse.** OR-Tools with weighted objective; the verifier from S5 runs again on the repaired day.
- **Wow.** A **before/after strip**: two rows of the day, changed commitments highlighted, the certificate on the
  repaired one, and a receipt in `.ics` the person can send to anyone.
- **Test.** Repair never moves a `fixed` commitment; the repaired day always carries a valid certificate.

### S7 · Act: propose, ask, do, sign

- **What happens.** Nothing external happens without the person seeing the exact action. Reversible writes go through;
  irreversible or external ones wait for approval bound to a hash and a 30-minute expiry.
- **Company way.** Approvals per exact action, standing rules per tool, a hash-chained audit with signed checkpoints;
  guardrails that are layered and testable (allowlisted tools, argument validation, human approval on irreversible actions).
- **We reuse.** All of this exists (`approvals.py`, `audit.py`); the calendar write goes to ICS today and Google Calendar
  API when connected; SNS/SES for notifications; the MCP server at `/mcp` for Alexa+.
- **Wow.** On Alexa: **"Your 9 am at the print shop is at risk; I can move the bank to 11:30 and book the earlier
  bus. Say yes to apply."** The same approval appears in the web app with the certificate attached.
- **Test.** An approval for a different argument set is refused; the audit verifies from the genesis hash.

### S8 · Monitor: the loop that survives a crash

- **What happens.** Every planned departure is a watched trigger. A GTFS-RT delay, a worse p90, a moved meeting or a
  crashed process must all lead to the same place: re-check, repair, approval.
- **Company way.** Durable execution: state persisted per step, replay on a new worker, hysteresis so a plan does not
  flip every five minutes (the 44-notification bug is the reason).
- **We reuse.** The lease worker with heartbeat and reaper (already survives `kill -9`); EventBridge Scheduler for
  time triggers; Redis Streams consumers for feed triggers; Temporal self-hosted only if a goal must outlive a deploy.
- **Wow.** The Today screen shows **"watching 3 departures · last check 12 s ago · next 07:45"**, and a live badge when a
  repair is in progress.
- **Test.** Kill the worker mid-repair; the goal resumes from the last persisted step with no duplicate calendar write.

### S9 · Learn: the scoreboard that makes the promise honest

- **What happens.** Every trip ends in an outcome: predicted vs actual departure and arrival. Outcomes drive the
  person's own conformal quantiles and the thesis metrics: Access Success Rate, Access Regret, Buffer Waste, Recovery Rate.
- **Company way.** Production trace sampling scores real traffic, not just a test set; retraining is scheduled, validated
  against the previous model and promoted only if better.
- **We reuse.** The `outcomes` table, MAPIE recalibration per person, a nightly job that rebuilds the coverage table,
  Athena over S3 outcome Parquet for the thesis tables.
- **Wow.** A **personal calibration card**: "your p90 has covered 93 % of 41 trips; buffer waste 6 min/day, down from 14".
- **Test.** The weekly report is regenerated from raw outcomes by one command and matches what the app shows.

### S10 · Observe (cross-cutting)

OpenTelemetry in the API, worker and solver; the collector fans out to Prometheus (metrics), Loki (logs), Tempo (traces)
and Grafana; Langfuse records every model call with cost. Three SLOs: plan request p95 < 800 ms, feed freshness < 120 s
in live cities, repair-to-notification < 60 s. Error budgets gate releases.

### S11 · Release (cross-cutting)

Every PR runs the unit tests, the compiler evaluation, the solver/verifier fuzz and a DeepEval suite for the agent;
a merge deploys as a canary behind an OpenFeature flag to 5 % of persons (hashed, sticky); new forecast models run in
shadow mode next to the serving model for a week before promotion.

### S12 · Research layers (thesis only)

MATSim or SUMO for the herding question (what if 20 % of a city follows the same advice), the sparse-sensing curve
(how few sensors still beat persistence), and Flower for federated calibration so outcomes never leave the phone.

## 3. What is deliberately not built

Routing engines, transit planners, solvers, map matchers, simulators, feature stores, observability backends, identity.
All of them exist under permissive licences; the project writes adapters, contracts, the verifier, the evaluation and
the product. The list of pinned upstreams stays in `REFERENCE_IMPLEMENTATIONS.md` and `THIRD_PARTY_LICENSES.md`.

## 4. Cost inside the credit envelope

| Component | Service | Monthly estimate |
|---|---|---|
| API + worker + routing sidecar | one ECS Fargate task set (or a single t4g.medium during the thesis) | 15–30 USD |
| Postgres | RDS db.t4g.micro | 12 USD |
| Redis | ElastiCache t4g.micro (or in-task Redis during the thesis) | 0–12 USD |
| Model calls | Bedrock Haiku 4.5, ~50 k calls | 5–10 USD |
| Training | g5.xlarge spot, ~20 h a month | 15 USD |
| Storage | S3 outcomes, artefacts, snapshots | < 2 USD |

Well inside the ~331 USD of credits in `RESOURCES.md`; the two 150 USD hackathon credits run to 2028.

## 5. Order of building (unchanged)

`PHASES.md` is the authority. The next phase is Phase 1 (`PHASE1_DESIGN.md`): S5 with the certificate. It starts only with
the OR-Tools official example reproduced unchanged, and stops at its exit gate.
