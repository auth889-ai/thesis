# How the app works, feature by feature

Each section says what a feature does, how to try it, how it works (with the files), what it has been measured to do, and what it
does not do. Every number here comes from a saved run under `evidence/`.

## Live twin: live forecasting alongside the simulation (added 2026-10-10)

The three forecasters run live beside the simulation and are scored as it runs. By default they do not steer it; a toggle (off by
default) feeds the forecast back into SUMO's routing (see "Steering traffic with the forecast" below). The decisions taken inside the running simulation are the ambulance alert and signal preemption, and the viewer's clicks.

**What it is.** A SUMO simulation of a city's corridor that keeps running in the web app, labelled SIMULATION, on the Research page
**Live twin** (`/app/lab/live-twin`; a link on the 3D City page leads there). The person can click on the map to place a crash or to
start an ambulance, move a traffic-demand slider while it runs, and watch three forecasters predict every road's speed 15 minutes
ahead and be scored live.

### Try it yourself

    make app                                  # or any local server of the API + web app
    open http://127.0.0.1:8000/app/lab/live-twin

1. Press **Start the twin**. The seed is taken from the clock and shown. The twin first warms up for 15 simulated minutes at full
   speed (a few seconds) so the forecasters have history, then runs at 8 simulated seconds per second (change it in the panel).
2. Choose what a click does: **place a crash** (the nearest car stops and blocks its lane), **start an ambulance there** (to the
   hospital in the city config), or **start, then destination** (two clicks).
3. While it runs: move **Traffic demand** (×0.5 to ×2), choose the ambulance's radio (**ITS-G5, C-V2X or 4G**), choose which
   forecaster colours the roads.
4. Watch: alerted cars turn **orange** and make way, the crashed car is **red**, the ambulance **white**; the green ring is the radio
   range. The counts give messages sent and delivered, cars alerted, signals turned green and the ambulance's time so far.
5. Below the map: the three forecasters' errors (last 10 scored minutes and since the start) and a live chart. The first scores appear
   15 simulated minutes after the first predictions.

For scripts: `POST /api/live-twin/{city}/start` → the twin's id, seed and roads; a WebSocket at `/api/live-twin/twins/{id}/ws`
streams vehicles and forecasts and accepts commands (`crash`, `ambulance`, `demand`, `technology`, `speed`, `clear_crashes`,
`stop`); the same commands go to `POST /api/live-twin/twins/{id}/command`.

### How it works

| Part | What | Files |
|---|---|---|
| City config | `live_twin:` in `config/cities/<city>.yaml`: network, demand file, demand label, base scale, the road types that get detectors. Dhaka: RQ2b's corridor and demand (DhaTraX counts at two sections, 07:00-08:00) at RQ2b's "Dhaka density" scale 0.78 (`evidence/ambulance_rq2/dhaka_density/match.json`). A city without the entry gets "no data for this city" | `core/common/data/city_config.py` (`LiveTwin`) |
| Demand | The configured hour repeated hour after hour (12 hours); SUMO's seed makes each hour different. The slider multiplies the base scale through TraCI `simulation.setScale` | `core/simulation/live_twin/demand.py` |
| Detectors | Generated from the network for any city: an E1 induction loop on every lane of each trunk, primary and secondary road at least 50 m long, aggregated per simulated minute. Dhaka: 170 roads, 373 loops. A minute in which no vehicle passed a road has no value; it is not filled in | `core/simulation/live_twin/detectors.py` |
| Simulation | SUMO 1.27.1 through TraCI, with the ambulance study's own options (sublane model 0.8 m, teleport after 300 s) | `core/simulation/live_twin/session.py` |
| Stream | sumo-web3d's approach (Sidewalk Labs, EPL-2.0): subscribe to each vehicle, send per step only the creations, the changed fields and the removals (its `deltas.py`, copied unchanged), over a FastAPI WebSocket; a new viewer gets a full snapshot first | `core/simulation/live_twin/deltas.py`, `backend/app/live_twin/router.py` |
| Crash | The car nearest the click on that road (within 100 m) stops and keeps its lane, as `scripts/live/run_sos_v2v.py` stops its car | `session.py` (`_crash`) |
| Ambulance | The RQ2 `AmbulanceRun`, arm alert + preemption, unchanged except its route id: the alert goes through the thesis's V2X delivery model (`core/networking/v2x/model.py`), alerted cars within 100 m ahead make way by rule v2 (`makeway.py`), the route's signals turn green (`SumoPreemption`). 100 % of cars equipped, as the thesis setting. **One difference from the thesis runs: no bluelight device** (see below) | `session.py` (`LiveAmbulance`), `core/simulation/ambulance/service.py` |
| Forecasters | Every simulated minute, for every road, 15 minutes ahead: **online** (River 0.26.1, one `StandardScaler` + `LinearRegression` shared by all roads; inputs: the speed now and 1, 2, 4, 9, 14 minutes earlier over the speed limit, and the demand scale; it learns the change from now to 15 minutes later, so untrained it equals "no change"; a sample is learned only when its true value arrives 15 minutes later); **Chronos-Bolt-small** zero-shot (RQ1's weights and revision, the last 60 minutes as context, gaps left as NaN, on a worker thread: a minute in which the previous call has not finished has no Chronos forecast and is said so); **no change** | `core/ml/forecasting/live/online.py` |
| Scoring | Mean absolute error in km/h, only on road-minutes all three predicted and whose true value exists; shown over the last 10 scored minutes and since the start | `online.py` |
| Page | MapLibre with a deck.gl overlay (vehicles, roads coloured by the chosen forecaster's prediction against the speed limit, radio ring, crash and hospital marks), a uPlot chart of the errors, English and Bangla | `frontend/src/features/livetwin/` |
| Limits | One twin per visitor (a second start returns it), at most 3 simulations on the server (twins plus the map's live job or the 3D City run), stopped after 60 s without a viewer; hosted: stopped after 10 minutes, 10 starts per visitor per day | `core/simulation/live_twin/manager.py`, `backend/app/platform/ratelimit.py` |

Not used here: RQ1's graph models (D2STGNN and the others) are tied to METR-LA's 207 sensors and cannot run on these roads.

### What has been measured

- **Learning run** (`scripts/live_twin/learning_run.py`; `evidence/live_twin/learning_run.json`, sha256 `50108ea2…6c5212`): one twin,
  no viewer, 180 simulated minutes, seed 1791595594, Chronos on every minute. Error since the start (km/h): online 14.33, Chronos-Bolt
  13.58, no change 14.58. Over the last 10 scored minutes the online model equals "no change" at first (minute 29: 18.06 and 18.06),
  and from about two simulated hours it is below it (minute 149: 10.81 against 12.04; minute 179: 13.04 against 13.51). The margin is
  small and changes from minute to minute; Chronos-Bolt has the lowest error over the whole run. One run, one seed: it shows the model
  learning, not that it beats the others.
- **Browser check** (`frontend/tests/qa/live_twin.cjs`; `evidence/live_twin/browser_check.json` and screenshots): 13 of 13 pass on the
  local server: seed shown, labelled SIMULATION, one twin per visitor, a click places a crash, a click starts an ambulance, messages
  are sent and delivered and cars alerted, the demand slider changes the running simulation, the forecasters are scored, the page keeps
  up with the server, the phone view runs without sideways scrolling, Stop ends it, no page errors.
- **Tests** (`backend/tests/live_twin/`): forecasters (no learning before the true value arrives, "no change" is the last value, the
  online model learns a fixed series, Chronos returns 15 steps), detectors, demand, the stream (lon/lat in Dhaka, clock seed, deltas),
  crash, ambulance and demand commands, the twin's ambulance without the bluelight device while the thesis keeps it, one twin per visitor, the server cap, the idle stop, the hosted daily limit, the WebSocket.
  Frontend: `frontend/src/features/livetwin/liveTwin.test.ts`.
- **Each reused repository's own example first** (`evidence/live_twin/upstream/`): River's README example 89.28 % (published
  89.28 %); deck.gl's MapLibre example draws as published; uPlot's basic example renders; sumo-web3d's own tests 4 of 4 and its data
  path on its own scenario (its server does not start on today's `websockets`). Details in `third_party/SOURCES.md`, "Live twin".

### Steering traffic with the forecast (closed loop, off by default; added 2026-10-10 night)

**What it does.** A toggle on the page (and `Session(steer=...)` for scripts) closes the loop, following SUMO's `device.rerouting`:
- Every simulated minute after the warm-up, the chosen forecaster's 15-minute prediction becomes each detector road's travel time (`traci.edge.adaptTraveltime`).
- A fixed share of vehicles then reroutes on those times (`traci.vehicle.rerouteTraveltime`). The share is chosen by a seeded hash, like the device's `probability`, so every arm informs the same vehicles.
- Rerouted cars turn blue.
- Code: `core/simulation/live_twin/session.py` (`_steer`, `informed`) and `frontend/src/features/livetwin/SteerControl.tsx`.
- Off by default: the twin, `make present` and every saved result are unchanged.

**Measured** (`scripts/live_twin/steer_compare.py`; `evidence/live_twin/steer_compare.json`, sha256 `be0ae1f3…`):
- **Setup:** seeds 11–15, the same seeds and informed vehicles in every arm (paired); 30 % of vehicles informed; 15 minutes of warm-up, then the window to minute 60.
- **Measure:** every trip that departed in the window (about 2 360–2 510 per seed); a trip still driving at minute 60 counts its time so far.

| Steering with | Mean trip time, s (mean over 5 seeds) | Paired difference against no steering, s (mean ± sd over seeds) | Seeds better than no steering |
|---|---|---|---|
| no steering | 963.7 | — | — |
| current travel times (no forecast) | 1 046.8 | +83.1 ± 98.3 | 1 of 5 |
| no change (last speed) | 932.6 | −31.1 ± 92.2 | 4 of 5 |
| online (River) | 951.9 | −11.8 ± 124.0 | 2 of 5 |
| Chronos-Bolt | 927.5 | −36.2 ± 115.4 | 3 of 5 |

**The finding.** No forecaster steers traffic reliably better than not steering:
- The mean differences (−36 to −12 s) are much smaller than their spread between seeds (sd 92–124 s), and the sign changes from seed to seed.
- Rerouting on current travel times is worse on average.
- The corridor is gridlocked: about 64 % of the trips that started in the window were still driving at minute 60 in every arm.

So little capacity is free to reroute into, which is consistent with RQ2's "inconclusive against reactive" in Los Angeles. One demand level, one share and five seeds: a sweep over share and demand is not done.

### The one difference from the thesis runs: no bluelight device (owner, 2026-10-10)

In the live twin only, the ambulance drives **without SUMO's bluelight device** (`has.bluelight.device` false in the twin's own copy
of the ambulance settings; `core/simulation/ambulance/configs/ambulance.yaml` and every thesis run keep it, and a test checks both).
The reason: SUMO 1.27.1's bluelight device has a recorded segmentation fault on this network (`evidence/emergency/dhaka/sumo_bluelight_crash.json`),
and with it the twin stopped (exit code 245) in 2 of the 3 server runs that started an ambulance and once in 4 test runs.

What stays: green signals on the ambulance's route (`SumoPreemption`) and cars making way under rule v2 when the alert reaches them.
What goes: the device's own behaviour, i.e. the ambulance no longer runs red lights by itself, and cars within the device's 25 m no
longer react to it directly. So the twin's ambulance times are not the thesis's numbers and must not be quoted as them; the page's info
line says this.

**Crash check after the change** (`scripts/live_twin/crash_check.py`; `evidence/live_twin/crash_check.json`, sha256 `1d924938…871cb60`):
20 twins, 20 different clock seeds, one ambulance click each at the city's ambulance origin to the hospital: **SUMO stopped in 0 of 20**,
and all 20 ambulances arrived (275 to 1 007 simulated seconds).

### What it does not do, and why

- **Q-learning signals (sumo-rl) are not in the twin.** sumo-rl needs NumPy below 2 and starts its own SUMO; River needs NumPy 2.2.5
  or later. They run as the map's separate simulation (main map → Simulation → Smart signals).
- **The traffic is generated**, fitted to recorded counts at two sections of one corridor for one morning hour; the twin repeats that
  hour. The forecasters' errors are errors on this simulation, not on Dhaka's real traffic.
- **Hosted:** not deployed yet (deploy waits for the owner's word on AWS). `infra/app/requirements.txt` has River; Chronos on the
  hosted server is optional (`infra/app/requirements_chronos.txt`, torch about 1 GB); without it the page says Chronos is not installed
  and compares the other two.
- The stream is about 0.35 MB/s at 20 simulated seconds per second; a slow phone connection will lag.
