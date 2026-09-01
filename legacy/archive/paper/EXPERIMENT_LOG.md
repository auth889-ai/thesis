# DhakaFlow — experiment log (running, includes failures)

Every entry records what was run, what came out, and what it changed. Negative
results are kept: they are what stops a contribution being claimed on an
untested assumption.

---

## E1 · P0 vertical slice, single O-D pair (2026-08-14)

**Setup.** Frozen Dhaka R1 network (sha256 `06194df0…`, verified). One O-D pair,
3 penalty-method alternatives, 5 route distributions, N = 300…1500 vehicles,
fixed-time signals, SUMO 1.27.1.

**Result.** The best *single* path beat the free-flow-cheapest path by 22.8% mean
time loss (188.4 s vs 244.1 s at N=300). Every splitting candidate **lost** at
every demand level tested.

**Why (structural, not tuning).** All candidate routes leave the same origin
edge, so they share one bottleneck. Rerouting cannot relieve a bottleneck that is
common to every alternative.

**Consequence.** Contribution C3 (system-optimal routing) is untestable on
single-O-D demand. Multi-OD demand became a prerequisite, not an enhancement.

**Bugs this run exposed (both fixed, both now tested):**
1. 8 edges in R1 are tagged 0.56 m/s while their forward twins are 16.67 m/s — an
   OSM artefact. One is Lab 02's "north" representative edge, so its recorded
   route costs (8065 s) are dominated by that single link. Endpoints are now
   drawn through a stated plausibility filter. The frozen lab is untouched.
2. SUMO trip statistics average **completed trips only**. At N=2500:
   `loaded=2500 inserted=500 waiting=2000` — yet mean travel time looked healthy,
   because 2000 vehicles were queued outside the network and invisible to the
   metric. `DemandCompletion` + a comparability gate now exclude such runs from
   ranking instead of silently ranking them.

---

## E2 · Multi-OD routing: user-optimal vs system-aware (2026-08-15)

**Setup.** 20 O-D pairs, 60 vehicles each (1200 total), 3 diverse alternatives per
pair (overlap ≤ 0.6), hub-directed sampling. Contention verified *before*
simulating: 501 loaded edges, **192 contended edges**, max edge load 360 veh
⇒ `testable: true`. 3 seeds, 7200 s horizon, all runs comparable, 0 collisions.

**Result — NEGATIVE.**

| Policy | mean time loss | stdev |
|---|---|---|
| `user_optimal` (selfish) | **357.8 s** | 2.5 |
| `system_aware` (inverse-cost spreading) | 407.5 s | 98.2 |
| `random_alternative` (control) | 478.5 s | 138.2 |

Naive spreading is **13.9% worse** than selfish routing, with 40× the variance.

**Interpretation.** This refutes the assumption that distributing traffic is
inherently system-optimal. The `system_aware` policy tested here weights
alternatives by inverse free-flow cost *regardless of congestion*, so it pushes
vehicles onto slower roads even where nothing needed relieving. That is spreading,
not system optimisation — and the control arm confirms the ordering is not random.

**Consequence.** A real system optimum must come from established assignment
theory, not from a hand-made sharing rule:
* Beckmann et al. (1956) — user equilibrium / system optimum formulation
* Frank–Wolfe / Method of Successive Averages for the assignment problem
* BPR volume–delay function for congestion-dependent edge cost

System optimum minimises Σ xₐ·tₐ(xₐ) and is obtained by assigning on **marginal**
cost, not average cost. Implementing that is the next routing step; the current
`system_aware` policy is retained as a named weak baseline, not deleted.

---

## E3 · R4 DUE vs R5 DSO — official SUMO assignment (2026-08-15)

**Setup.** Official `duaIterate.py` from the local SUMO 1.27.1 install, both arms.
The arms differ by **exactly one documented flag**:

```
R4 DUE  python $SUMO_HOME/tools/assign/duaIterate.py -n <net> -t trips.xml \
            -l 4 --nointernal-link --logit duarouter--routing-threads 4 sumo--end 7200
R5 DSO  python $SUMO_HOME/tools/assign/duaIterate.py --marginal-cost -n <net> \
            -t trips.xml -l 4 --nointernal-link --logit ... (identical otherwise)
```

`--marginal-cost` is SUMO's own documented system-optimal mode. `--logit` is
applied to **both** arms because SUMO warns that marginal cost works best with
it — applying it to one arm only would confound the route-choice model with the
assignment objective.

**Demand.** 15 O-D pairs × 30 vehicles = 450 trips; 394 loaded edges, **114
contended edges**, `testable: true`. 3 seeds, 10 800 s horizon, all runs
comparable (450 inserted, 0 waiting, 0 running at end), 0 collisions.

**Result.**

| Arm | mean time loss | vs DUE |
|---|---|---|
| R4 DUE | **58.20 s** | — |
| R5 DSO (marginal cost) | 58.38 s | −0.32% (within noise) |

**Two findings.**

1. **Official assignment beats hand-routed paths by ~6×.** E2's fixed-path
   routing produced ~358 s mean time loss; official `duaIterate` produces ~58 s
   on the same network. Our hand-built route sets were badly suboptimal, which
   retrospectively explains why "spreading" looked harmful in E2 — it was
   spreading traffic across *poor* paths. This is direct evidence for the
   official-implementation rule: the hand-made version was not a weaker variant
   of the real method, it was a different and much worse method.

2. **DUE ≈ DSO at this demand level.** Marginal-cost assignment can only help
   when links are congested enough that one driver's presence measurably slows
   others. At 450 trips the network is far from that regime (58 s loss on
   ~300 s trips). The DUE/DSO gap must be sought at higher demand — a demand
   escalation is running.

**Status.** R4 and R5 both EXECUTE through official SUMO code. Whether DSO
*beats* DUE on this network is not yet established and is not claimed.

### E3b · Demand escalation — the DUE/DSO crossover

Same official commands, 15 O-D pairs, 3 seeds each, demand varied.

| veh/pair | total trips | max edge load | R4 DUE | R5 DSO | DSO improvement |
|---|---|---|---|---|---|
| 30 | 450 | 150 | 58.20 s | 58.38 s | −0.32% |
| 60 | 900 | 300 | 104.27 s | 109.66 s | −5.17% |
| 120 | 1800 | 600 | 377.46 s | **290.73 s** | **+22.98%** |
| 200 | 3000 | 1000 | 703.82 s | **509.97 s** | **+27.54%** |

**Finding — the crossover is congestion-dependent, and that is the theory
working.** System-optimal assignment can only help when a vehicle's presence
measurably slows others: marginal cost exceeds average cost only under
congestion. Below ~900 trips the network is uncongested and DSO is neutral to
slightly worse (it imposes detours that buy nothing). Above ~1800 trips DSO
reduces total network delay by **23–28%**.

**Why this matters for the thesis.** It establishes `ROUTING_VALIDITY = VALID`:
routing *can* change network-wide outcomes on the real Dhaka R1 network, and the
size of the effect is a function of demand. It also sets the operating regime for
every later routing experiment — evaluating a routing method at 450 trips would
have shown "no effect" and wrongly rejected it.

**Not yet claimed.** 3 seeds is enough to see a 23–28% effect but not enough for
a confidence interval in a paper; the publication run needs ≥10 seeds with a
statistical test, and calibrated rather than structured-synthetic demand.

**Retrospect on E2.** E2's conclusion ("spreading is worse") was correct about
E2's own policy but is superseded as a statement about system-optimal routing:
that policy spread traffic over hand-built paths that were ~6× worse than
official assignment produces. E2 remains the recorded weak baseline (R2).

## E4 · DUE vs DSO statistical validation — 10 seeds (2026-08-15)

**Setup.** Official `duaIterate.py` per arm (identical commands ± `--marginal-cost`),
assignment converged once per arm, then **10 independent simulation seeds** per
arm per demand level. Metrics parsed from SUMO's own tripinfo/statistics.

| Level | trips | metric | DUE mean [95% CI] | DSO mean [95% CI] | improvement | Welch p | Cohen's d |
|---|---|---|---|---|---|---|---|
| v120 | 1800 | total delay (s) | 632,469 [563,912–701,027] | 491,968 [476,515–507,421] | **22.2%** | 1.1e-03 | 2.02 |
| v200 | 3000 | total delay (s) | 1,729,552 [1,627,522–1,831,582] | 1,391,764 [1,339,071–1,444,457] | **19.5%** | 1.3e-05 | 2.98 |
| v120 | 1800 | total travel time (s) | — | — | 12.6% | 1.5e-03 | 1.94 |
| v200 | 3000 | total travel time (s) | — | — | 14.1% | 8.1e-06 | 3.12 |

**Integrity (all seeds, both arms):** returncode 0, **0 collisions**, all demand
inserted AND completed (throughput identical: 1800/3000 per seed — the
comparison is fair by construction). Secondary finding: DSO reduces jam
teleports ~3× (449→148 at v120; 777→369 at v200).

**Disclosures.**
1. Teleports are non-zero (~2.5% of vehicle-runs at v120 under DUE). SUMO
   teleports remove jammed vehicles after 300 s, which truncates the worst
   delays — the measured DUE delay is therefore a *lower bound*, and the DSO
   improvement conservative.
2. queue/spillback: NOT_MEASURED in this harness (needs per-step lane
   observation; instrumented at the control gate).
3. Demand is structured-synthetic with verified contention, not calibrated
   Dhaka demand. The claim transfers to calibrated demand only after the twin
   gate.

**Final routing claim (supersedes E3b's 23–28% preliminary):** on the verified
Dhaka R1 network under structured synthetic demand at congested load, official
SUMO system-optimal assignment reduces total network delay by **19.5–22.2%**
versus user equilibrium (10 seeds/arm, Welch p < 0.002, Cohen's d 2.0–3.0).
ROUTING VALIDATION: **PASSED**. Routing subsystem now frozen until the joint
routing+control gate.
