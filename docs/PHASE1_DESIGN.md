# Phase 1 design — the smallest LIFE OS core that proves feasibility

**Headline claim, to be measured, not promised.** On a generated benchmark of days with seeded failures and
distractors, LIFE OS finds every infeasible day, names the constraint that actually fails and not the distractor, never
changes a feasible day, rejects every bad repair, and every accepted verdict carries a certificate that an independent
checker re-derives from the input — at a p95 under 200 ms per day on a laptop. The numbers go in `BENCH.md` and the
README only after they are measured; the README states what was measured and on what.

**The structural idea that makes it premium.** The solver proposes; an independent checker verifies. `verify.py`
shares no code with the CP-SAT model: it re-derives feasibility of any schedule — the solver's, a repair's, or a
person's hand-made one — from the canonical input and the same constraint definitions written a second time. A
report is accepted only when the verifier signs it. This is the certificate pattern from certified SAT solving
(an untrusted solver plus a trusted checker, see `RESEARCH_PIXY_BLACKBOX.md`), and it is what BlackBox's invariant
suite is to its repairs: the thing that makes a bad repair impossible to pass off.

**Not in Phase 1.** Deep learning, SUMO, federated learning, networking simulation, Alexa, cross-city research,
multiple agents, any probability, any LLM in the check.

**The seeded fixture, BlackBox-style.** Eva's day carries a distractor and a hidden real failure. The distractor: the
hospital leg looks tight (a 40-minute gap with a 32-minute static journey) but fits. The real failure: the interview
requires a printed CV, the print shop is a commitment that closes at 15:00 and depends on the CV being finished, and the
only slot that fits it collides with the hospital appointment. A shallow checker blames traffic; the correct verdict
names the dependency. The fixture is generated deterministically (seed pinned) and fully disclosed as synthetic.

**The receipt.** `examples/eva_day/` is committed unedited from a real run: the input, the report, the verifier log,
the solver log, `BENCH.md`, and `repaired_day.ics` — a real calendar file produced from the repaired plan that anyone can
import into Google, Apple or Outlook calendar without a key or a server.

**What already exists and is reused unchanged.** The seven contracts and the relational store (`backend/app/lifeos/
{entities,db,repo}.py`, thirteen tables, Alembic), the compiler (text → Commitment), the profile.

## 1. Architecture

```
data/lifeos/examples/eva_day.json ──▶ lifeos.twin.build_day ──▶ DayGraph (networkx)
                                          │ commitments, places, dependencies, constraints
                                          ▼
                                   lifeos.travel.static ──▶ TravelEdge per (from, to, mode) with provider="static",
                                          │                  freshness="static", accessibility flags
                                          ▼
                                   lifeos.feasibility.model ──▶ OR-Tools CP-SAT: intervals, precedence, travel,
                                          │                      windows, deadlines, accessibility
                                          ▼
                                   lifeos.feasibility.check ──▶ FeasibilityReport: verdict, first_failing, schedule,
                                          │                      slacks, evidence[], solver stats
                                          ▼
                         results/lifeos/feasibility/<example>.json · POST /api/lifeos/check-day · CLI · tests
```

Rules of the module: no network, no model, no randomness; the same input gives the same report byte for byte.

## 2. Folder structure (new files only)

```
backend/app/lifeos/
  twin/__init__.py
  twin/graph.py            DayGraph: nodes = commitments, edges = travel and dependency; free windows
  travel/__init__.py
  travel/static.py         static travel time by mode from place coordinates and a speed table; accessibility rules
  travel/speeds.yaml       per-mode speeds and access overheads with their source; per-city overrides
  feasibility/__init__.py
  feasibility/model.py     the CP-SAT model builder (variables, constraints) — one function per constraint kind
  feasibility/check.py     check_day(): verdict, first failing constraint by ordered re-solve, slacks, evidence
  feasibility/verify.py    the independent checker: re-derives feasibility of any schedule from the input; no shared code with model.py
  feasibility/certificate.py  signs a report only when verify() passes; hash of input + schedule + constraint set
  feasibility/ics.py       writes the repaired day as an RFC 5545 calendar file (the receipt)
  feasibility/fixtures.py  deterministic generator of benchmark days: N days, seeded failures, distractors, a manifest
  feasibility/report.py    FeasibilityReport and Evidence contracts (Pydantic)
  feasibility/router.py    POST /api/lifeos/check-day
  feasibility/bench.py     wall time and RSS per example size, writes results/lifeos/feasibility/BENCH.md
  feasibility/__main__.py  CLI: python -m app.lifeos.feasibility <example.json> [--out report.json]
data/lifeos/examples/
  eva_day.json             the worked example with the distractor and the hidden dependency failure (see above)
  healthy_day.json         a day that fits with slack everywhere
  stairs_day.json          the faster edge needs stairs; the person avoids stairs
  missing_place.json       a commitment without coordinates
backend/tests/test_feasibility_core.py
backend/tests/test_verify.py           one test per rejection path of the verifier, BlackBox-style
backend/tests/test_travel_static.py
evals/lifeos/scenarios.py  healthy_day, seeded_failure, distractor_not_blamed, bad_repair_rejected, accessibility_violation,
                           stale_evidence, byte_identical_rerun — graders in code, results committed per run
examples/eva_day/          the receipt: input, report, verifier log, solver log, repaired_day.ics
results/lifeos/feasibility/  reports and BENCH.md (committed as evidence)
docs/ACCEPTANCE.md         every gate with a runnable command and the artifact that proves it
docs/JUDGE_SCORECARD.md    self-assessment with the weakness column filled honestly
docs/GRAVEYARD.md          what was tried and dropped, with the number that killed it
.github/workflows/ci.yml   deterministic, keyless: unit tests, the eval subset, the exact scenario count asserted, web build, secret scan
Makefile target: judge-check (the same evidence CI runs, one command, no key, no network)
```

## 3. Schemas (additions; existing contracts unchanged)

```python
class Evidence(BaseModel):                 # a fact produced by tool code only
    id: str; kind: Literal["travel","dependency","window","deadline","accessibility","solver"]
    source: str                            # "static-speeds" | "cp-sat 9.x" | "twin"
    freshness: Literal["static","typical","recorded","live"]
    observed_at: datetime; detail: str; data: dict

class Transition(BaseModel):               # one leg between two placed commitments
    from_id: str; to_id: str; mode: Mode; depart: datetime; arrive: datetime
    travel_s: int; slack_s: int; accessible: bool; evidence_id: str

class Assignment(BaseModel):               # what the solver chose for a movable or anytime-before commitment
    commitment_id: str; start: datetime; end: datetime; moved_min: int

class FailingConstraint(BaseModel):
    kind: Literal["travel","dependency","window","deadline","accessibility","missing_place"]
    commitment_ids: list[str]; detail: str; evidence_ids: list[str]

class FeasibilityReport(BaseModel):
    person_id: str; day: date; verdict: Literal["YES","RISKY","NO"]
    first_failing: FailingConstraint | None
    risky_reasons: list[str]               # slack below the buffer, stale evidence
    transitions: list[Transition]; assignments: list[Assignment]
    min_slack_s: int | None; buffer_s: int
    evidence: list[Evidence]
    solver: dict                           # status, wall_ms, num_conflicts, ortools version
    inputs_hash: str                       # sha256 of the canonical input, for reproducibility
    certificate: Certificate | None        # present only when the independent verifier accepted the schedule

class Certificate(BaseModel):
    verified: bool; checker_version: str; constraints_checked: int; violations: list[str]
    input_hash: str; schedule_hash: str; signed_at: datetime
```

Verdict rules, deterministic: NO when CP-SAT is INFEASIBLE or a required place has no coordinates and no supplied
edge; RISKY when feasible but any transition slack is below the person's buffer (default 10 min) or any cited evidence
is older than its freshness window; YES otherwise. The first failing constraint is found by adding constraint groups in
a fixed order (windows → deadlines → dependencies → travel → accessibility) and re-solving until infeasible.

Static travel: `travel_s = haversine(from, to) / speed(mode, city) + access_overhead(mode)`, with the speed table and
its source in `speeds.yaml` (Dhaka average 7 km/h from the cited study; other cities from the table's stated source).
Accessibility: a walk edge longer than `max_walk_min` is excluded; an edge flagged `stairs` is excluded when the person
avoids stairs; an excluded edge is evidence, not silence.

## 4. Dependencies

`ortools` (Apache-2.0, new), `networkx` (present), `pydantic`, `sqlalchemy`, `pytest` (present). Nothing else.

## 5. Repo and file patterns reused

- BlackBox `backend/blackbox/models.py`: the fact/hypothesis/action split and the forward-only stage helper → our
  `Evidence`, `FeasibilityReport` and later `stages.py`; re-implemented, pattern attributed.
- BlackBox `evals/scenarios.py` and `harness.py`: scenario objects with code graders → `evals/lifeos/`.
- BlackBox `scripts/judge_check.sh` and `tests/test_engine.py`: keyless proof path and one test per rejection path.
- Pixy `framework/scripts/benchmark.md`: benchmark table with a correctness column → `BENCH.md` with the verdict per row.
- OR-Tools official example "scheduling with sequence-dependent setup times" reproduced unchanged first, then adapted.

## 6. Test cases

1. Eva's day is NO; first failing = travel between hospital (ends 14:00) and interview (16:00) when the static edge
   is longer than the gap — or YES with the recorded slacks when it fits; the expected outcome is fixed in the example.
2. A healthy day is YES, every slack above the buffer, no movable task moved (moved_min = 0 for all).
3. A movable task is placed inside its window without breaking any fixed commitment.
4. An anytime-before commitment ends before its deadline and after its dependencies.
5. A dependency cycle is NO with first failing = dependency.
6. A commitment without coordinates and without a supplied edge is NO with first failing = missing_place.
7. The stairs day: the faster edge is excluded, the slower accessible edge is used, the report cites the exclusion.
8. A walk longer than max_walk_min is excluded.
9. Slack below the buffer yields RISKY with the reason naming both commitments.
10. Evidence older than its freshness window yields RISKY with a stale-evidence reason.
11. The same input twice gives byte-identical reports (`inputs_hash` and JSON equal).
12. The CLI writes the report file and exits non-zero on NO.
13. The HTTP route returns the report and refuses an input that fails the contracts.
14. Benchmark: 5, 10 and 15 commitments solve under a stated budget (recorded, not asserted, in BENCH.md).
15. Distractor not blamed: on Eva's day the first failing constraint is the print-shop dependency, not the hospital leg.
16. Bad repair rejected: a hand-made schedule that moves the study block to fix the print shop but overlaps the
    assignment deadline is refused by the verifier with the violated constraint named.
17. Verifier independence: the verifier accepts every solver schedule on the benchmark and rejects every schedule
    with one injected violation (mutation test over windows, deadlines, dependencies, travel, accessibility).
18. The certificate is invalid when the input changes by one minute (hash mismatch) and must be recomputed.
19. The receipt: `repaired_day.ics` parses with the standard library reader and matches the report's assignments.
20. Benchmark generator: N seeded days regenerate byte-identically from the manifest.

## 6b. Upstream contributions (with your go, since they are external actions)

Two real findings from the compiler work deserve issues with minimal reproductions: dateparser returns None for a bare
clock time when `RELATIVE_BASE` is timezone-aware, and `search_dates` misreads "Friday 10 AM at" as 30 October; and
spaCy's small English model labels "CV" as a person. Filing them is cheap, true, and the kind of thing the winners did.

## 7. Exit gate

- All tests above green; full suite green.
- `python -m app.lifeos.feasibility data/lifeos/examples/eva_day.json` prints the verdict and the first failing
  constraint; the four example reports are committed under `results/lifeos/feasibility/`.
- `make judge-check` passes without a key or a network.
- `docs/GRAVEYARD.md` started; `FEATURE_CODE_MAP.md` and `REFERENCE_IMPLEMENTATIONS.md` updated with the OR-Tools
  mini-report and the reproduced official example.
- The verifier accepts 100 % of solver schedules and rejects 100 % of mutated ones on the benchmark; the numbers are in
  `BENCH.md` with the machine and the ortools version.
- `examples/eva_day/` committed unedited; `ACCEPTANCE.md` and `JUDGE_SCORECARD.md` written for this phase.
- CI green on a push with no secrets configured.
- Limitations stated: static speeds, no probabilities, single day, sequence solved for at most about 15 commitments,
  the fixture is self-authored so its realism is illustrative and the machinery is the contribution.
- Commit. Stop.
