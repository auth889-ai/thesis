# Repository research report: Pixy and Project BlackBox

Read on 2026-09-30 from blob-less clones; every file named below was opened. Devpost pages fetched the same day.

---

## 1. Pixy — "Literally the Smallest Functioning LLM Ever"

```text
Repository:   https://github.com/bitanath/pixy
Commit:       ec97e8d9489a76cc124518d80dbf4ec799135171 (2026-09-18)
License:      Apache-2.0 (LICENSE, © 2026 bitanath). Model weights separately under the Falcon-LLM licence.
Hackathon:    Arm Create: AI Optimization Challenge — Overall Winner (Devpost page).
```

**Problem solved.** One narrow, measurable problem: run a functional 0.5 B-parameter language model, multi-turn, on an
Apple Watch Series 9 (about 100 MB peak RAM, two cores, no GPU) at a usable token rate. A second, server-side use of the
same runtime: PII masking of log lines on an ARM Linux host.

**Core architecture.** A dependency-free inference runtime in Zig (`framework/core/`: `main.zig` entry, `index.zig`
exports, `mats.zig` matmul kernels, `ops.zig` tensor primitives, `dequant.zig` quantisation, `accelerate/` Metal
shaders, `stream.zig` session streaming), a second Zig runtime for a small CNN that turns a watch drawing into a prompt
(`visual/core/`), a PyTorch training pipeline that only produces weights (`training/`), a profiler-report CLI in Zig
(`performix/pxy/`), and a SwiftUI watch app that links the two static libraries. Python is confined to training,
validation and weight conversion (`HOW-TO-LLM.md`, "Runtime must not require Python").

**Exact folders/files inspected.** `README.rst`, `HOW-TO-LLM.md`, `OPTIMIZATIONS.md`, `LICENSE`,
`framework/core/{main,stream,ops}.zig`, `framework/scripts/{benchmark.md,deploy.sh}`, `training/TRAIN.md`,
`performix/pxy/src/main.zig`, `performix/deploy.sh`, `visual/core/main.zig`, `visual/convert_weights.py`, the tree of
`pixy Watch App/`, `framework/core/assets/*.gguf`, `performix/reports/*.zip`.

**What is original work.** The Zig runtime (tensor ops, Q8_0 and Q5_K/Q6_K dequantisation, matmul kernels, RoPE,
attention for the Falcon-H1 Mamba2 hybrid), the ARM NEON mapping through Zig `@Vector`/`@mulAdd`/`@reduce`/
`@shuffle`/`@select` (`OPTIMIZATIONS.md`, ten documented transformations with the NEON instructions each emits), the
mmap loader, the streaming session, the drawing CNN and its runtime, the Performix report parser and renderer, the watch app.

**What is reused/external.** Falcon-H1 0.5B and Tiny 90M weights (TII), llama.cpp's GGUF format and its quantiser
(`convert_hf_to_gguf.py`, `quantize`), the `ai4privacy/pii-masking-200k` dataset, Perfect Freehand for synthetic
drawings, Arm Performix for profiling, Apple Metal for the abandoned GPU path.

**What was trained.** A CNN emoji classifier on nine drawn shapes (PyTorch, `training/train_convnet.ipynb`,
`weights.pth`, `weights_best.pth`, converted to `visual/core/assets/weights.fw`). A QLoRA fine-tune of Falcon-H1 for
PII masking (`training/TRAIN.md`: 209 k examples plus 10 % identity examples; LoRA on `in_proj`, `x_proj`, `dt_proj`;
`out_proj` kept in fp16 for the Mamba2 kernel; merged, converted to GGUF, quantised to Q5_K_M).

**What was only inference.** The chat model itself (Falcon-H1 0.5B instruction-tuned, quantised, not trained).

**What was benchmarked.** `framework/scripts/benchmark.md`: three GGUF sizes embedded via `@embedFile`, one fixed
prompt, generation time by `mach_absolute_time`, RSS by `task_info`, before and after the July 25 optimisation
(`@Vector(4)` → `@Vector(8)` in six kernels; `f64` → `f32` in RoPE, softmax, SwiGLU, RMS norm, attention). Devpost:
Q5_K 354 MB / 332 MB RAM / 3,271 ms vs Q8_0 531 MB / 497 MB RAM (64 MB with mmap) / 1,628 ms; SIMD 1.83×; mmap cut the
initial load from 535 MB to about 4 MB; about 3 tokens/s on the watch (README says 1.5; the two figures differ and the
repository does not reconcile them).

**What metrics were used.** File size, binary size, generation time, tokens per second, RSS delta, and a correctness
sanity check per model ("What is the capital of India?" with the answer recorded next to the timing).

**How correctness was proven.** Output text recorded beside every benchmark row; a Swift smoke test
(`framework/scripts/test.swift`) run by `deploy.sh` after every build; the CNN validated in `visual/validate.ipynb`; the
watch demo and the Linux PII-masking binary run in front of the judges.

**How failures were handled.** A written graveyard on Devpost: NEON beyond 128-bit registers, Metal shaders (filtered by
Swift), SmolLM2 (incoherent multi-turn), precomputed dequantised weights (1.5 GB), Q5_K-only quantisation (accuracy loss
on specific tensors). `stream.zig` carries an honest inline note that the streaming path was written quickly and needs a
day of review. Performix's own limitation (`INSUFFICIENT_PMU_COUNTERS`) is recorded in `HOW-TO-LLM.md`.

**What tests exist.** One Swift smoke test per build; a validation notebook for the CNN; no unit-test suite.

**What artifacts are generated.** GGUF files at four sizes, static libraries per target (`llm-watchos.a`,
`visual-watchos.a`, `llm-linux-piimask`), PyTorch checkpoints, converted weights, four Performix report archives, the
benchmark table.

**What is reusable for LIFE OS.** The engineering discipline, not the code: benchmark-first with a fixed prompt and a
correctness column; profile before optimising and keep the profiler reports in the repository; a documented
edge/cloud split (what runs where and why); local processing of private text before any cloud call (their PII masker);
lazy loading of model files with a measured RAM claim; a resource budget stated as a number (100 MB, two cores) and every
change measured against it; a one-command deploy script that also runs the smoke test; a written graveyard.

**What should NOT be copied.** The Zig inference engine, the SIMD kernels, the GGUF loader and the watch app: LIFE OS
runs on servers and phones with PyTorch and ONNX available, and its models are graph and tabular models, not a chat LLM.
Copying an inference engine would add a technology without a necessary role.

**License/attribution requirements.** Apache-2.0: any code taken needs the licence text and a NOTICE line; the Falcon
weights carry their own terms. We take no code, so only the pattern attribution in `REFERENCE_IMPLEMENTATIONS.md` applies.

---

## 2. Project BlackBox — evidence-gated autonomous data-incident repair

```text
Repository:   https://github.com/alejandro-publius/blackbox-datahub
Commit:       b72a32c64e11404b1de98b517bde7e487ca35963 (2026-09-10)
License:      Apache-2.0 (LICENSE); CITATION.cff present.
Hackathon:    Build with DataHub: The Agent Hackathon — Grand Prize out of 600+ (README, Devpost).
```

**Problem solved.** Silent semantic data failures: a payment provider starts sending cents instead of dollars, every
schema validates, every job stays green, revenue is 93× wrong. One sentence from an engineer starts an agent that reads
lineage, proves the cause, repairs the transform, verifies against an invariant suite, and writes the resolution back.

**Core architecture.** FastAPI backend (`backend/blackbox/api.py`) with an incident store that persists full state
snapshots and fans them out over SSE (`store.py`); an investigator loop on Claude (`agent/investigator.py`) where the
model chooses tools and deterministic tools produce every fact (`agent/tools.py`); Pydantic models mirrored exactly in
the frontend types (`models.py`); a forward-only stage machine with two terminal exits; a repair module that writes a
real file, rebuilds the warehouse, runs the full invariant suite and commits on an isolated worktree (`repair.py`);
DataHub reads over three transports and writes of incidents, notes and tags (`datahub/`); optional OpenTelemetry to
Phoenix (`tracing.py`); a Next.js command centre with React Flow lineage; a deterministic eval harness (`evals/`).

**Exact folders/files inspected.** `README.md`, `LICENSE`, `Makefile`, `CITATION.cff`, `.github/workflows/ci.yml`,
`backend/blackbox/{models,api,store,repair,tracing}.py`, `backend/blackbox/agent/{investigator,tools,prompts}.py`,
`backend/blackbox/datahub/writeback.py`, `evals/{README.md,scenarios.py,harness.py,results/latest.md}`,
`docs/{ARCHITECTURE,ACCEPTANCE,JUDGE_SCORECARD,DEMO_SCRIPT}.md`, `examples/sample-incident/{README.md,incident_state.json}`,
`pipeline/invariants/test_invariants.py`, `scripts/judge_check.sh`, the test names in `tests/`.

**What is original work.** The evidence-gated state machine (`IncidentStage`, `STAGE_ORDER`, `can_advance_to`; stages
advance only as a side effect of tool activity); the three-kind object model — facts (`EvidenceItem`, produced only by
tool code, carrying `kind`, `source` and the `transport` that produced it), hypotheses (LLM-proposed, resolved only with
cited evidence ids), actions (system code, gated by stage and verified by re-execution); the confirm gate
(`t_confirm_root_cause`: rejects unless cited evidence includes a lineage/metadata item and a quantitative item, the
blamed asset is in the traversed graph, the quantitative payload references the blamed field and asset by name, and the
cited numbers actually show an anomaly); the symmetric no-incident gate (`t_declare_no_incident`: needs quantitative
evidence that shows normal ranges); the two-phase flow (investigation stops at `ROOT_CAUSE_CONFIRMED` until an operator
authorises repair; `allow_repair` in the executor); the repair loop (path-restricted to `pipeline/transforms/*.sql`,
difflib diff from disk, rebuild, all 32 invariants and the KPI inside [0.8, 1.3]); revert of unverified patches
(`_cleanup_unverified_patch`); writeback that raises the incident at proof and resolves it only after verification; the
eval harness with code graders and contamination scrubbing; the keyless `judge-check`.

**What is reused/external.** Anthropic SDK, DataHub OSS with its MCP server, Agent Context Kit and GraphQL, DuckDB,
pytest, difflib, git worktrees, `gh`, Next.js, React Flow, OpenInference/OpenTelemetry, Arize Phoenix.

**What was trained.** Nothing. **What was only inference.** Claude as the investigator.

**What was benchmarked.** The eval battery (`evals/README.md`): `positive_incident` (11 machine-checked criteria:
correct root cause, distractor not blamed, repair targeted and single-file, 32/32 invariants, KPI within 1 % of the
committed baseline, writeback done, plus turns and tool calls reported), `control_no_incident` (healthy data must yield
`NO_INCIDENT`, no patch, transforms untouched), `bad_repair_rejected` (a blanket `/100` must fail the
historical-immutability invariants; runs without any key), `datahub_ablation` (metadata tools off and the gate
relaxed so the test is not circular; result reported honestly: the agent still diagnoses the five-transform fixture by
reading files), `positive_incident_repeat` for consistency. Results committed per run under `evals/results/`.

**What metrics were used.** Pass/fail per machine-checked criterion; KPI anomaly ratio before and after; invariants
passed/total; turns and tool calls per run; wall time; token usage in the transcript.

**How correctness was proven.** Every fact is a tool output with an id; the root cause cannot be confirmed without cited
evidence that names the field and shows the anomaly; the repair only counts when the real file is changed, the warehouse
rebuilt and the whole suite green; graders read the final state JSON, the transcript, pytest and `git diff`, never the
model's own words; an unedited run is committed under `examples/sample-incident/`; CI runs the deterministic subset on
every push and asserts the invariant count is exactly 32 so a shrunken suite cannot pass as green.

**How failures were handled.** Terminal `FAILED` with the error recorded; unverified patches reverted and the warehouse
rebuilt; publication runs after verification and is non-gating, its failure recorded as evidence; the ablation's
uncomfortable result written into the README; limitations listed in `ACCEPTANCE.md` and a self-critical
`JUDGE_SCORECARD.md`; a security finding (`read_csv('.env')` past a SELECT-prefix guard) fixed and regression-tested.

**What tests exist.** 58 unit tests (`tests/test_engine.py`: stage order, sticky terminal stages, every rejection path of
the confirm gate, the no-incident gate, hypothesis elimination needs evidence, repair path allowlist, real diff,
read-only SQL, filesystem exfiltration blocked; `tests/test_repair_pr.py`; `tests/test_tracing.py`; `tests/test_context_kit.py`),
32 pipeline invariants, the eval battery, a Playwright drill.

**What artifacts are generated.** `data/incidents/{id}.json` full state and `{id}.transcript.jsonl`, `evals/results/run_NNNN.json`
and `latest.md`, per-scenario artifacts, the difflib patch, the fix branch and optional PR, DataHub incident, note and tag,
a Phoenix trace per incident when enabled.

**What is reusable for LIFE OS.** The whole control philosophy, re-implemented on our contracts: the LLM decides where to
look, deterministic and probabilistic tools decide what is true, the person decides when it may act. Concretely: facts as
typed evidence items with provenance and freshness; hypotheses that can only be confirmed or eliminated by citing
evidence; a forward-only stage machine whose transitions are side effects of tool calls; a feasibility gate with the same
shape as `confirm_root_cause`; repair verified by re-running the complete check, with revert on failure; a healthy control
and a bad-repair rejection as standing evals; outcome writeback into the twin's history; a keyless judge check; an
unedited example run committed; limitations and a scorecard written down.

**What should NOT be copied.** The DataHub-specific transports, the DuckDB warehouse, the SQL repair surface, the
Next.js command centre, the single-incident fixture. LIFE OS repairs a schedule, not a transform, and its truth comes from
routing engines, forecasters and a constraint solver, not a warehouse.

**License/attribution requirements.** Apache-2.0 with a citation file. We re-implement the patterns; if any function is
copied later it carries the licence header, the source path and the commit, and is listed in
`REFERENCE_IMPLEMENTATIONS.md` and `THIRD_PARTY_LICENSES.md`.

---

## 3. Mapping: reference idea → LIFE OS

| Reference idea | LIFE OS equivalent | Why useful | Package / code / service | Original work required | Research experiment | Production use | Priority |
|---|---|---|---|---|---|---|---|
| BlackBox evidence items (facts only from tools, with provenance) | `Evidence` with `kind` (travel, forecast, dependency, accessibility, weather, calendar), `source` (valhalla, otp, model id, solver), `freshness`, `observed_at` | the LLM never types a number | our `lifeos/evidence.py`; BlackBox `models.py` as the shape | yes | every decision metric traces to evidence ids | yes | P1 |
| BlackBox hypothesis + confirm gate | `Hypothesis` (traffic risk, hospital delay, missing document, incomplete prep, personal lateness) confirmed only with cited evidence that names the commitment and shows the risk | the agent cannot declare "traffic is the problem" | re-implemented gate; OR-Tools + AccessTwin as the tools | yes | agent-hallucination eval | yes | P1 (gate shape), P13 (agent) |
| BlackBox forward-only stage machine | `UNDERSTAND → HYPOTHESES → EVIDENCE → FEASIBILITY_GATE → PLAN → APPROVAL → ACT → VERIFY → WRITE_OUTCOME`, transitions as side effects of tools | honest state for the UI and the audit | our `lifeos/stages.py` | yes | — | yes | P1 |
| BlackBox two-phase operator authorisation | plan is proposed; consequential actions wait for approval (already in `agent/approvals.py`) | policy over persuasion | existing permission engine | small | action-approval eval | yes | done |
| BlackBox repair verification (rebuild + full suite) | after any repair, rerun the whole-day feasibility check and every constraint; success only after verification | a repair that fixes one commitment and breaks another must fail | `feasibility.check_day` rerun; OR-Tools | yes | bad-repair eval | yes | P1 (check), P16 (repair) |
| BlackBox healthy control | a feasible day must come back unchanged: no invented problem, no moved task | false-positive guard | eval scenario | yes | healthy-day eval | CI | P1 |
| BlackBox bad-repair rejection | a repair that breaks another deadline is rejected by the full check | verification has teeth | eval scenario | yes | bad-repair eval | CI | P16 |
| BlackBox revert of unverified patch | an unverified plan change never reaches the twin; the previous plan is restored | no half-applied days | `lifeos/plan.py` transactions | yes | — | yes | P16 |
| BlackBox writeback | outcome and reason written into the twin's history (`outcomes`, `events`) | memory that outlives the run | Phase 0 tables | small | calibration studies | yes | P1 (report), P19 |
| BlackBox code graders, no self-grading | metrics computed from stored state, transcripts and solver output, never from model text | trustworthy evals | `evals/` harness | yes | all | CI | P1 |
| BlackBox `make judge-check` | keyless deterministic proof: unit tests, healthy-day check, web build, secret scan | judges verify in one command | Makefile + script | small | — | CI | P1 |
| BlackBox unedited example run | `examples/eva_day/` with input, evidence, report, solver log | inspectable without a key | files | small | — | — | P1 |
| BlackBox transport provenance | `Evidence.source` names the engine and model version; `freshness` says live, typical, recorded, static | "stale evidence" handled | contracts | small | stale-evidence eval | yes | P1 |
| BlackBox limitations and scorecard | `ACCEPTANCE.md`-style gate table and a self-critical scorecard per phase | honesty | docs | small | — | — | every phase |
| Pixy benchmark-first with a correctness column | `results/lifeos/feasibility/BENCH.md`: solver wall time and RAM per example size with the verdict recorded | performance claims with proof | pytest-benchmark or a small timer | small | solver scaling | yes | P1 |
| Pixy profile before optimising | one OpenTelemetry trace per goal: compiler → twin → routing → forecast → AccessTwin → solver → agent, p50/p95 per span | find the slow part before touching it | opentelemetry-sdk, CloudWatch or Phoenix | small | latency study | yes | P20 |
| Pixy mmap / lazy loading | load forecaster checkpoints and embeddings lazily, measured cold start and RSS | RAM and cold-start cost | torch `mmap=True`, onnxruntime | small | edge/cloud study | yes | P19, P24 |
| Pixy local PII masking | redact names, e-mail addresses, phone numbers and free text locally before any cloud model call; the compiler's model path receives the redacted text | privacy | spaCy NER plus rules; optionally a small local model | yes | compiler accuracy with and without redaction | yes | P1 of the compiler (already built), extend at P15 |
| Pixy edge/cloud split | phone: compiler rules path, static feasibility, cached edges; cloud: forecasters, routing engines, the model | a decision when the network is gone | onnxruntime, executorch | yes | accuracy vs latency vs energy | yes | P24 |
| Pixy model compression | quantised forecaster for the edge, measured against the full model on decision metrics | same decision quality at lower cost | onnxruntime quantisation | yes | edge study | yes | P24 |
| Pixy resource-budget metrics | a stated budget per request (latency, RAM, cost) checked in CI | keeps the product usable | benchmark script | small | — | CI | P1 (solver), P20 |
| Pixy benchmark CLI | `python -m app.lifeos.feasibility.bench` | reproducible numbers | script | small | — | — | P1 |
| Pixy graveyard | `docs/GRAVEYARD.md`: what was tried and dropped, with the number that killed it | a reviewer trusts a project that records its failures | docs | small | — | — | every phase |

---

## 4. Dependency decisions

| Repository | Decision | Reason |
|---|---|---|
| google/or-tools | [x] direct package dependency (`ortools`, Apache-2.0) | CP-SAT is the feasibility and day optimiser; never rewritten |
| valhalla/valhalla | [x] external service, [x] adapter (`pyvalhalla` or HTTP) | road routing, isochrones, map matching; MIT |
| opentripplanner/OpenTripPlanner | [x] external service | transit and multimodal on GTFS; LGPL, never vendored |
| conveyal/r5 | [x] external service via `r5py`, pinned | opportunity reachability (P26); unstable third-party API noted by its authors |
| nnzhan/Graph-WaveNet, liyaguang/DCRNN, GestaltCogTeam/STID, XDZhelheim/STAEformer | [x] research benchmark, [x] adapter through BasicTS | trained one at a time in Phase C and later; STAEformer has no licence file: read and benchmark only |
| HKUDS/OpenCity, tsinghua-fib-lab/UniST | [x] research benchmark | cross-city and low-data experiments only after the classical chain; UniST has no licence file |
| LibCity/Bigscity-LibCity | [x] architecture inspiration | config, data, model, runner, evaluator layout for our experiment folders |
| eclipse-sumo/sumo | [x] direct package dependency (`eclipse-sumo`, `traci`, EPL-2.0) | the digital twin (P21) |
| matsim-org/matsim-libs | [x] external service (Java, GPL-2) | population simulation (P22); never linked |
| nsnam/ns-3-dev-git, eclipse-mosaic/mosaic | [x] external service | networking experiments (P23) |
| adap/flower | [x] direct package dependency (`flwr`, Apache-2.0) | federated personal models (P25) |
| openai/openai-agents-python | [x] architecture inspiration | structured output and human-in-the-loop patterns on Bedrock; no dependency |
| langchain-ai/langgraph | [ ] not needed | our worker already gives durable, resumable runs with a lease; adding a second runtime adds nothing necessary |
| open-telemetry/opentelemetry-python | [x] direct package dependency (P20) | one trace per goal |
| bitanath/pixy | [x] architecture inspiration | patterns only; no code |
| alejandro-publius/blackbox-datahub | [x] architecture inspiration; [ ] small licensed code reuse held open for `models.py`-style stage helpers if re-implementation would be a copy anyway | patterns re-implemented on our contracts |

---

## 5. AWS, where it improves the product or the demo

| Service | Use | Phase |
|---|---|---|
| Bedrock | compiler model path and the agent (already in) | now |
| S3 | experiment artifacts and checkpoints (`experiment_id/` folders), datasets | Phase A onward |
| RDS PostgreSQL | the authoritative Life Twin store by URL when accounts arrive | block D |
| Lambda | lightweight event handlers (calendar changed, weather changed) feeding the event bus | P17 |
| ECS/Fargate | the FastAPI service and the routing engines for the demo month | block D/F |
| EventBridge/SQS | monitor and repair events | P17 |
| SNS | alerts (already in) | now |
| CloudWatch + OpenTelemetry | traces and p50/p95 per stage | P20 |
| Cognito | sign-in | block D |

Training stays on Colab and Kaggle unless a run cannot finish there; the credits pay for the demo month and the few GPU
hours Colab cannot give.
