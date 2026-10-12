# Strength audit, 2026-10-10 (read-only; nothing in the code or results was changed)

Ten features scored PASS / WEAK / MISSING on six points. Evidence is file:line or a command's output. Three read-only passes over the
code gathered it; the claims marked ✔ were re-checked by hand. Reference standards: SUMO's TraCI and device.rerouting, sumo-rl, Flow,
RESCO, BasicTS, the Veins examples.

- **a. Upstream reuse:** upstream code is vendored or used unmodified, and extended by a subclass or wrapper (diffed against the pin).
- **b. Closed loop:** an ML model or protocol decides inside the running simulation, and the traffic or network changes as a result.
- **c. GUI:** the effect is visible in a GUI (sumo-gui, Qtenv or the web app).
- **d. Comparison:** baselines, several seeds, and at least one sweep.
- **e. Finding:** a finding explained from the model or the data.
- **f. Scripts and README:** run scripts and a README for that feature.

## Table

| Feature | a. Upstream reuse | b. Closed loop | c. GUI | d. Comparison | e. Finding | f. Scripts and README |
|---|---|---|---|---|---|---|
| Ambulance V2X alert | PASS | PASS | PASS | PASS | PASS | PASS |
| Crash SOS car-to-car | WEAK | PASS | PASS | WEAK | MISSING | WEAK |
| Smart signals (sumo-rl) | PASS | PASS | WEAK | PASS | PASS | WEAK |
| Forecasting and Model Lab | WEAK | WEAK | PASS | PASS | PASS | PASS |
| Phone mesh (PONS, The ONE) | PASS | WEAK | PASS | PASS | PASS | PASS |
| Live digital twin | PASS | WEAK | PASS | WEAK | PASS | WEAK |
| Weak-signal prefetch | WEAK | WEAK | PASS | PASS | WEAK | WEAK |
| Crash detection (phone) | WEAK | PASS | PASS | WEAK | WEAK | PASS |
| Hospital reach | PASS | WEAK | PASS | WEAK | MISSING | WEAK |
| Map app navigation | WEAK | WEAK | PASS | MISSING | WEAK | WEAK |

## Upstream code: where it lives and whether it is unmodified

| Upstream | Where | Pin | Licence | Unmodified? |
|---|---|---|---|---|
| sumo-rl | `~/.dhakaflow/upstream/sumo-rl` | `86f0fc41…` = HEAD; also checked at run time (`core/simulation/ambulance/rl_signals.py:31-34`) | MIT | **Yes.** `git status` and `diff <pin>` are empty. Extended by the subclass `AmbulanceEnv(SumoEnvironment)` (`rl_signals.py:69-74`). |
| adaptive-traffic-signal-rl (2 files) | copied into `core/simulation/signals/preemption/{emergency,phases}.py` | `b62436b5…` | MIT | **Yes, apart from a 4-line header and one import line each.** sha256 matches `third_party/SOURCES.md:163`. Wrapped by `sumo_adapter.py`. |
| Veins 5.3.1 | `~/.dhakaflow/upstream/veins` | `6571085f…` | GPL-2.0+ | **Yes.** Clean checkout. Extended by the subclass `AmbulanceAlert11p : DemoBaseApplLayer` (`research/veins_dhaka/src/AmbulanceAlert11p.h:6`). |
| OMNeT++ 6.2.0 | release tgz | sha256 checked | Academic Public | Only build flags in `configure.user` (`SOURCES.md:194`); not a git checkout. |
| SUMO 1.27.1 | pip / `~/.dhakaflow/upstream/sumo` | `7717f237…` | EPL-2.0 | **Yes.** |
| sumo-web3d | tarball, sha256 `2423dda8…` | `d89fe801…` | EPL-2.0 | **Yes.** `deltas.py` is copied with 2 comment lines added. |
| BasicTS (legacy) | `~/.dhakaflow/upstream/BasicTS_legacy` | `4c3e2d37…` = HEAD | Apache-2.0 | **Yes, no tracked change.** 29 untracked items are our own `DF_user*` configs. |
| **OpenCity** | `~/.dhakaflow/upstream/OpenCity` | `eca64c9d…` = HEAD | MIT | **No ✔.** `conf/general_conf/pretrain.conf`: `dataset_use = ['PEMS07M']` changed to `['DF_METR_LA_R5']` (`git diff`). This contradicts "no source line edited" in `core/ml/forecasting/README.md`. `UPSTREAM_PINS.yaml:324` still says `PINNED_NOT_FETCHED`. |
| Chronos / River | pip 2.3.1 / 0.26.1 | revisions as in `SOURCES.md` | Apache-2.0 / BSD-3 | **Yes** (used as released). |
| PONS 0.2.1 | `research/mesh_pons/upstream/PONS` | `2fd70381…` | MIT | **Yes.** The `.venv` copy is identical to the tag. Two wrappers of ours. |
| The ONE 1.6.0 | `~/.dhakaflow/upstream/the-one` | `42b6e20f…` | GPL-3.0 | **Yes, no tracked change.** 192 build `.class` files. Not listed in `UPSTREAM_PINS.yaml`. |
| Headway www-app | `frontend/map/` (a fork, no reference checkout) | `d0b994e5…` | Apache-2.0 | **No: edited in place.** 13 upstream files carry "TrafficTwin change" (`SOURCES.md:99` says 9). Four more are newer than the saved patch. `evidence/design/headway_reproduce/traffictwin_changes.patch` is stale. Not listed in `UPSTREAM_PINS.yaml`. |
| travelmux, Valhalla, Ferrostar | docker digest / image tag 3.9.0 / npm 0.57.0 | see `SOURCES.md` | Apache-2.0 OR MIT / MIT / BSD-3 | **Yes.** Valhalla is pinned by tag, not digest. `UPSTREAM_PINS.yaml:406-413` (`685e3d8`) conflicts with `SOURCES.md:184`. |
| WreckWatch, Bartendr, BreadCrumbs | papers only | PDF sha256 in `SOURCES.md` | © publishers | No code exists; we reimplemented them. |

**Note:** almost all feature code, results and evidence are **untracked** in git (`core/`, `frontend/map/`, `scripts/live/`, `research/*`,
`results/*`, `evidence/*`, `third_party/`). By the owner's rule nothing is committed until the end. Until then, these files exist only on
this laptop and in the Drive archives.

## Evidence per feature

### Ambulance V2X alert: all PASS
- **a.** SUMO, the 2 ATSC files and the Veins subclass, as in the upstream table.
- **b.**
  - The V2X model decides delivery: `core/simulation/ambulance/service.py:209-213` calls `core/networking/v2x/model.py:75-86`.
  - Delivered alerts are applied through TraCI: `service.py:188` → `makeway.py:39-42`.
  - Signals are preempted: `service.py:204-206` → `sumo_adapter.py:140-141`.
- **c.**
  - sumo-gui: the radio ring and orange cars making way (`scripts/live/run_v2x.py:97,109`).
  - Web: `core/simulation/live_jobs/jobs.py:103` → `frontend/map/src/traffictwin/ttSim.ts:23-26`, with screenshots in `evidence/live_web/v2x_*`.
  - No sumo-gui or Qtenv screenshot is saved.
- **d.**
  - Arms `no_alert` / `alert` / `alert_preemption`, 3 radio technologies, equipped shares 0–1, seeds 11–15.
  - Density sweep ×0.5–×4: 684 runs, 600 of them paired (`results/emergency/dhaka/rq2/summary.json:6-80,872`).
- **e.** The saving falls with free road width (rho −0.16) and rises with the queue at signals (`summary.json:877-882`). The make-way v1 artefact is explained in `evidence/ambulance_rq2/inspect/dhaka/SLOWDOWN.md`.
- **f.** `make run-v2x`, `make demo-ambulance`; `core/simulation/ambulance/README.md`.

### Crash SOS car-to-car
- **a. WEAK.**
  - The thesis path is our own code imitating TraCIDemo11p (`run_sos_v2v.py:106-135`), not a subclass.
  - Only the `--veins` view runs Veins' TraCIDemo11p unchanged.
- **b. PASS.** `model.deliver` decides each delivery (`run_sos_v2v.py:119`), and warned cars reroute through `setAdaptedTraveltime` + `rerouteTraveltime` (`:128-129`). This is a protocol, not an ML model.
- **c. PASS.** sumo-gui colours (`:94,125,135`) and the web map (`jobs.py:158`); screenshots in `evidence/live_web/sos_*`.
- **d. WEAK.**
  - The baseline is the same seed without the warning.
  - Only one saved run exists (seed 11, 50 % equipped; `evidence/live_runs/sos_v2v/runs/`).
  - No seeds or sweep.
- **e. MISSING.** `last_run.json`: 1 car rerouted; affected cars 212.4 s against 212.5 s; 9 948 of 10 244 messages out of range. Nothing explains these numbers.
- **f. WEAK.** `make run-sos-v2v`, `docs/LIVE_RUNS.md:38-43`, but no feature README.

### Smart signals (sumo-rl)
- **a. PASS.**
  - sumo-rl unchanged, with the subclass (`rl_signals.py:23-40,69-74`).
  - Its own example was reproduced first (`evidence/ambulance_rq2/reproduce/SUMMARY.json`).
- **b. PASS.**
  - The agents act inside SUMO: `rl_signals.py:164` → upstream `env.py:335-339` → `traffic_signal.py:176,193`.
  - The Q-tables are trained beforehand and frozen during evaluation (alpha 0, epsilon 0; `rl_signals.py:157-160`), as RESCO-style evaluation does.
- **c. WEAK.**
  - sumo-gui shows the lights natively; our code only adds a halting-count label (`run_signals.py:81`).
  - The web map draws no signal state (`ttSim.ts` has no signals branch); `TtSimulation.vue:35-36` shows counts only.
- **d. PASS.**
  - Fixed-time baseline.
  - Scale sweep ×0.5–×4 with 10 seeds each (`summary.json:637`).
  - Training seeds are separate from evaluation seeds (`rl_signals.py:27`).
- **e. PASS.**
  - Slower runs are explained (`summary.json:884`; `evidence/ambulance_rq2/inspect/dhaka/QLEARNING.md`).
  - The vehicle-hours cost (794 against 532) is stated but not explained.
- **f. WEAK.** `make run-signals`; only one row in `core/simulation/ambulance/README.md:24`.

### Forecasting and Model Lab
- **a. WEAK.**
  - BasicTS, Chronos and River are unmodified.
  - **OpenCity has one edited config line ✔**, which the README denies.
- **b. WEAK.**
  - The Model Lab is open loop (`core/ml/forecasting/layer/lab.py:62-99`), and the map's forecast layer replays saved files (`layer/service.py:1-8`).
  - A real closed loop exists only in RQ2's Los Angeles twin: `routing_forecast.py:60-84` → `routing/controller.py:55-112` → `twin/runner.py:224-236` applies the reroutes through TraCI. It was inconclusive against reactive rerouting (`docs/PAPER_MAP.md:157-170`) and was not run in Dhaka.
- **c. PASS.** The Model Lab computes on Run (`ModelLabPage.tsx:23-30`); screenshots in `evidence/live_runs/model_lab/`, `evidence/forecast_layer/`.
- **d. PASS.**
  - Seeds 11/23/37.
  - Persistence and historical-average baselines.
  - Sweeps over horizon (15/30/60) and city (`results/forecasting/rq1/summary.md:11-31`).
- **e. PASS.** Dhaka's speeds jump by more than 30 % of free-flow in 6.5–13.1 % of 5-minute steps, so XGBoost is 72.7 % worse than persistence at 60 min (`docs/PAPER_MAP.md:114`).
- **f. PASS.** `make run-forecast`, `research/forecasting_rq1/scripts/`, two READMEs. `run-forecast` REPRODUCED with a largest difference of 0.

### Phone mesh (PONS, The ONE)
- **a. PASS.** PONS is identical to tag 0.2.1; The ONE has no tracked change.
- **b. WEAK.**
  - The routers decide inside PONS (`scripts/live/run_mesh.py:41-55`) and The ONE (`run_mesh_one.py:105-106`).
  - Movement is a fixed SUMO trace, and alerts never feed back into the traffic.
- **c. PASS.**
  - The live window plus web frames (`mesh_frames.py`, `ttSim.ts:32`); screenshots in `evidence/live_web/mesh_*`.
  - No screenshot of The ONE's GUI.
- **d. PASS.** 3 routers × seeds 1–5; a phones sweep (4/8/12/17); range 10 against 30 m.
- **e. PASS.** PRoPHET never forwards, so its delivery equals direct contact (`research/mesh_pons/RESULTS.md:59-65`).
- **f. PASS.** `make run-mesh`, `make demo-mesh`, READMEs.

### Live digital twin
- **a. PASS.** The sumo-web3d delta file is unchanged, and River, deck.gl and uPlot are used as released, each reproduced first (`evidence/live_twin/upstream/`).
- **b. WEAK.**
  - The forecasters only predict and are scored (`core/simulation/live_twin/session.py:239-243`); nothing feeds back into SUMO.
  - The in-simulation decisions are the ambulance protocol (`session.py:401-423`) and the viewer's commands.
  - The title "ML in the loop" (`docs/EXPLAIN.md:6`) overstates this.
- **c. PASS.** `frontend/src/features/livetwin/liveTwin.ts:19-23`, `LiveTwinPage.tsx:54-65`; screenshots in `evidence/live_twin/`.
- **d. WEAK.** One learning run (one seed); 20 seeds for the crash check only; no sweep.
- **e. PASS.** The online model equals "no change" at first and is slightly below it after about two simulated hours; Chronos is lowest; said as one run (`docs/EXPLAIN.md:53-58`).
- **f. WEAK.** `scripts/live_twin/*.py` and `docs/EXPLAIN.md`, but no Makefile target and no feature README.

### Weak-signal prefetch
- **a. WEAK.** Bartendr and BreadCrumbs are papers only and reimplemented (`frontend/src/lib/schedule.ts`, `breadcrumbs.ts`). Workbox is used unchanged.
- **b. WEAK.**
  - During navigation the app saves along the drive by Bartendr's schedule (`useAlongTheDrive.ts:8-9`).
  - The browser experiment compares only with and without the pack.
- **c. PASS.** `evidence/prefetch/*.jpg`, `evidence/live_runs/offline/`.
- **d. PASS.**
  - 4 network conditions × 2 arms × 3 runs.
  - Energy estimate: seeds 1–3 × weak share 0.1/0.3/0.5.
- **e. WEAK ✔.** In all 9 energy rows Bartendr's schedule equals "download now" (35.1 J, one burst; `results/networking/prefetch/summary.json` `energy.rows`). So the 43–73 % saving comes from **prefetching on a good signal, not from the scheduling**, but `README.md:100` and `PAPER_MAP.md:469` credit the scheduling. The energy is estimated from the paper's numbers, not measured.
- **f. WEAK.** No Makefile target for the experiment or `core.networking.prefetch.results`, and no feature README.

### Crash detection (phone)
- **a. WEAK.** WreckWatch is a paper only; the rule is our own (`core/safety/sos.py:25-26`, `frontend/src/features/emergency/sos.ts`).
- **b. PASS, TEST mode.** Motion → rule → countdown → TEST alert (`useMotion.ts:28-34` → `SosCard.tsx:36-38`; map app `tt.ts:105-141`). Nothing is ever sent.
- **c. PASS.** `MotionGraph.tsx`; screenshots in `evidence/sos/`, `evidence/live_runs/sos_graph/`.
- **d. WEAK.** One threshold (4.0 g), three synthetic traces from one seed; no threshold sweep and no baseline detector.
- **e. WEAK.** "Only the crash passes 4 g" is circular: the traces were built on either side of 4 g (`sos.py:33`).
- **f. PASS.** `make run-sos-v2v`, `core/safety/README.md`, `docs/LIVE_RUNS.md`.

**Bugs found:**
- **Wrong peak ✔.** `detect()` reports the first sample over the threshold as `peak_g`: the hit's value overwrites the trace peak (`core/safety/sos.py:54`). For `crash_jolt` it says **5.87 g; the true peak is 6.37 g at 12.06 s**. Detection and its time are unchanged, but the "Peak, g" column in `PAPER_MAP.md:502` and `README.md:114` is wrong. The TypeScript `detect` reports the true peak, so the two disagree.
- **Stale hashes ✔.** `research/sos/traces/SHA256SUMS` lists `03ce7b94…` for `crash_jolt.json`, but the file is `7d0d9fc6…`; the traces were rewritten on 9 October. The same stale hashes appear in `evidence/sos/traces.SHA256SUMS` and `results.json`.
- **Button sent as sensor.** The map app sends `source: 'sensor'` even when the SOS button is pressed (`frontend/map/src/traffictwin/tt.ts:137`), so a button press is labelled as coming from the motion sensor, with a peak of 0 g.

### Hospital reach
- **a. PASS.** Valhalla 3.9.0 unchanged, through our HTTP client (`core/simulation/routing/valhalla.py:141,156`). Pinned by tag, not digest.
- **b. WEAK.** The reach table is a saved build (`backend/app/emergency/router.py:47-51`). Only "nearest hospitals" and the isochrone are computed live. No model decides anything.
- **c. PASS.**
  - `ReachCard.tsx`, `ReachMap.tsx`; screenshots in `evidence/reach/dhaka/`.
  - The map app shows no isochrones.
- **d. WEAK.** Baseline: map speeds against recorded speeds. One hour (08:30), one grid (500 m), one profile; deterministic, so no seeds.
- **e. MISSING.** The shares stay 9.7 / 27.7 / 45.9 % although about 7 000 points changed per site (`results/reach/dhaka/summary.json`). Not explained; `README.md:134` says "Not analysed".
- **f. WEAK.** Only `python -m core.safety.reach build`; no Makefile target and no feature README.

### Map app navigation
- **a. WEAK.**
  - Headway is edited in place (13 marked files; the patch is stale; no reference checkout).
  - travelmux, Valhalla and Ferrostar are used unchanged.
- **b. WEAK.**
  - Ferrostar recalculates when off route, and the crash detector is armed during a trip.
  - Routing uses no live or forecast speeds (`backend/app/routing/router.py:217-239`; `valhalla.py:236-239`).
- **c. PASS.** QA matrix M1–M13: 48 pass, 0 fail, 6 not applicable (`evidence/qa/mapflow/2026-10-10T04-19-52-795Z.md`). `evidence/navigation/*.png`.
- **d. MISSING.** QA pass/fail only; no baseline, seeds or sweep.
- **e. WEAK.** Engineering observations only, for example Valhalla answering Bangla requests in English.
- **f. WEAK.** No Makefile target for the map app or `mapflow.cjs`; `frontend/map/README.md` is Headway's own.

## Fixes, smallest first, ranked by impact ÷ (hours × risk)

Impact is how visible the fix is to the supervisor (1–3). Risk is the chance of breaking `make present`: low ×1, medium ×2, high ×3. Rows
marked **(result)** change a reported number or claim and need the owner's yes first ("do not change existing results").

| # | Fix | Points fixed | Impact | Time | Risk | Score |
|---|---|---|---|---|---|---|
| 1 | Reword the live twin title: "forecasters run live beside the simulation; they do not steer it yet" (`docs/EXPLAIN.md:6`, page intro) | twin b (honesty) | 2 | 0.1 h | low | 20 |
| 2 | **(result)** Prefetch: credit the saving to prefetching, not scheduling; say Bartendr's schedule equals "download now" in all 9 rows (`scripts/readme/build.py`, `PAPER_MAP.md:469`) | prefetch e | 3 | 0.25 h | low | 12 |
| 3 | Record the OpenCity config edit truthfully (`core/ml/forecasting/README.md`, SOURCES); set PINS status to fetched | forecasting a | 2 | 0.25 h | low | 8 |
| 4 | Map app SOS: send `source: 'button'` for a button press (`tt.ts:137`) | crash detection b | 1 | 0.25 h | low | 4 |
| 5 | **(result)** `sos.py:54`: report the true peak (6.37 g); rebuild `results.json` and refresh the trace SHA256SUMS | crash detection e | 2 | 0.5 h | low | 4 |
| 6 | Makefile targets: `run-twin`, `reach`, `mapflow`, `prefetch-results` (call existing code) | f for 4 features | 1 | 0.25 h | low | 4 |
| 7 | Screenshot The ONE GUI and sumo-gui / Qtenv once (`--gui` runs) into `evidence/` | mesh c, V2X c | 1 | 0.25 h | low | 4 |
| 8 | Live twin: learning run × 5 seeds and demand ×{0.75, 1, 1.5} (new results only) | twin d | 2 | 1 h (mostly compute) | low | 2 |
| 9 | GUI colours: alerted yellow, ambulance green, rerouted blue, live counter (your Step 4) | V2X / SOS / twin c | 2 | 1 h | low | 2 |
| 10 | Crash detection: threshold sweep 2.5–6 g × 10 trace seeds, plus a speed-gate baseline (new results only) | crash detection d | 1 | 1 h | low | 1 |
| 11 | Hospital reach: explain why the shares did not move (look at which points changed and by how much) | reach e | 1 | 1 h | low | 1 |
| 12 | Headway: fetch the reference checkout at `d0b994e5`, regenerate the patch, fix `SOURCES.md:99`; add Headway, travelmux, Ferrostar, PONS and The ONE to PINS; settle the Valhalla pin | map a | 1 | 1 h | low | 1 |
| 13 | Signals on the web map: colour the corridor junctions by phase in the live job's frames | signals c | 2 | 1.5 h | medium | 0.7 |
| 14 | SOS car-to-car: shares {0, 0.25, 0.5, 1} × 5 seeds, plus one explained finding (new results only) | SOS d, e | 2 | 2.5 h | low | 0.8 |
| 15 | `features/<name>/README.md` ×10, wrapper scripts, `check_setup` (your Step 2) | f everywhere | 2 | 3 h | low | 0.7 |
| 16 | Closed loop in the live twin: forecaster → edge travel times → reroute a share via TraCI (device.rerouting style), 5 seeds (your Step 3) | twin b, forecasting b | 3 | 5 h | medium | 0.3 |
| 17 | Mesh: a delivered alert makes the warned cars reroute in SUMO | mesh b | 1 | 3 h | medium | 0.2 |

**Not proposed:** forecast-aware routing in the Dhaka map app. RQ2 found it inconclusive even in Los Angeles; adding it now would be large and risky.

## Applied on 2026-10-10 (owner's yes), each followed by the tests and `make present` (7 of 7, every thesis check REPRODUCED)

| Fix | Change | `make present` log |
|---|---|---|
| 1 | Live twin renamed "live forecasting alongside the simulation"; `docs/EXPLAIN.md` says the forecasts do not steer it | `evidence/live_runs/present_20261010_172800` |
| 2 | RQ5 credits the energy saving to prefetching; Bartendr's schedule adds no extra saving in 9 of 9 rows (computed in `scripts/paper_map/research.py`) | `present_20261010_173750` |
| 3 | The OpenCity `pretrain.conf` value is recorded (`['PEMS07M']` → `['DF_METR_LA_R5']`, left by an unrestored run of `opencity_city_eval.py`) in `core/ml/forecasting/README.md` and `third_party/SOURCES.md` | `present_20261010_174324` |
| 4 | An SOS button press is sent as `button` (no peak) and labelled as the button, not the sensor (`frontend/map/src/traffictwin/tt.ts`, `core/safety/sos.py`, test in `backend/tests/emergency/test_sos.py`) | `present_20261010_174951` |
| 5 | `detect()` reports the trace's true peak, `peak_g` (crash_jolt 6.37 g), and the reading that fired the rule, `at_g` (5.87 g); detection is unchanged (12.04 s). Results rebuilt: traces byte-identical, SHA256SUMS verified OK, `evidence/sos/traces.SHA256SUMS` refreshed. `sos_graph.cjs` reads its thesis numbers from the results file | `present_20261010_175652` |

The project-wide tests in `tests/` fail 3 repository-layout checks before and after these fixes. They are unrelated to the fixes: a nested
PONS checkout and a Claude worktree, RQ1 checkpoints under `results/`, and the three RQ1 `.npz` files over 10 MB.

The search for classmate project names found none: the only hit was inside base64 image data.
