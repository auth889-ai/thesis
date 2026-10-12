# core/networking — V2X messages, offline mesh, weak-signal prefetch

The networking research: the V2X network model the ambulance alert travels on (part of **RQ3**), phone-to-phone delivery
with no network (**RQ4**), and prefetching a trip before a weak-signal stretch (**RQ5**). Everything here is
SIMULATED or an emulated network, and every result says so.

## Papers
- **RQ4, offline mesh:** the routers as implemented in PONS: Epidemic, Spray and Wait, PRoPHET. Radio range from Keränen, Ott,
  Kärkkäinen, "The ONE Simulator for DTN Protocol Evaluation", SIMUTools 2009.
- **RQ5, weak signal:**
  - main references: Schulman, Navda, Ramjee, Spring, "Bartendr: A Practical Approach to Energy-aware Cellular Data
    Scheduling", ACM MobiCom 2010; Nicholson, Noble, "BreadCrumbs: Forecasting Mobile Connectivity", ACM MobiCom 2008;
  - secondary: Borkowski et al., "Prediction-Based Prefetch Scheduling in Mobile Service Applications", IEEE MS 2016.
- **V2X network model:** 5GAA P-190033 (test report); ETSI EN 302 637-2 / -3 (CAM, DENM); Eckermann et al., "tinyLTE",
  IEEE VTC-Spring 2018; Xu et al., "DSRC versus 4G-LTE for Connected Vehicle Applications", J. Adv. Transportation 2017.

## Official repositories, versions, licences
From `third_party/SOURCES.md`, sections "Offline mesh", "Works with weak signal" and "Ambulance alert phase".

| Source | Version | Licence |
|---|---|---|
| PONS (`pons-dtn`) | `0.2.1` = commit `2fd70381b1b02e3e2227b5e596dc7fd92f458893` | MIT |
| The ONE simulator, `default_settings.txt` | commit `43eaab1e0592af2526d124ee9ba9590eeadcd49a` | GPLv3; one value cited, no code copied |
| SUMO `traceExporter.py`, `randomTrips.py` | tag `v1_27_1` | EPL-2.0 |
| Bartendr, BreadCrumbs | papers (PDF sha256 in SOURCES.md) | © ACM; method only, nothing copied |
| 5GAA, ETSI, tinyLTE, Xu et al. | PDF sha256 in SOURCES.md | values cited only (Xu et al.: CC BY) |
| Eclipse MOSAIC (`mosaic/`) | not recorded in third_party/SOURCES.md (pinned in `upstream/UPSTREAM_PINS.yaml`) | not recorded in third_party/SOURCES.md |

## Which file implements which part
| File | Part |
|---|---|
| `v2x/model.py` | The network model: inside a technology's range a message arrives with the source's delivery ratio, after the source's mean delay times the number of radio legs; beyond range it does not. Every parameter is sourced in `v2x/configs/network_model.yaml`; a parameter without a source makes the technology refuse by name. |
| `v2x/channel.py` | A deterministic simulated message channel between SUMO vehicles and the controller: latency, loss, TTL. |
| `v2x/v2x_bus.py`, `v2x/observed_costs.py`, `v2x/state_correction.py` | Control messages for the closed-loop routing study (RQ2); fusing received observations into forecast edge costs; online state correction. |
| `v2x/energy.py` | Estimated radio energy of a trip pack after Bartendr's Palm Pre measurements, and its dynamic-programming schedule (a Python mirror of `frontend/src/lib/schedule.ts`). |
| `mesh/results.py` | The offline mesh table of a city: PONS's statistics per router, a mean over seeds with its spread, and the plain line. |
| `prefetch/results.py` | The weak-signal experiment's results: the browser rows from run files and the energy rows on the real route. |
| `mosaic/` | An Eclipse MOSAIC penetration-rate sweep, event advisories and latency injection on the Dhaka R1 scenario (earlier V2X work). |

The mesh runs themselves are in `research/mesh_pons/scripts/` (`03_run_pons.py`, `04_report.py`). The browser half of RQ5 is in `frontend/src/lib/` (`breadcrumbs.ts`, `schedule.ts`) and `frontend/tests/weak_signal.experiment.cjs`.

## Substitutions and why
- **PONS is used unchanged, with two adapters of ours around it**, each justified by a saved failure:
  - `read_ns2` turns SUMO's ns-2 trace into PONS move tuples, because PONS's reader divides by a stopped vehicle's zero speed;
  - `generator_with_metadata`, because `SprayAndWaitRouter` writes into metadata that PONS's generator passes as `None`.
- **Radio range of 10 m** (the ONE's Bluetooth default), not a Dhaka measurement.
- **Bartendr's energy figures are a labelled estimate:** "estimated from Bartendr's Palm Pre measurements, not measured on our phones".
- **BreadCrumbs' model stays in the browser.** Our version is used for a saved trip only after 5 completed trips (our reading of "one week").
- **The network model has no fading, no interference and no load.** The 4G delivery ratio (0.96) is one 2017 field study in Xi'an, not Dhaka.

## Tests
| File | What it checks |
|---|---|
| `backend/tests/networking/test_network_model.py` | Sourced parameters only, deterministic, honest about range. |
| `backend/tests/rebuild/test_v2x_channel.py` | Deterministic; latency delays delivery; loss drops messages; TTL expires. |
| `backend/tests/rebuild/test_state_correction.py` | Time-dependent costing, the incident detector and the residual correction. |
| `backend/tests/networking/test_energy.py` | The Python schedule gives the same plan and energy as the TypeScript one, and the optimum. |
| `backend/tests/networking/test_prefetch_results.py` | Browser rows from run files; plain numbers from the same rows; energy rows on the real route. |
| `backend/tests/mesh/test_mesh_results.py` | The report's formulas, honest refusals, per-city tables and the feed line. |
| `backend/tests/routing/test_signal.py` | Track-based signal prediction after Bartendr (`core/simulation/routing/signal.py`): 100 m steps with heading, and heading-matched history. |

## Results
- **RQ4:** `evidence/mesh/dhaka/results.json` (label SIMULATED; Dhaka twin, synthetic uncalibrated demand, 17 vehicles simulated, 10 m radio). Report: `research/mesh_pons/RESULTS.md`.
- **RQ5:** `evidence/prefetch/summary.json` (label SIMULATED, an emulated network) with `summary.sha256` and the run logs in `evidence/prefetch/`.
- **V2X model for RQ3:** see `core/simulation/ambulance/README.md`. MOSAIC sweep outputs: `results/networking/`.
