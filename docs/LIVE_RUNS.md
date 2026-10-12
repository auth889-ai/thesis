# Live runs: every feature computed in front of the audience

Nothing below replays a saved result. Each command runs the research code now, with the parameters you give it. At the end it prints
the measured results using the same code that produced the thesis numbers. With the thesis settings it checks those numbers and says
**REPRODUCED** or **DIFFERENT**; with other settings it says the result is new.

Where a second, independent simulator is shown (Veins, The ONE), its numbers are labelled as that simulator's own. They are not
claimed to match the thesis, which used SUMO with our V2X model and PONS. Everything runs offline on this laptop, except the place
search and the Dhaka routing server in `run-offline`.

`make present` runs all of them in the order of the talk, about 7 minutes (`scripts/live/present.py --dry` lists the steps).

| # | Command | Implemented in | Thesis check |
|---|---|---|---|
| 1 | `make run-v2x` | `scripts/live/run_v2x.py` → `core/simulation/ambulance/service.py` `run_one` | any saved RQ3 run with the same seed, share, level and arm: travel times, all four message counts and cars alerted equal |
| 1′ | `make run-v2x ARGS="--veins"` | `scripts/live/run_veins.py v2x`, `research/veins_dhaka/src/AmbulanceAlert11p.*` | second view (Veins 5.3.1, 802.11p); Veins's numbers |
| 2 | `make run-sos-v2v` | `scripts/live/run_sos_v2v.py` (`core/safety/sos.py`, `core/networking/v2x/model.py`) | the SOS rule on the thesis traces = `evidence/sos/results.json`; car-to-car numbers are new (no thesis number) |
| 2′ | `make run-sos-v2v ARGS="--veins"` | `scripts/live/run_veins.py sos` (Veins's `TraCIDemo11p`, unchanged) | second view; Veins's numbers |
| 3 | `make run-signals` | `scripts/live/run_signals.py` → `service.run_one` (fixed time), `rl_signals.run` (sumo-rl Q-learning) | saved runs of the same level and seed: travel time, queue, blocked time, vehicle-hours equal |
| 4 | Model Lab page `/app/lab/model-lab`, `make run-forecast` | `core/ml/forecasting/layer/lab.py` → RQ1's `predict_checkpoints` | on an RQ1 test window the forecast equals RQ1's saved prediction |
| 5 | `make run-mesh` | `scripts/live/run_mesh.py` → PONS `NetSim.run()` | 17 phones, 10 m: each study seed's created and delivered counts equal |
| 5′ | `make run-mesh ARGS="--one"` | `scripts/live/run_mesh_one.py` (The ONE 1.6.0) | second view; The ONE's numbers |
| 6 | `make run-offline` (`ARGS="--rq5"` adds the check) | `frontend/tests/live/run_offline.cjs`; the RQ5 experiment `frontend/tests/weak_signal.experiment.cjs` | 2G-like with the saved trip: time to route within 0.2 s of the thesis median (0.8 s) |
| 7 | SOS screen graph (`/app/emergency` on a phone; on the laptop `node frontend/tests/live/sos_graph.cjs --trace=sumo_collision`) | `frontend/src/features/emergency/MotionGraph.tsx`, `useMotion.ts` | since R1 (2026-10-11 evening) the replayed trace is the one step 2 built from SUMO's own collision record (`evidence/live_runs/sos_v2v/collision_trace.json`); the countdown starts iff that run's own rule check said so. `--trace=crash_jolt` replays the thesis's SYNTHETIC trace as before (`evidence/sos/results.json`) |

## What to change live, and what the audience should see

### 1. `make run-v2x`: ambulance and V2X alert (RQ3, Dhaka corridor, simulation)
- `--share 0.25` (default 1.0). Fewer cars can hear the alert: fewer turn orange, and "cars alerted" drops. Seed 11: 30 cars at 100 %.
  Saved runs exist for 0.25, 0.5, 0.75 and 1.0, so the check still runs.
- `--tech c_v2x` or `--tech cellular_4g`. The blue range ring grows (425 m to 625 m) or disappears (4G, no range limit); the
  out-of-range count changes.
- `--seed 12` or `--level x2`. Different traffic. Seed 12 at 50 % gives no alert 343 s and alert 268 s, which the saved run confirms.
- `--arm alert`. Alert only, no green signals. On seed 11 it is faster than with signals (263 s against 284 s), a point the thesis makes.
- `--veins`, with `--share` and `--txpower` (mW). The same corridor in OMNeT++: press RUN (F5) and radio frames animate between cars;
  blue = ambulance, orange = making way.

### 2. `make run-sos-v2v`: crash SOS, car to car (simulation)
- `--share 0.1` (default 0.5). The blue wave of warned cars spreads more slowly: "half warned within … s" grows.
- `--tech c_v2x`. Longer range: more cars warned, sooner.
- `--crash-at 900`. The crash happens at a busier moment: more cars are heading for it and more reroute (green).
- `--veins`. Veins's own TraCIDemo11p: a stopped car turns red, hearers turn green and reroute. On Dhaka's queues it also warns about
  queued cars: that is its rule.

### 3. `make run-signals`: fixed-time against Q-learning signals (RQ3)
- `--level x2` or `--level x0.5`. Heavier or lighter traffic. Watch the "halting at the corridor junctions" label in each window.
- `--seed 12`. Another day of the same traffic. Seed 11 at Dhaka's density: Q-learning gets the ambulance through in 188 s against
  292 s, but costs all vehicles 794 against 532 vehicle-hours.

### 4. Model Lab: traffic prediction (RQ1, Los Angeles METR-LA, recorded data)
- **Sensor:** pick any of the 207. The chart redraws with the recorded speed, the model's forecast and "no change".
- **Moment:** `2012-06-05T08:30` is an RQ1 window in the morning rush; any moment between 4 and 27 June 2012 was never used in
  training.
- **Model:** D2STGNN, DCRNN, GWNet, MegaCRN, STAEformer, STID or "no change". On a single window "no change" can win; the thesis
  averages are over thousands of windows.

### 5. `make run-mesh`: phone-to-phone mesh (RQ4, simulation)
- `--range 30` (default 10 m, The ONE's Bluetooth setting). More phones turn orange (in range); delivered rises (The ONE at 30 m:
  8.3 %).
- `--phones 6`. Fewer phones: almost nothing is delivered.
- `--protocol spray_and_wait`. Fewer copies per alert at a similar delivery.
- `--one`. The same movement in The ONE's GUI: press Play; links appear when phones meet.

### 6. `make run-offline`: weak signal (RQ5)
- Watch DevTools' Network panel. After the switch to offline, the Size column reads "(ServiceWorker)" for the app's files and the saved
  trip.
- `ARGS="--profile=2g"` or `--profile=3g`. Throttled instead of offline, as in the thesis experiment.
- `ARGS="--rq5"`. Runs the thesis experiment once more and compares the time to route.

### 7. Crash detection graph (RQ6)
On a phone over HTTPS (the hosted site, after the next deploy), go to Emergency, Crash SOS, Arm, and shake: the blue line follows
the shake and the countdown starts when it crosses the red 4 g line. On the laptop (no motion sensor), the replay buttons run the
thesis traces through the same rule.

## One-time setup (already done on this laptop; logs in evidence/live_runs/)

```bash
third_party/omnetpp/fetch.sh && (cd ~/.dhakaflow/upstream/omnetpp-6.2.0 && ./install.sh -y --no-3d)   # see build_errors.md for the 4 fixes
third_party/veins/fetch.sh                                                                          # Veins 5.3.1 against OMNeT++ 6.2.0
python3 -m venv ~/.dhakaflow/venvs/sumo-veins && ~/.dhakaflow/venvs/sumo-veins/bin/pip install eclipse-sumo==1.21.0
(cd ~/.dhakaflow/upstream/omnetpp-6.2.0 && source setenv -q) && cd research/veins_dhaka/src && \
  opp_makemake -f --make-so -o dhakaveins -I$HOME/.dhakaflow/upstream/veins/src -L$HOME/.dhakaflow/upstream/veins/src -lveins && make MODE=release
third_party/the-one/fetch.sh                                                                       # The ONE 1.6.0
```

`run-offline` and the Model Lab need the local app server: `make present` starts it (port 8011), with the local travelmux for Dhaka
directions.

## The same runs from the web app (map "Simulation" chip)

On the main map, tap **Simulation**, pick Ambulance V2X, Crash SOS, Phone mesh or Smart signals, change the settings and press Run.
The server computes the run now with the code above (`core/simulation/live_jobs/`), streams positions to the map and ends with
the result and the thesis check (REPRODUCED, DIFFERENT, or "new" when no thesis run has these settings). One simulation runs at a
time on the server; a hosted server allows 6 starts per visitor per day.

    make app                                               # the API + web app on http://127.0.0.1:8000
    cd backend && python -m pytest -q tests/live_jobs      # parameters, one-at-a-time lock, visitor limit, lon/lat
    LOCAL_URL=http://127.0.0.1:8000/ node frontend/tests/qa/live_web.cjs   # each tab in a browser, desktop and phone → evidence/live_web/

The API, for scripts: `POST /api/live/{v2x|sos|mesh|signals}` with the settings as JSON → `{job}`; `GET /api/live/jobs/{job}?since=N`
→ new frames, status, and at the end the result; `POST /api/live/jobs/{job}/stop`. Mesh needs `research/mesh_pons/.venv`, signals the
sumo-rl venv (see above); the hosted server has neither yet.

## Display flags (added 2026-10-10 night; display only, off by default)

    make run-v2x ARGS="--gui-colours"          # alerted cars yellow, the ambulance green; label: alerted / ambulance delay / delivered / green now
    make gui-routing [ARGS="--profile its-g5 --minutes 30"]   # 2026-10-12 Part D: RQ2 forecast routing in sumo-gui on the LA twin, loop unchanged (features/forecasting/README.md, Live demo)
    make gui-ambulance-loop [ARGS="--seed 11 --arm rl_v2i"]   # 2026-10-12 Part E: the ML + V2X ambulance loop in sumo-gui (features/ambulance-loop/README.md, Live demo)
    make run-ambulance-loop                                       # Part A: 5 seeds x 4 arms headless -> evidence/ambulance_loop/
    make run-v2x-live SEED=<n> FROM=<edge|random> TO=<edge|random> [DEMAND=dhatrax-peak]   # 2026-10-12: the viewer's own seed (SEED=, else the clock; `make run-v2x` itself keeps seed 11), route and demand level; prints them and the result
    make run-sos-v2v ARGS="--gui-colours"      # warned cars yellow, rerouted cars blue; label: alerted / rerouted

The flag changes colours and the label through `traci.vehicle.setColor` and the POI label only; the runs' logic, numbers and
thesis checks are the same with and without it (`scripts/live/run_v2x.py` `gui_hook`, `scripts/live/run_sos_v2v.py` `simulate`).
The web app's live twin has its own switch, "Steer traffic with the forecast" (off by default): see `docs/EXPLAIN.md`.

## `make gui-mesh`: The ONE in its own window (added 2026-10-11)

    make gui-mesh                               # thesis setting: 17 phones, 10 m, PRoPHET, seed 1; press Play in the window
    make gui-mesh ARGS="--protocol epidemic --range 30 --seed 3"

Runs `core.DTNSim` without its batch flag, so its GUI opens on the study's own movement (`scripts/live/run_mesh_one.py`). The terminal
prints what each colour and line means (read from The ONE's `gui/playfield` sources): blue squares are phones, green circles their
radio range, black lines connections, red lines message transfers, the small squares a phone's buffer. Its numbers are The ONE's, not
the thesis's (PONS). PONS has no GUI of its own; `make run-mesh` is our live matplotlib view of it.

## Live hospital reach on the map app (step K, added 2026-10-11; off by default)

    make app → the main map `/` → Hospitals chip → switch on "Live reach: tap the map" → tap any point
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_reach.cjs      # desktop + phone check → evidence/reach/live/

A tap asks `GET /api/emergency/reach/{city}/live?lat&lon&k=3` (`core/safety/reach.py:live`): the 3 nearest hospitals by drive time,
each one's 10/20/30-minute polygons from the city's own Valhalla server (its isochrone API; computed now, in parallel, timed), and
the ambulance-direction time from the nearest hospital to the tapped point. The card says "Computed live by Valhalla in X s" and
shows the thesis's saved shares (9.7 / 27.7 / 45.9 %) unchanged beside it. Dark blue 10 min, blue 20 min, light blue 30 min. Map speeds,
not live traffic. The first answer for a point takes about 8-13 s (the routing server is in Mumbai); each hospital's polygons are
then kept while the app runs. Works on the hosted app (Valhalla is on the same instance).

## `make gui-veins`: the V2X ambulance in Veins under OMNeT++ Qtenv, next to sumo-gui (step H, added 2026-10-11)

    make gui-veins                               # thesis setting: 100 % radios, 20 mW, seed 0; press RUN (F5) or FAST (F6) in the OMNeT++ window
    make gui-veins ARGS="--share 0.5 --seed 2"

`scripts/live/run_veins.py v2x --sumo-gui --gui-colours`: our ambulance application (`research/veins_dhaka/src/AmbulanceAlert11p`, a
subclass of Veins's `DemoBaseApplLayer`) in Veins 5.3.1 on the Dhaka corridor, with Veins's own frame animation in Qtenv and the same
traffic in sumo-gui (SUMO 1.21 driven by Veins). `--gui-colours` is a parameter of our app (`guiColours`, off by default): the
ambulance green and cars that heard the alert yellow while they make way, in both windows; without it Veins's blue / orange. The
terminal prints what to watch in each window. The numbers at the end are Veins's, not the thesis's (`make run-v2x`).

## `make run-sos-collide`: a real collision inside SUMO (step N, added 2026-10-11)

**R1 (2026-10-11 evening): the crash sensor's trace from SUMO's own record.** After the contact the run reads `collisions.xml`
(`colliderSpeed`, `victimSpeed`, written by SUMO) and builds the accelerometer trace the Emergency page replays: the closing speed
|collider − victim| becomes a 120 ms half-sine pulse along x (the pulse length is ASSUMED, the synthetic trace's; SUMO records the speeds
at the contact, not the impact), with the same road noise as the synthetic traces, and every sample carries the speed of the car whose phone
runs the rule (the one the story calls crashed), so WreckWatch's 15 mph floor is applied for the first time. `core/safety/sos.py:from_collision`
→ `evidence/live_runs/sos_v2v/collision_trace.json` (kind `sumo_collision`, label SIMULATION, detection recorded inside). The same trace
API serves it (`/api/emergency/sos/trace/sumo_collision`, 404 until the run has happened), the Emergency page shows a fourth chip
"collision from the simulation" only when it exists, the Research RQ6 table adds one labelled line, and `make present` runs this
collision as step 2 and replays its trace as step 7. The three SYNTHETIC traces and `evidence/sos/results.json` are unchanged.
Run of 2026-10-11 19:49 (seed 11, Dhaka density, ITS-G5, 50 %, headless): SUMO's record at t = 687 s, collider CNG `veh284` at
12.26 m/s, victim motorcycle `cal300_174` (the commanded car) at 20.00 m/s; closing speed 7.74 m/s → 10.33 g pulse; phone at 72.0 km/h;
the rule fires at 12.02 s (5.18 g on that sample). Tests: `backend/tests/emergency/test_sos.py` (the pulse's integral, the speed floor,
the API, the row), `tests/platform/test_live_runs.py::test_present_runs_a_real_collision_and_replays_its_trace_in_the_graph_step`.

    make run-sos-collide                          # seed 11, Dhaka density, ITS-G5, 50 % of cars with the app; crashed cars red
    make run-sos-collide ARGS="--share 0.5 --seed 12 --no-gui"

`scripts/live/run_sos_v2v.py --collide --gui-colours`: at the crash time one car on the crash road that has a car ahead stops obeying
SUMO's safe-speed rules (`speedMode 0`, no lane change) and drives into it; SUMO runs with `--collision.action warn` and
`--collision.stoptime` (the colliding cars stop, then continue; SUMO docs, Simulation/Safety) and writes every contact to
`collisions.xml`. The trigger is SUMO's own `simulation.getCollidingVehiclesIDList()`, not a stop we impose; from there the existing
car-to-car SOS path runs unchanged (delivery through the thesis's V2X model, receivers reroute as TraCIDemo11p does). The terminal
first prints the five differences from Veins's TraCIDemo11p (read from the vendored source, not run). SUMO's record of the contact
(collider, victim, lane, position, time) is kept in `evidence/live_runs/sos_v2v/last_run.json`. No thesis number exists for car-to-car
SOS; the figures are new, as the run says.

## AID: automatic incident detection inside SUMO (step J, added 2026-10-11; our own design)

    make aid-train                                # 5 training seeds (1-5): rows -> data/aid/train.csv, model -> results/aid/model.joblib (about 1 min)
    make aid-eval                                 # 5 held-out seeds (11-15) on the unseen station pairs -> evidence/aid/summary.json (about 2 min)
    make aid-gui ARGS="--seed 12"                 # LIVE: sumo-gui, the model watching every pair every 30 s; incident red, warned yellow, rerouted blue
    make aid-train ARGS="--sensor camera"          # J2: the same seeds with cameras at the 2 signalised junctions -> data/aid/camera_train.csv, results/aid/camera_model.joblib
    make aid-eval ARGS="--sensor camera"           # J2: held-out seeds, offline -> evidence/aid/camera_summary.json (no closed loop)
    make aid-frontier                              # J1: DR vs false alarms over the thresholds, loop model + California #7 + camera, x0.78 (saved rows) and x0.3 (new runs) -> evidence/aid/frontier/

Run 2026-10-11: frontier (`evidence/aid/frontier/frontier.json`, sha256 `0902fba9…`): under 0.5 false alarms per pair-hour no detector
passes DR 0.10 at either density; DR 0.5-0.8 costs 5-11 false alarms per pair-hour; California #7 tops out at 0.15. Camera (J2,
`evidence/aid/camera_summary.json`, sha256 `b1afeee9…`): DR 0.45 at 6.96 false alarms per camera-pair-hour on the held-out seeds;
details and limits in `features/aid/README.md`.

E1 loops every 300 m along the ambulance route (11 stations, 10 pairs; `core/simulation/aid/stations.py`), one row per pair per 30 s
(speeds, occupancies, flows of both stations, the California differences, the downstream occupancy's change). Incidents: a vehicle
stopped in its lane for 3-5 minutes at random times and places (`core/simulation/aid/run.py`). Baseline: California Algorithm #7
(Payne & Tignor 1978), thresholds calibrated on the training seeds. Model: scikit-learn HistGradientBoosting, trained on seeds 1-5
and the even-numbered pairs, tested on seeds 11-15 and the odd-numbered pairs. Closed loop: a detection sends the V2X warning from the
pair's downstream station (the thesis's delivery model) and reroutes the warned cars as the live twin's steering does. The result is
in `features/aid/README.md`; it is honest and negative at Dhaka's density.

## The phone's real accelerometer on the map app (step D, added 2026-10-11)

    on a phone over HTTPS (the hosted app): start a trip → tap "Use this phone's crash sensor" → iOS asks once → "Crash sensor on: 1.02 g" updates live
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/phone_sensor.cjs     # headless check with synthetic DeviceMotionEvents → evidence/sos/phone_sensor/

`frontend/map/src/traffictwin/tt.ts:usePhoneSensor` asks `DeviceMotionEvent.requestPermission()` inside the tap (iOS grants it only
there), then arms the same detector as before (`frontend/src/maplink/index.ts:armCrashDetector`, the WreckWatch rule unchanged: 4 g
on `accelerationIncludingGravity`) with the source `phone-sensor` and a live g readout (10 samples a second at most). A detection from
the real sensor is TEST and stays on the phone: the app does not post it, not even to its own alerts feed, and the server refuses to
store one that is posted (`core/safety/sos.py:raise_test`). The SOS button and the automatic arming are unchanged. DeviceMotion exists
only in a secure context, so over plain HTTP the button says the sensor needs HTTPS.

## `make demo`: the talk's live parts, one after another (step F, added 2026-10-11)

    make demo                      # 9 parts in the talk's order; Enter runs a part, s skips it, q quits; the app server is started if needed
    make demo ARGS="--list"        # prints the parts and their commands without starting anything
    make demo ARGS="--only v2x,map"

`scripts/live/demo.py`: 1 V2X with `--gui-colours`, 2 `gui-veins`, 3 smart signals, 4 the live twin with steering (browser), 5 `gui-mesh`,
6 `run-sos-collide`, 7 `aid-gui`, 8 the Model Lab (one forecast computed now, checked against RQ1's saved window), 9 the map app (live
reach, the phone sensor). Each part prints "What to watch" before it starts. `make present` (the timed 7-step run) is unchanged.

## `make run-routing-quick`: the RQ2 closed loop live on the Los Angeles twin (step L, added 2026-10-11)

    make run-routing-quick ARGS="--quick"    # 1 seed (201), baseline + predictive_corrected_v2x, about 7 min; THESIS CHECK per seed-arm
    make run-routing-quick                    # 2 seeds x 3 arms, about 25 min (each V2X arm about 5 min per seed; not under 5 min)

`scripts/live/run_routing_quick.py` runs `core.simulation.closed_loop.control.closed_loop.run_point` with the saved run's PROTOCOL
(la_c4_central_wide, prepeak, ideal link, 30 % penetration, 8x peak demand on the arterials, fork at 1 200 s, 4 800 s, Graph WaveNet
every 300 s) and reuse off, then compares total vehicle-hours (incl. never inserted), arrivals and teleports per seed and arm with
`results/v2x/closed_loop/..._stressA_eval_fork1200_x8_peak_arterial/report.json`. Run on 2026-10-11 (`--quick`): seed 201 baseline
3 750.9 veh-h (69 s), predictive_corrected_v2x 3 770.7 veh-h (288 s), **REPRODUCED exactly, 2 of 2**, 428 s in all
(`evidence/live_runs/routing_quick/last_run.json`). The quick mode is a check, not the RQ2 evidence (that stays the saved 2-seed run).

## `make sweep-v2x`: equipped share 0 / 25 / 50 / 75 / 100 % at Dhaka density (step I, added 2026-10-11)

    make sweep-v2x ARGS="--quick"    # seeds 11, 12 (10 runs, 4 at a time) -> evidence/sweeps/v2x_share_quick.{csv,png,json}
    make sweep-v2x                    # seeds 11-15 (25 runs) -> evidence/sweeps/v2x_share.{csv,png,json}

`scripts/live/sweep_v2x.py` calls the thesis's own `core/simulation/ambulance/service.run_one` (make-way v2, alert + pre-emption over
ITS-G5 by default; `--arm alert`, `--tech c_v2x|cellular_4g`); share 0 is the siren-only run every saving is measured against. Every run
is checked against the study's saved run with the same settings (REPRODUCED / DIFFERENT / new) and the runs go to `evidence/sweeps/runs/`,
never into `results/`. The plot shows each seed's saving against the share and the median; the JSON records the counts and the sha256.
Run on 2026-10-11 (5 seeds, 25 runs, 213 s, 4 at a time): **25 of 25 REPRODUCED exactly**; median saving 71 s at 25 %, 76.5 s at
50 %, 32 s at 75 %, 8 s at 100 %, with means swinging from +109 s to −142 s because single seeds lose up to 699 s, and 6 of the 25 runs
(seed 14's four alert runs, seed 12 at 25 %, seed 13 at 100 %) have no arrival: SUMO 1.27.1's bluelight device stopped the run, exactly as
in the saved study runs (`evidence/emergency/dhaka/sumo_bluelight_crash.json`). So the sweep shows no monotone gain with the share: the
same finding as `results/emergency/dhaka/rq2/summary.json` (`findings.stops`), which stays the thesis's number. The quick mode
(seeds 11, 12; 100 s) reproduces 10 of 10.

## `make run-twin`: the live twin in the browser (step E, added 2026-10-11)

    make run-twin                    # starts the app server if needed (port 8011), opens /app/lab/live-twin, prints what to do; Ctrl-C ends it

Nothing is simulated by the command itself: the twin runs on the server when "Start the twin" is pressed (`docs/EXPLAIN.md`).

## `docs/QA_PREP.md` (step G, 2026-10-11): two results the examiners will ask about

Read-only: per-seed tables and the file:line of every number for (1) alert + pre-emption 3 s against alert only 26 s at Dhaka density,
and (2) rerouting on current travel times 1 047 s against no steering 964 s in the live twin. Both say where the cause is not established.

## Max-Pressure signals and EV priority (step S, added 2026-10-11)

    make run-signals ARGS="--controller maxpressure"       # right window: Max-Pressure (Varaiya 2013) instead of Q-learning; --controller maxpressure_ev adds EV priority
    make compare-signals                                    # headless: fixed time, Q-learning, Max-Pressure, Max-Pressure + EV priority on seeds 11-15 -> evidence/signals/controllers/
    make compare-signals ARGS="--quick"                     # seeds 11, 12

Survey (GitHub API, read-only; `third_party/SOURCES.md`): RESCO (GPL-3.0) and LibSignal (no licence) both have a Max-Pressure agent;
neither can be copied into this MIT repo, so the controller is ours (`core/simulation/signals/signal_baselines.MaxPressureController`:
queue-based pressure, min green 10 s, max 60 s, the program's own yellow) on the same three corridor junctions the Q-learning arm controls.
EV priority (`core/simulation/ambulance/mp_signals.MaxPressureEV`): the junction within the alert's `ahead_m` of the driving ambulance
prefers its approach's green, program-safe; no V2X message. Run 2026-10-11 (`evidence/signals/controllers/compare.json`, sha256 `6dd664df…`,
260 s; fixed time and Q-learning **10 of 10 REPRODUCED exactly** against the study's runs):

| Controller | Ambulance, s (mean; arrived) | Others' mean time loss, s | Vehicle-hours | Queue at signals | vs fixed, ambulance (paired) |
|---|---|---|---|---|---|
| fixed time | 411.6 (5 of 5) | 483.1 | 792.0 | 7.4 | — |
| Q-learning (sumo-rl) | 380.3 (3 of 5; 2 bluelight stops) | 417.4 | 933.8 | 0.4 | +108 ± 306 (2 of 3 better) |
| Max-Pressure | 493.6 (5 of 5) | 490.8 | 764.4 | 3.7 | +82 ± 629 (2 of 5 better) |
| Max-Pressure + EV priority | 475.0 (5 of 5) | 493.0 | 800.0 | 1.8 | +63 ± 495 (2 of 5 better) |

Honest result: **no controller is reliably better than fixed time on this corridor at Dhaka density.** Max-Pressure cuts the queue at the
signals (7.4 -> 3.7 vehicles) and halves the ambulance's time on seeds 11 and 13 (187 / 190 s against 292 / 898 s) but quadruples it on
seed 14 (1 342 s against 299 s); EV priority fires twice per run (both junctions on the route) and trims the worst case (849 s) without
making the mean reliable (2 of 5 seeds better, sd 495 s). Others' time loss is within 10 s of fixed time with sd about 280 s. The
mechanism is the one in `docs/QA_PREP.md`: the ambulance's time is set by the cars queued in front of it, which a greener light cannot
clear in time at this density.

## `make sweep-mesh`: The ONE's routers over the phone count (step P, added 2026-10-11)

    make sweep-mesh                      # Epidemic, Spray-and-Wait, PRoPHET, MaxProp x phones 17/50/100/200 x seeds 1-3 (48 runs, about 40 s) -> evidence/mesh/routers/
    make sweep-mesh ARGS="--quick"       # seed 1 only

The ONE 1.6.0 (GPL-3.0, batch, unchanged) on the study's window (research/mesh_pons/work/dhaka.fcd.xml, 900-1200 s): phones ranked by
presence (17 present throughout = the thesis's set; 50 present >= 236 s, 100 >= 175 s, 200 >= 77 s), absent phones parked out of range;
messages only among the 17 full-window phones at every count (the added phones relay), 300 messages per run, radio 10 m, seed = the
message set. Run 2026-10-11 (`evidence/mesh/routers/sweep.json`, sha256 `2c777c3e…`): delivery ratio 0.036-0.040 for every router at every
count (Epidemic 0.036 -> 0.040 from 17 to 200 phones; PRoPHET 0.038 at every count; MaxProp 0.036 -> 0.039), latency 71-79 s. **The
router does not matter and extra relays do not help here**: with a 10 m radio over a 5.8 x 5.5 km network in a 300 s window, contacts are
the bottleneck, and a message is delivered only when sender and receiver (or one relay) meet. These are The ONE's numbers, consistent with
the thesis's PONS result (0.028 with 17 phones, `results/networking/mesh/dhaka/summary.json`, which is untouched).

    make sweep-mesh ARGS="--range-sweep"   # P2: Epidemic, 17 and 100 phones, radio 10/30/50/100 m, seeds 1-3 (24 runs, 13 s) -> evidence/mesh/range/

Run 2026-10-11 (`evidence/mesh/range/range.json`, sha256 `0010567a…`): delivery ratio with 17 phones 0.036 / 0.077 / 0.090 / 0.110 at
10 / 30 / 50 / 100 m, with 100 phones 0.040 / 0.103 / 0.123 / 0.184; latency 72-107 s. **Delivery rises with range at both counts, and
with the range the extra relays start to matter** (at 100 m, 100 phones deliver 0.18 against 0.11 for 17): contacts are the bottleneck.
Even at a Wi-Fi-Direct-class 100 m, fewer than one message in five arrives within the 300 s window.

## `make sweep-sos`: crash SOS car to car over app share and crash time (step Q1, added 2026-10-11)

    make sweep-sos                       # share 25/50/75/100 % x crash at 600/900 s x seeds 11-15, + 10 no-warning twins (50 runs, about 3 min) -> evidence/sos/sweep/
    make sweep-sos ARGS="--quick"        # seeds 11-12, crash at 600 s (10 runs, under 1 min)

The live run's own `simulate()` (`scripts/live/run_sos_v2v.py`), headless, ITS-G5, Dhaka density: a car stops at the crash time, its
phone's rule fires, the warning floods car to car through the thesis's V2X model, warned cars still routed over the crash road reroute
(TraCIDemo11p's way). Each cell is paired with the same seed's run without any warning. Headline per cell: the mean time from the
crash to arrival over **all** the cars that were heading for it, a car not arrived within 600 s counted at 600 s (the mean over arrived
cars alone rewards stranding cars); also the extra cars arrived within 600 s. Run 2026-10-11 (`evidence/sos/sweep/sweep.json`, sha256
`52f20766…`): warned 213-971 cars, rerouted 1.4-8.4 per run (few other roads on the corridor; "no other road" for most); seconds saved,
medians by share and crash time: 25 % −0.6 / +1.5, 50 % −3.1 / −4.1, 75 % +3.8 / −1.4, 100 % +5.8 / +4.4 (600 s / 900 s crash), slower in
1-4 of 5 seeds; extra arrivals within 600 s: 0.0 / 5.6 / 11.6 / 11.4 for the 600 s crash, −0.8 / −0.6 / 1.4 / 1.2 for the 900 s crash;
in-range delivery 0.90-0.91 (the model's 0.9). **The warning reaches nearly every equipped car but changes few routes, and the saving
is inside the seed spread**: at 75-100 % it gets about 11 more cars through within 10 minutes when the crash comes at 600 s, nothing
reliable at 900 s. CHECK: the saved live run's cell (seed 11, 50 %, crash at 600 s) REPRODUCED; the SOS rule on the thesis traces
REPRODUCED. There is no thesis number for car-to-car SOS; nothing saved was changed.

## `make aid-incidentnet`: IncidentNet's own XGBoost code on our camera rows (step J3-A, added 2026-10-11)

    make aid-incidentnet            # their training function and their evaluate() protocol, unchanged, on data/aid/camera_*.csv (under 1 min) -> evidence/aid/frontier/incidentnet.{json,png}

Five files of MPSLab-ASU/IncidentNet @ `7d73a229` (Apache-2.0) copied unchanged into `third_party/incidentnet/` with a NOTICE; nothing
installed (xgboost 3.4.1 already present; their requirements pin no version). Their scenario, data and models are not in the repo, so the
paper's 98 % / 6.26 % / 197 s are context only. Run 2026-10-11 (`incidentnet.json`): **their way** (one dataset of all 1 200 camera rows,
`df[299:]`, random 80/20 row split x5): accuracy 0.7171 ± 0.0248, recall 0.3156 ± 0.0514, precision 0.4129 ± 0.0424;
**our protocol with their recipe** (train seeds 1-5, held-out 11-15): best DR 0.7 at 7.2 FA/pair-h (thr 0.15), the J2 camera model 0.7 at 7.68;
under their evaluate() protocol detection 90.0 %, false alarms 0.67 % of predictions, time to detect 60.0 s (their 1 000-row look-back
suppresses false alarms at our 30 s rows). Their eval entry point called as written: `TypeError: evaluate() takes 2 positional arguments but 4 were given` (the file defines
`evaluate` twice; recorded, not edited). Saved AID results, model and CSVs unchanged (`evidence/aid/summary.json` still `eedd6fef…`).

## `make prefetch-masts`: the weak-signal profile from real OSM mast positions (step Q3, added 2026-10-11)

**R2 / R3 (2026-10-11 evening, "all features real and dynamic" before the redeploy).** R2: the hosted app's `.env` (written by
`infra/app/setup.sh`) sets `TRAFFICTWIN_SIGNAL_MASTS=1`, so the trip's weak-signal strip on the hosted app also uses the real OSM
mast positions (`road_source` says so); the code default stays off; the package ships `data/cities/dhaka/masts.json` and
`evidence/prefetch/masts/summary.json` (`infra/app/data_files.txt`, checked by `backend/tests/test_hosted_package.py`). R3: the Research
page's RQ5 energy table ends with one line from the mast profile (`/api/networking/prefetch` → `energy.masts`, read from
`evidence/prefetch/masts/summary.json` at request time by `core/networking/prefetch/results.py:masts_row`); the saved synthetic rows and the
summary's sha256 are unchanged (`backend/tests/networking/test_prefetch_masts.py`).

    make prefetch-masts                  # data/cities/dhaka/masts.json (saved Overpass answer, OSM base 2026-10-11) + the real route -> evidence/prefetch/masts/ (seconds)
    make prefetch-masts ARGS="--fetch"   # refresh the masts from the Overpass API first (one query, recorded in the file)

Replaces the SYNTHETIC weak stretches of RQ5's energy estimate with the level modelled from the nearest OpenStreetMap radio site
(8 of 40 elements in the box qualify) and the 3GPP TR 38.901 urban-macro path loss at 1.8 GHz with an ASSUMED EIRP of 56 dBm; bins at
Bartendr's anchors. Run 2026-10-11 (`evidence/prefetch/masts/summary.json`, sha256 `33aa91c8…`): nearest site median 2 040 m;
steps strong 4 / medium 32 / weak 49 of 85; energy on this profile now 35.1 J, as needed 140.3 J, Bartendr 35.1 J in 1 burst at km 10 (saving 75.0 %).
**Honest reading:** OSM lists a tiny fraction of Dhaka's cell sites, so "weak" here means "no OSM mast nearby", and the schedule's one
burst comes after 80 % of the drive because the energy model has no deadline. Not measured on any phone. The saved thesis results
(`results/networking/prefetch/summary.json`, sha256 `99013624…`) are untouched; the app uses the mast bins only with
`TRAFFICTWIN_SIGNAL_MASTS=1`.

## Veins loops (2026-10-12): `make veins-ambulance-loop`, `make veins-forecast-routing`

Machine learning and a packet-level 802.11p network (Veins 5.3.1) in ONE SUMO run, two TraCI clients. Architecture, what to see, results: `docs/VEINS_LOOPS.md`; evidence `evidence/veins_ambulance_loop/`, `evidence/veins_forecast_routing/`.
