# Graduation map — labs → permanent platform

Rule: `paper reproduction → benchmark → Dhaka adaptation → KEEP decision →
adapter → dhakaflow/`. A lab's *numbers* never move into the platform; its
*validated capabilities* do, expressed as interfaces. Lab 00 and Lab 01 results
remain frozen and unedited (verified: `git diff` on their evidence is empty).

## Lab 00 — Traffic Science / UTD19 MFD → `dhakaflow/evaluation/`

**Status:** PASS (frozen). **Graduates to:** `evaluation/traffic_science.py`.

| Lab 00 concept (validated on real UTD19 data) | Platform expression |
|---|---|
| Flow, occupancy→density, speed `v = q/k` | `common/units.py`: `speed_from_flow_density`, `percent_to_fraction`, `flow_per_interval_to_vph` |
| MFD state (density vs flow), per-lane vs per-km² conventions | `MFDPoint(density, flow, units)` — mixing conventions in one diagram is blocked by the explicit `units` field |
| Critical point (n\*, P\*), critical speed v\* = P\*/n\* | `CriticalPoint.critical_speed`, `congestion_state()` |
| Edge-of-range maximum caveat (torino never entered deep congestion) | `CriticalPoint.interior_maximum` — a required honesty flag |
| "n\* ≤ ~⅓ jam density" physics check (Loder et al.) | `CriticalPoint.sanity_check_vs_jam()`; unknown jam density returns True (unavailable ≠ failed) |
| Calibrated vs uncalibrated analysis distinction | `CriticalPoint.calibrated` (False ⇒ UNCALIBRATED_ANALYSIS) |
| **Control relevance:** ideal control keeps n ≈ n\* | `distance_to_critical()` — the set-point signal for Labs 14–21 and a candidate reward term for Lab 20 |

**Cross-check (no Lab 00 number altered):** the platform formula reproduces Lab
00's frozen torino value — `CriticalPoint(31.9, 1104).critical_speed ≈ 34.6 km/h`
— asserted in `tests/platform/test_interfaces.py`.

**Not graduated:** the UTD19 dataset, the fitted torino parameters, and the
re-sampling/quantile-fit pipeline stay in `paper_labs/00_utd19/` and are cited,
never duplicated.

## Lab 01 — SUMO Foundation → `dhakaflow/simulation/`, `control/`, `safety/`, `evaluation/`

**Status:** PASS (frozen at `ca2ac81`). **Graduates to:** four modules.

| Lab 01 capability (validated in real Colab run) | Platform expression |
|---|---|
| SUMO lifecycle via TraCI, seeded and deterministic (15/15 clean runs) | `simulation/SimulationBackend` — `reset · step · close`, same scenario+seed ⇒ identical trajectory |
| Signal read/write surface (`getControlledLinks`, `setPhaseDuration`) | `simulation/SignalActuator` — separated from the backend so a shield can wrap only the write side |
| Scenario definition (net + routes + seed + duration) | `common/TrafficScenario`, incl. `warmup_s` and `evaluation_window_s` (Bologna §1.5 warm-up lesson) |
| Per-step observation (halting counts, queue ratio, running/arrived) | `common/TrafficObservation` + `LaneState` |
| Controller decisions (hold/extend/terminate) with rationale | `control/SignalAction`, `SignalActionType`, `TrafficController.act(obs, t, forecast=None)` |
| min-green / max-green / yellow preserved; 0 collisions, 0 teleports | `safety/SafetyConstraints` (defaults **are** Lab 01's 10 s/45 s/3 s) + `SafetyShield` |
| Transport metric set incl. proxy honesty (stops, spillback) | `common/TrafficMetrics` + `MetricsComputer.proxy_metric_names` |
| Fair multi-seed matrix (identical demand across arms) | `evaluation/BenchmarkSpec.assert_fair()` + `ArmSetup` |
| Upstream integrity discipline (pinned SHAs, no vendoring) | `common/RunProvenance.upstream_shas`; policy in `PLATFORM_ARCHITECTURE.md` |
| Evidence bundling + checksums | `common/provenance.py` (`sha256_file`, `git_sha`, `RunProvenance.to_json`) |

**Explicitly not graduated:** the max-pressure *algorithm* (it is a
`BASELINE_IMPLEMENTATION`, superseded by Lab 14's network-scale benchmark), the
unit scenario XMLs, and the frozen 5-seed numbers.

## Forward slots (empty by design)

`perception/` (Labs 04–06), `forecasting/` (07–12), `digital_twin/` (13),
`routing/` (22), `priority/` (23), `nlp/` (24), `genai/` (25) contain contracts
only. Nothing is implemented until its lab passes and a KEEP decision is
recorded.
