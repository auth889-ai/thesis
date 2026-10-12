# core/simulation/ambulance — V2X ambulance alert and signal control (RQ3)

**RQ3:** does an alert sent ahead of an ambulance, or signal control, get it through Dhaka traffic faster than the
siren alone, and why? Runs on the Dhaka twin in SUMO with the corrected make-way rule (**v2**). Result folders keep
their earlier name (`results/emergency/dhaka/rq2/`), because evidence hashes point at them; in `docs/PAPER_MAP.md` this
question was RQ2 before renumbering.

## Papers and sources
| Source | Version | Licence | What we use |
|---|---|---|---|
| **SUMO-RL**: Alegre, "SUMO-RL", GitHub 2019. RESCO nets: Ault & Sharon, NeurIPS 2021 Datasets and Benchmarks | commit `86f0fc41401eeca724b2e8878f5020dc6d70c9b4` | MIT | `SumoEnvironment`, `QLAgent`, `EpsilonGreedy`, with their default observation, reward and timing |
| **adaptive-traffic-signal-rl**: Adityakumar1805 (no paper) | commit `b62436b5d5fb1e5d07008d6f486f1a06a09ff64a` | MIT | Its emergency override and signal safety state machine, copied into `core/simulation/signals/preemption/` |
| **Eclipse SUMO**: Lopez et al., IEEE ITSC 2018. Emergency vehicles and the sublane model | tag `v1_27_1` (`7717f2379d9e314a0c81c5cec748444de06a2a91`) | EPL-2.0 | The emergency vehicle type and `--lateral-resolution`. The bluelight device's side rule is written again by us. |
| **5GAA P-190033**; **ETSI EN 302 637-2/-3**; **tinyLTE** (IEEE VTC-Spring 2018); **Xu et al.**, J. Adv. Transportation 2017 | as in SOURCES.md | cited values only | Radio range, latency, message interval and loss for the V2X network model (`core/networking/v2x/`) |

All from `third_party/SOURCES.md`, sections "Ambulance alert, RQ2" and "Ambulance alert phase".

## Which file implements which part
| File | Part |
|---|---|
| `service.py` | One ambulance trip on a city's twin, with and without an alert. It reads `alert.makeway` (version, distance, keep strategic lane changes) from `configs/ambulance.yaml`. |
| `makeway.py` | Making way before SUMO's bluelight device would act. Alerted vehicles within `distance_m` ahead move to the side the device would choose. v2 keeps their route (strategic) lane changes. |
| `measures.py` | Why the alert helps or not, measured each step: the free width ahead, the queue at the route's signals, the share of alerted vehicles that moved, and time blocked. |
| `rl_signals.py` | The Q-learning signal arm: SUMO-RL's `QLAgent`, through an adapter that subclasses `SumoEnvironment` to call our ambulance hook after each step. |
| `corridor.py` | The Dhaka-density row: a corridor cut with `netconvert --keep-edges`, and demand from SUMO's `routeSampler.py` matched to DhaTraX counts. |
| `study.py` | RQ3 end to end: the density ladder, the arms, paired seeds, the Dhaka row, and the v2 re-run of every alerting arm (`rerun_v2`). |
| `summary.py` | Paired time saved against the siren-only run of the same seed and density: medians and IQR, the runs more than 5 s slower, correlations with 95 % CIs, old (v1) against new (v2), and the plain sentences. |
| `results.py` | The ambulance experiments' per-city table: every configuration against the no-alert baseline of the same seed, as a mean over seeds with its spread; seeds where SUMO crashed are counted beside the row. |
| `configs/` | `ambulance.yaml`: arms, densities and the make-way block. |

## Substitutions and why
- **Make-way v2 in place of v1.** v1 told every alerted vehicle up to 1 000 m ahead to stop strategic lane changes, which caused a circular wait (an artefact). v2 keeps strategic changes and limits moving aside to 100 m ahead, chosen by a rule fixed before the pilot (`evidence/ambulance_rq2/makeway_v2/choice.json`). The v1 results are kept, labelled, in `results/emergency/dhaka/rq2/record_v1_makeway_artefact/`.
- **Our side rule in place of SUMO's bluelight device**, because the device crashes SUMO 1.27.1 on the Dhaka network (`evidence/emergency/dhaka/sumo_bluelight_crash.json`).
- **Preemption learns of the ambulance when the alert is delivered**, not at the stop line (our change of meaning to the reused override).
- **Demand** on the density ladder is generated (randomTrips, not calibrated). Only the Dhaka row is matched to recorded DhaTraX counts.

## Reproduced first
- SUMO-RL's `experiments/ql_single-intersection.py`, unchanged, against `-fixed`. It publishes no number, so the check is the direction of its README figure (`evidence/ambulance_rq2/reproduce/`).
- adaptive-traffic-signal-rl's 36-run benchmark gave tables byte-identical to the shipped ones, and its 5 safety tests pass (`evidence/third_party/atsc_rl/`).

## Tests
| File | What it checks |
|---|---|
| `backend/tests/emergency/test_rq2.py` | The free-space and queue measures, the gridlock and frontier rules, and the correlation. |
| `backend/tests/emergency/test_ambulance.py` | Honest refusals, the device's own side rule, and which configurations may run. |
| `backend/tests/signals/test_preemption_adapter.py` | The reused state machine drives a junction only through phases of the junction's own programme. |

## Results
- Summary: `results/emergency/dhaka/rq2/summary.json` and `summary.md`. Evidence hashes: `evidence/ambulance_rq2/SHA256SUMS`.
- Its `findings.density` reads: "With every vehicle equipped, the alert's median saving is -0.5 s (-0.3 %) at demand x0.5; 0.5 s (0.2 %) at demand x1; 2.5 s (1.1 %) at demand x2; 3.5 s (1.2 %) at demand x3; -2.0 s (-0.5 %) at demand x4."
- Its `findings.stops` reads: "No equipped share reaches a median saving of 10 % at any density."
- Inspection of the Dhaka-density slowdown and of the Q-learning delay: `evidence/ambulance_rq2/inspect/dhaka/`.
