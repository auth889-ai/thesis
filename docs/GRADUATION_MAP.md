# Graduation map — labs → permanent platform

Rule: `paper reproduction → benchmark → Dhaka adaptation → KEEP decision →
adapter → dhakaflow/`. A lab's *numbers* never move into the platform; its
*validated capabilities* do, expressed as interfaces. Lab 00, Lab 01 and Lab 02
results remain frozen and unedited (verified 2026-08-14: `git diff HEAD` over
`paper_labs/00_utd19`, `01_sumo_foundation` and `02_dhaka_osm` is empty).

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
| **Control relevance (bounded):** Loder et al. note that maximising *travel production alone* would act near n ≈ n\* | `distance_to_critical()` — a **diagnostic**, offered to later labs only as an optional state feature / reward-shaping term / risk signal, to be justified by ablation. **Not a control target**: Labs 14–21 optimise travel time, waiting, queue, pressure, spillback, throughput, downstream capacity, person/pedestrian/emergency delay, forecast risk and safety. Forecast-Aware MAPPO (Lab 20) is never required to hold n ≈ n\* |

**Lab 00 regression fixture (no Lab 00 number altered):**
`test_lab00_torino_regression_fixture_is_not_a_dhaka_threshold` pins that the
platform's v\* = P\*/n\* arithmetic still reproduces the frozen torino estimate
(31.9 veh/km/lane, 1104 veh/h/lane → 34.6 km/h) together with its
`interior_maximum=False` and `calibrated=False` caveats. It verifies **frozen
Lab 00 behaviour only**. It is **not** a Dhaka operating threshold, control
target or calibration input — critical values are network-specific and torino's
must never be transferred into Dhaka control or calibration. Dhaka's own
critical behaviour is estimated from Dhaka data in Labs 06/13.

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
| min-green / max-green / yellow preserved; 0 collisions, 0 teleports | `safety/SafetyConstraints` (**no universal defaults** — every timing value comes from a named scenario profile) + `SafetyShield`. Lab 01's 10 s/45 s/3 s survive only as the explicitly named `LAB01_VALIDATED_REFERENCE_PROFILE`, tagged as synthetic-scenario values with no real-world jurisdiction; Dhaka profiles must come from Dhaka field/regulatory data |
| Transport metric set incl. proxy honesty (stops, spillback) | `common/TrafficMetrics` + `MetricsComputer.proxy_metric_names` |
| Fair multi-seed matrix (identical demand across arms) | `evaluation/BenchmarkSpec.assert_fair()` + `ArmSetup` |
| Upstream integrity discipline (pinned SHAs, no vendoring) | `common/RunProvenance.upstream_shas`; policy in `PLATFORM_ARCHITECTURE.md` |
| Evidence bundling + checksums | `common/provenance.py` (`sha256_file`, `git_sha`, `RunProvenance.to_json`) |

**Explicitly not graduated:** the max-pressure *algorithm* (it is a
`BASELINE_IMPLEMENTATION`, superseded by Lab 14's network-scale benchmark), the
unit scenario XMLs, and the frozen 5-seed numbers.

## Lab 02 — Real Dhaka Network (OSM → SUMO) → `dhakaflow/common/`, `simulation/`

**Status:** PASS — **FROZEN** (user approval 2026-08-14). Freeze baseline is two
commits: `SCIENTIFIC_EXECUTION_COMMIT = 6936ea9` (measured region selection,
dual-construction validation, live-reference foundation) and
`RESOURCE_TRACEABILITY_COMMIT = c852e64` (manifests + master resource index).
Lab 02 is not to be rerun, redesigned, extended or cosmetically modified unless
a future integration test reveals a genuine defect. **Graduates to:** the
scenario/observation contracts and the live-reference protocol.

Lab 02 is a *substrate* lab: its product is a geography, not an algorithm. So
what graduates is the **capability to express a validated real network through
the platform contracts** — never the network file itself, and never a number
measured on it.

| Lab 02 capability (validated on the real R1 snapshot) | Platform expression |
|---|---|
| A validated real network is a runnable scenario (net + demand + seed + horizon) | `common/TrafficScenario` — Lab 02's `build_scenario` emits `dhaka_R1_lab02_v2` with **no new type**; the Lab 01 contract absorbed a real 6 527-edge network unchanged |
| Provenance of a geographic artifact (source endpoint, download time, licence, checksum) | `common/provenance.py` (`sha256_file`, `RunProvenance`) — the OSM snapshot and `.net.xml` are pinned by sha256, so any later lab can prove *which* Dhaka it simulated |
| Honesty labels on inherited infrastructure | `TrafficScenario.metadata` string flags — `demand=SYNTHETIC_VALIDATION_DEMAND`, `traffic_side=left_hand`. Signal timings stay `IMPORTED_HEURISTIC`. Later labs must read these before claiming realism |
| Driving a real network through the Lab 01 lifecycle | `simulation/SimulationBackend` — `SumoDhakaBackend` (in the lab, structural conformance only) proved the contract holds outside the unit scenarios: `reset · step · close` on 3 001 trips, 0 collisions |
| Left-hand traffic as a checkable property, not an assumption | Verified two ways in-lab (declared `lefthand=true` + geometry over 5 250 opposite-carriageway pairs, 98.9%). Graduates as the `traffic_side` metadata key — **Bangladesh drives on the left, and every later scenario must carry this flag** |
| External ground truth without ingesting proprietary content | `common/live_reference.py`: `LiveTrafficReference` protocol, `LiveRouteRequest/Observation`, and `LiveRouteObservation.persistable_metadata()` — the type system makes "metadata and boolean verdicts only" enforceable rather than a promise. Status `READY_NOT_EXECUTED` (no key; user DECISION 1) |
| Dual-construction cross-validation as a method (independent Branch A/B, explained tolerance failures) | **Method, not code** — recorded in `DESIGN_V2.md §3`. Labs that build a second artifact from the same source reuse the rule: an explained deviation passes, an unexplained one fails |

**Explicitly not graduated:**

- `R1.osm` and `dhaka_r1.net.xml` — cited by checksum from
  `paper_labs/02_dhaka_osm/`, never copied into `dhakaflow/`.
- The **synthetic demand** (`randomTrips`/`duarouter`, seed 42) and every metric
  measured under it — mean travel time 266.7 s and mean speed 13.1 m/s are
  *toolchain-health evidence*, **not** Dhaka traffic conditions and not a
  calibration target. Lab 13 calibrates against real observations.
- The **netconvert-synthesised signal programs** (17 TLS across 19 traffic-light
  junctions). `IMPORTED_HEURISTIC` timings are a placeholder for Lab 13's real
  DMP/field plans; no RL lab may treat them as the operational baseline.
- The region-selection scoring (C1–C8) and `src/regions.py` candidates — a
  one-time decision procedure, frozen as evidence in `REGION_SELECTION.md`.
- `SumoDhakaBackend` itself stays in the lab: it is a *conformance
  demonstration*. A production backend belongs in `simulation/` only after a lab
  needs it under a KEEP decision.

**Carried-forward obligations** (limitations that later labs inherit): OSM
attribute completeness on R1 is lanes 22.1%, maxspeed 12.8%, name 45.2% — this
is the measured field-survey burden any calibration must close.

## Forward slots (empty by design)

`perception/` (Labs 04–06), `forecasting/` (07–12), `digital_twin/` (13),
`routing/` (22), `priority/` (23), `pipeline/nlp/` (24), `genai/` (25) contain contracts
only. Nothing is implemented until its lab passes and a KEEP decision is
recorded.
