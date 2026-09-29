# Phase 1 design — the smallest LIFE OS core that proves feasibility

**Claim to prove.** A person's real-life commitments can be represented and deterministically checked for feasibility:
YES, RISKY or NO, with the first failing constraint named, from static travel times, on a reproducible example.

**Not in Phase 1.** Deep learning, SUMO, federated learning, networking simulation, Alexa, cross-city research,
multiple agents, any probability, any LLM in the check.

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
  feasibility/report.py    FeasibilityReport and Evidence contracts (Pydantic)
  feasibility/router.py    POST /api/lifeos/check-day
  feasibility/bench.py     wall time and RSS per example size, writes results/lifeos/feasibility/BENCH.md
  feasibility/__main__.py  CLI: python -m app.lifeos.feasibility <example.json> [--out report.json]
data/lifeos/examples/
  eva_day.json             the worked example (university 09:00, hospital 13:00, interview 16:00, assignment 18:00)
  healthy_day.json         a day that fits with slack everywhere
  stairs_day.json          the faster edge needs stairs; the person avoids stairs
  missing_place.json       a commitment without coordinates
backend/tests/test_feasibility_core.py
backend/tests/test_travel_static.py
evals/lifeos/scenarios.py  healthy_day, infeasible_day, accessibility_violation, stale_evidence (graders in code)
results/lifeos/feasibility/  reports and BENCH.md (committed as evidence)
Makefile target: judge-check (pytest deterministic subset, the four examples, web build, secret scan)
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

## 7. Exit gate

- All tests above green; full suite green.
- `python -m app.lifeos.feasibility data/lifeos/examples/eva_day.json` prints the verdict and the first failing
  constraint; the four example reports are committed under `results/lifeos/feasibility/`.
- `make judge-check` passes without a key or a network.
- `docs/GRAVEYARD.md` started; `FEATURE_CODE_MAP.md` and `REFERENCE_IMPLEMENTATIONS.md` updated with the OR-Tools
  mini-report and the reproduced official example.
- Limitations stated: static speeds, no probabilities, single day, sequence solved for at most about 15 commitments.
- Commit. Stop.
