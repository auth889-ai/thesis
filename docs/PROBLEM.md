# The problem, frozen (Phase 0)

Frozen on 2026-09-30. No code in this phase. Everything after this document is measured against it.

## The product promise

**Make my day actually work.**

A person's calendar, tasks, places, roads, transit, weather, deadlines and the changing real world live in separate
apps. Each app is right on its own, and the day as a whole can still be impossible. Calendar knows events. Maps know
routes. A task app knows work. Weather knows rain. LIFE OS asks the one question none of them ask:

> Taken together, is this day actually possible?

## One engine, one problem

```
                    LIFE OS          "What do I need to accomplish?"
                       │
                   LIFE TWIN         "What does my day require?"
                       │
                  ACCESS TWIN        "Can I reliably reach it?"
          ┌────────────┼────────────┐
       Traffic       Transit     Constraints (weather, disruption, accessibility, cost, time)
          └────────────┼────────────┘
              REACHABILITY MODEL
                       │
               FEASIBLE PLAN  →  MONITOR  →  change?  →  REPAIR  →  updated plan
```

| Layer | Its only job |
|---|---|
| **LIFE OS** | turn knowledge into action: read the day, propose, ask before consequential actions, remember, audit |
| **Life Twin** | the day as a structure: commitments, tasks, deadlines, places, free windows, dependencies, the person's constraints |
| **AccessTwin** | the decision: can this person reliably reach this commitment before its deadline, by which mode, leaving when |
| **TrafficTwin** | the prediction: current traffic → future traffic → uncertainty. Nothing else. |

Interview, hospital, school, job, errand, emergency are **use cases and evaluation domains**, never separate products.
Dispatcher, city operator and developer are not separate faces. The reachability engine is shown to a person, and any
partner reaches the same engine through the same interface.

## The three entities

```
Person
  id · name · timezone · home · places · mobility profile (max walk, wheelchair, avoid stairs, elevator) · on-time target · calibration (measured, from outcomes)

Commitment
  id · title · location · start · deadline (the latest acceptable arrival) · duration · priority (must / should / could) · flexibility (fixed / movable within a window / any time before a deadline) · source (calendar, task, the person, the agent)

Travel Edge
  from · to · mode (car, transit, walk, cycle, mixed) · departure · travel time (expected) · uncertainty (an interval and a distribution when one exists) · cost · accessibility (fits the person's profile or not) · source (which provider, which model, live or typical or recorded)
```

Example day:

```
Eva
Home ──travel──▶ Class 09:00 ──travel──▶ Hospital 13:00 ──travel──▶ Interview 16:00 ──travel──▶ Assignment due 18:00 (anywhere)
```

## Exit condition of Phase 0

The system can answer one question about one day, from these three entities alone:

```
Is today's plan feasible?    YES  /  RISKY  /  NO
```

with the first failing edge named. Nothing more.

## The research question and the hypothesis

**Question.** Can uncertainty-aware predictive mobility improve reliable access to time-critical commitments?

**Hypothesis.** Better traffic prediction → better travel-time uncertainty → better reachability decisions → more
commitments completed on time. The thesis proves or disproves that prediction accuracy changes the person's actual
outcome, not only a forecasting error.

**Title candidates.**
1. *AccessTwin: Uncertainty-Aware Multimodal Reachability and Closed-Loop Replanning for Time-Critical Urban Commitments*
2. *AccessTwin: Reliable Multimodal Reachability under Sparse Sensing, Uncertainty, and Urban Disruptions*

## The metrics that count

Forecast metrics (MAE, RMSE, MAPE) are reported but are not the thesis metrics. The thesis metrics are about people:

| Metric | Definition |
|---|---|
| **Access Success Rate** | commitments reached on time ÷ all required commitments |
| **Access Regret** | how much worse the chosen plan was than the hindsight-optimal plan |
| **Buffer Waste** | how unnecessarily early the person arrived |
| **Recovery Rate** | disrupted plans successfully repaired ÷ disrupted plans |
| **Opportunity Reachability** | jobs, hospitals, schools, services reliably reachable within X minutes |

## What others built, and what is taken from each

| Need | Who built it | What they did | What we take |
|---|---|---|---|
| Reachability and isochrones | [Conveyal R5](https://conveyal.com/learn), [r5py](https://sustainability-gis.readthedocs.io/en/2023/lessons/L2/r5py_calculating_travel_time_matrices.html), [r5r](https://ipeagit.github.io/r5r/), [OpenTripPlanner analysis](https://docs.opentripplanner.org/en/latest/Analysis/) | multimodal travel-time matrices, cumulative-opportunity accessibility, isochrones; travel time as a **percentile over a departure window**, not a point | R5 or OTP as the multimodal routing and reachability engine (dependency, not rewritten); percentile accessibility is the definition behind Opportunity Reachability and the Explore page |
| Reliable path and latest departure | [SPOTAR literature](https://arxiv.org/html/1804.07829v2), [on-time arrival probability](https://www.sciencedirect.com/science/article/abs/pii/S0191261509000174), [reliable shortest path with correlations](https://www.sciencedirect.com/science/article/abs/pii/S0191261518302959) | maximise the probability of arriving within a budget; path-centric joint distributions; best departure and path together in stochastic time-dependent networks | the formal definition of AccessTwin's answer: P(arrive before deadline) per mode and departure, and the latest departure meeting the person's target |
| Quantile travel time with calibration | [Namma Commute](https://github.com/harsharajkumar-273/namma-commute-) | quantile gradient-boosted trees for 10/50/90 percentile drive time per horizon; conformal calibration per horizon; latest safe departure from the calendar; door-to-door offset from real trips | the design of the uncertainty phase, as an adapter |
| Whole-day solver | [OR-Tools CP-SAT](https://github.com/giangstrider/scheduling-optimization-ortools), [Timefold](https://solver.timefold.ai/) (Apache-2.0) | constraint programming for time windows, precedence, flexible tasks | the deterministic day optimiser: fixed events, flexible tasks, deadlines and uncertain travel edges as constraints; no LLM guessing |
| Travel buffers that move with events | [Reclaim.ai](https://help.reclaim.ai/en/articles/4281992-travel-time-decompression-time-and-tasks-habit-breaks) | travel time scheduled around located events and re-scheduled when the event moves | the buffer as a first-class block in the Life Twin |
| Population-level evaluation | [MATSim](https://matsim.org/), [synthetic populations](https://github.com/matsim-scenarios/matsim-ile-de-france) | thousands of agents with activity schedules adapting mode, route and time | the city-wide question: does predictive access planning raise opportunity accessibility for a population, not one Eva |
| Agent safety | tahodev/openmuse, openai-agents-python (studied in the earlier Phase 1) | exact-action approval, standing decisions, verifiable audit | already in LIFE OS; the agent calls a mature AccessTwin instead of prompting |

## What exists today against this frame

Kept: the profile (person), calendar and tasks (commitments), the commute planner and live routing (travel edges with
an empirical probability where recorded corridor data exists), feasibility grades and conflicts (a first YES / RISKY / NO),
the monitor, outcomes and calibration, the agent with approvals and audit, the SUMO twin and the V2X channel, the
forecasting harness, the consumer pages. Reframed: the departure probability is only real where corridor history exists
and must become a calibrated interval in any city (Phase 5–6); the pages become Today · Plan · Agent · Explore · Activity · You (Phase 23).
