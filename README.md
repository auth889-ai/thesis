# Do traffic models and V2X alerts built for Western cities work in Dhaka?

*An undergraduate thesis (IUT CSE, Networking Research Group) on machine learning and networking for road traffic, with Dhaka as the case study and Los Angeles as the comparison city (Berlin is configured; no Berlin result yet). Every number below is generated from a results file by `scripts/readme/build.py`.*

## Why

Most traffic forecasting models, V2X safety protocols and routing ideas are built and tested on roads in Los Angeles, the San Francisco Bay Area or Europe: loop detectors with months of history, lane discipline, one vehicle type. Dhaka has none of that. Its roads mix cars, buses, rickshaws, CNGs and motorbikes, its speeds jump from minute to minute, and a camera site has one recorded day. This thesis takes established methods from their papers and official code, reproduces each one's published result first, and then measures what happens when it meets Dhaka: forecasting, forecast-aware routing, an ambulance alert over V2X, phone-to-phone alerts without a network, maps that work on a weak signal, and crash detection on the phone. The web app at the end applies what held up, and says where it did not.

## Research questions

| New | Question | Status | Earlier number in `docs/EXPERIMENT_PROTOCOL.md` | Earlier number in code, result folders and the app |
|---|---|---|---|---|
| RQ1 | Forecasting transfer to Dhaka | done | RQ4 | RQ1 |
| RQ2 | Forecast-aware closed-loop routing against reactive routing | Los Angeles only; not run in Dhaka | RQ1 and RQ6 | — |
| RQ3 | V2X ambulance alert and signal control, corrected make-way rule | done | RQ5 (part) | RQ2 |
| RQ4 | Offline phone-to-phone mesh: Epidemic, Spray and Wait, PRoPHET | done (sparse setting) | — | — |
| RQ5 | Weak-signal prefetch: time to a usable route and radio energy | done | — | — |
| RQ6 | Crash detection on the phone, WreckWatch rule | done (synthetic traces) | — | — |
| Supporting | Ambulance reach from hospitals (isochrones) | done | — | — |
| Planned | Uncertainty and on-time arrival | not run | RQ2 | — |
| Planned | Sensor coverage needed before forecasts help | not run | RQ3 | — |

## ML

### RQ1 · Forecasting transfer to Dhaka: how far ahead, and why Dhaka differs

*Los Angeles, San Francisco Bay Area, Dhaka · from `results/forecasting/rq1/summary.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| Graph WaveNet, METR-LA, MAE@15min | 2.69 | 2.719 | — |
| Graph WaveNet, PEMS-BAY, MAE@15min | 1.3 | 1.3083 | — |
| OpenCity, cross-city (zero-shot), MAE (zero-shot, PEMS07M, authors' 288-step horizon) | 4.5 | 4.5 | — |
| PatchSTG, LargeST-SD, 12-step average MAE (trained with the authors' recipe) | 16.9 | 16.9825 | — |
| Chronos-Bolt-small, exchange_rate, MASE | 1.77484 | 1.77722 | — |
| Dhaka (DhaTraX), 15-minute MAE km/h: best zero-shot (Chronos-Bolt-small (zero-shot)) against persistence | — (none published for this measure) | — | 2.225 against 2.385 |
| Dhaka (DhaTraX), 60-minute MAE km/h: best zero-shot (Chronos-2 (zero-shot)) against persistence | — (none published for this measure) | — | 2.877 against 2.717 |

**The finding.** Dhaka (DhaTraX, three camera sites, one day each), the best model other than persistence: at 15 minutes Chronos-Bolt-small (zero-shot) 2.225 km/h against persistence 2.385 (better); at 30 minutes Chronos-2 (zero-shot) 2.41 km/h against persistence 2.623 (better); at 60 minutes Chronos-2 (zero-shot) 2.877 km/h against persistence 2.717 (not better).

**Why.** Dhaka's speeds jump: 6.5-13.1 % of 5-minute steps change by more than 30 % of free-flow, against 0.7 % on a median METR-LA sensor-day and 0.0 % on PEMS-BAY. 2 of 3 sites vary more than a median Los Angeles sensor-day (coefficient of variation BM 0.51, BS 0.19, INT 0.49 against 0.229, and 0.1621 in the Bay Area); 3 of 3 remember less an hour ahead (autocorrelation at 60 minutes 0.08-0.3 against 0.3572 and 0.5766).

### RQ2 · Forecast-aware closed-loop routing against reactive routing

*Los Angeles (twin); not run in Dhaka · from `results/v2x/controller_status.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| Vehicle-hours against reactive rerouting (Los Angeles twin) | — (none published for this measure) | — | -0.91 % (95 % CI -2.15 to +0.33; 4 wins, 1 losses): INCONCLUSIVE |
| Vehicle-hours against no rerouting | — (none published for this measure) | — | -0.12 % (95 % CI -1.07 to +0.83; 2 wins, 3 losses): INCONCLUSIVE |
| Oracle (perfect future speeds) against reactive: is future information worth anything? | — (none published for this measure) | — | -1.83 % (95 % CI -3.52 to -0.14; 5 wins, 0 losses): HELPED |
| Dhaka | — | — | not run (RQ1: no Dhaka forecast with skill an hour ahead) |

**The finding.** Perfect future speeds beat reactive rerouting (-1.83 % (95 % CI -3.52 to -0.14; 5 wins, 0 losses): HELPED); our forecasts do not yet (-0.91 % (95 % CI -2.15 to +0.33; 4 wins, 1 losses): INCONCLUSIVE).

**Why.** Future speeds are worth something here (the oracle), but why our forecasts fall short of it has not been isolated.

## Networking and safety

### RQ3 · V2X ambulance alert and signal control (make-way v2)

*Dhaka (simulated, generated demand) · from `results/emergency/dhaka/rq2/summary.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| sumo-rl Q-learning against fixed timing, waiting time over the last 20 % of steps (s) | — (none published for this measure); direction of its README figure | 31.2 against 3418365.7: pass | — |
| Alert to vehicles, time saved, s (Dhaka-density corridor, 54.37 against recorded 57.7 vehicles/km) | — (none published for this measure) | — | median 26.0 (25-75 %: -17.0 to 39.8); 4 of 10 runs slower than the siren alone |
| Alert + signal preemption, time saved, s (Dhaka-density corridor, 54.37 against recorded 57.7 vehicles/km) | — (none published for this measure) | — | median 3.0 (25-75 %: -21.0 to 32.5); 4 of 10 runs slower than the siren alone |
| Q-learning signals (sumo-rl), no alert, time saved, s (Dhaka-density corridor, 54.37 against recorded 57.7 vehicles/km) | — (none published for this measure) | — | median -49.5 (25-75 %: -243.8 to 140.0); 5 of 10 runs slower than the siren alone |

**The finding.** At the density the corridor reaches (54.37 vehicles/km on the INT section against the recorded 57.7), the alert to every vehicle saves a median 26.0 s (time saved, 25-75 %: -17.0 to 39.8 s) over 10 paired seeds, 4 of them slower than the siren alone; with signal preemption it saves a median 3.0 s (time saved, 25-75 %: -21.0 to 32.5 s); with Q-learning signals and no alert it costs a median 49.5 s (time saved, 25-75 %: -243.8 to 140.0 s). Only 653 vehicles an hour pass the section there, against 1184 recorded: the density matches, the flow does not.

**Why.** Smarter signals do more: the Q-learning signals' median saving beats the alert to every vehicle at 5 of 5 densities, which suggests the ambulance's delay on this route sits at the junctions more than behind vehicles that could move aside.

In plain words, as the app says it:

> In simulated traffic as crowded as Dhaka's recorded morning rush on one road, warning every nearby vehicle typically got the ambulance there about 26 s sooner on a 346 s trip, though not every time; smarter traffic lights made it about 49 s later. *(Simulation, Dhaka; demand level: the Dhaka-density corridor. How we know: `docs/PAPER_MAP.md`, RQ3, and the ambulance card on Research.)*

### RQ4 · Offline phone-to-phone mesh (Epidemic, Spray and Wait, PRoPHET)

*Dhaka (simulated, sparse setting) · from `evidence/mesh/dhaka/results.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| Epidemic: delivery ratio | — (none published for this measure) | — | 0.028 ± 0.009 (n=5) |
| Spray and Wait (7 copies, non-binary): delivery ratio | — (none published for this measure) | — | 0.027 ± 0.014 (n=5) |
| PRoPHET (PONS defaults): delivery ratio | — (none published for this measure) | — | 0.029 ± 0.013 (n=5) |

**The finding.** In this sparse setting the three routers deliver 2.7-2.9 % of messages; PRoPHET (PONS defaults) needs 0.03 copies per message against up to 0.62.

**Why.** Only the 17 of 277 vehicles present for the whole window take part, so a message reaches only those; low delivery is the sparse setup, not a property of the city.

### RQ5 · Weak-signal prefetch: time to a usable route and radio energy (Bartendr, BreadCrumbs)

*Dhaka route, emulated network · from `evidence/prefetch/summary.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| Time to a usable route on a 2G-like link, s (without → with prefetch) | — (none published for this measure) | — | 7.4 → 0.8 |
| Radio energy saved by prefetching the pack on a good signal against downloading as needed (Bartendr's schedule adds no extra saving in our runs) | — (none published for this measure) (Bartendr's own setting differs) | — | 43.4-73.3 % (estimated from Bartendr's measured power, not measured) |

**The finding.** On a 2G-like link the route appears in 0.8 s with the pack against 7.4 s without; prefetching on a good signal is estimated to save 43.4-73.3 % of radio energy (Bartendr's schedule adds no extra saving in our runs: in 9 of 9 rows it chose a single download at once, the same energy as downloading the pack now).

**Why.** A weak radio sends slowly and stays powered longer per byte; fetching once in a strong stretch avoids both.

### RQ6 · Crash detection on the phone (WreckWatch rule)

*none (synthetic traces) · from `evidence/sos/results.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| normal_ride: peak 1.54 g | — (none published for this measure) | — | not detected |
| hard_brake: peak 2.03 g | — (none published for this measure) | — | not detected |
| crash_jolt: peak 6.37 g | — (none published for this measure) | — | detected |

**The finding.** On synthetic traces the rule flags the crash jolt only (1 of 3).

**Why.** Only the crash jolt passes 4.0 g.

## Supporting measurement

### Supporting · Ambulance reach from hospitals (isochrones)

*Dhaka (map speeds) · from `results/reach/dhaka/summary.json` · full section: [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md)*

| Measure | Baseline paper, published | Our reproduction | Our result (city as stated) |
|---|---|---|---|
| Share of Dhaka's 2610 grid points within 10 minutes of an emergency hospital | — (none published for this measure) | — | 9.7 % |
| Share of Dhaka's 2610 grid points within 20 minutes of an emergency hospital | — (none published for this measure) | — | 27.7 % |
| Share of Dhaka's 2610 grid points within 30 minutes of an emergency hospital | — (none published for this measure) | — | 45.9 % |

**The finding.** 45.9 % of Dhaka's grid is within 30 minutes of an emergency hospital at map speeds (9.7 % within 10).

**Why.** Not analysed: the study measures reach; it does not test causes.

## Limitations

- **RQ1:** DhaTraX speeds come from camera tracking whose calibration the authors did not validate; one day per site.
- **RQ1:** LA units are mph (loop detectors); Dhaka units are km/h (camera median speed).
- **RQ1:** The foundation models are deterministic; seeds vary the scored test block and the trees' training.
- **RQ2:** One Los Angeles scenario; five evaluation seeds.
- **RQ2:** Not run in Dhaka.
- **RQ3:** All traffic is simulated (SUMO); the demand is generated, not calibrated to Dhaka counts.
- **RQ3:** The ambulance's 3.4 km route crosses 2 signals; the Q-learning baseline controls the 3 signals within 500 m of it.
- **RQ3:** ITS-G5 only in the sweep; C-V2X and 4G at one density are in the earlier table.
- **RQ3:** SUMO 1.27.1's bluelight device crashes on some seeds; a crashed seed is replaced by the next one.
- **RQ3:** The simulation does not reach Dhaka's recorded density on the INT section (see density_gap): every ambulance number here is from traffic lighter on that road than Dhaka's recorded morning, and is not a statement about Dhaka at its recorded density.
- **RQ4:** Every number is a simulation on generated, uncalibrated traffic; nothing is a measurement of the city.
- **RQ4:** Only the 17 of 277 vehicles present for the whole window take part, so a message reaches only those; low delivery is the sparse setup, not a property of the city.
- **RQ5:** Energy is estimated from Bartendr's Palm Pre measurements (ACM MobiCom 2010), not measured on our phones.
- **RQ5:** Not measured: offline, the map: whether our own tiles were drawn after the network was cut (the route answers stayed on screen in both arms because the app shell keeps its last answers).
- **RQ6:** Synthetic traces only; no recorded crash.
- **Supporting:** Map speeds, not live traffic.
- **Future work, uncertainty and on-time arrival:** not run: RQ1 found no model that beats "no change" at 60 minutes in Dhaka, so there is no forecast whose intervals are worth calibrating there yet; it needs more recorded Dhaka days first.
- **Future work, sensor coverage needed before forecasts help:** not run: RQ2 has not yet shown a traffic benefit from forecasts in Los Angeles, so there is no benefit yet to measure against sensor coverage.

## Repository layout

| Folder | What is in it |
|---|---|
| `core/ml/` | Forecasting (adapters for the official models, training, evaluation, the Dhaka transfer study), perception, the incident text classifier |
| `core/networking/` | V2X channel and delivery, the PONS mesh results, the weak-signal prefetch results, Eclipse MOSAIC |
| `core/simulation/` | The SUMO twin, signal control (sumo-rl), routing, the closed-loop controller, the ambulance study |
| `core/safety/` | Crash detection (WreckWatch rule), hospitals, ambulance reach |
| `core/common/` | Paths, city configs, datasets and recorded data, provenance labels |
| `backend/app/` | The web application only: HTTP routers, live services, alerts, the map app's adapters. It imports from `core/`; `core/` never imports it (a test checks) |
| `frontend/map/` | The main map app: Headway's web frontend (Apache-2.0), pointed at our routing, tiles and search |
| `frontend/` | The research pages (React, under `/app/`) |
| `research/` | Per-study scripts and notes |
| `results/`, `evidence/` | Summaries, logs and SHA-256 hashes for every number. Large run outputs are on Google Drive (`data/MANIFEST.yaml`, `make fetch-data`) |
| `config/cities/` | One file per city; nothing city-specific lives in code |
| `third_party/SOURCES.md` | Every reused repository: URL, commit, licence, paper, files used |
| `docs/` | `PAPER_MAP.md` (every question in full), `EXPERIMENT_PROTOCOL.md`, `RUNBOOK.md` (run commands and the system's earlier record) |

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
make test                                              # backend and research tests
make fetch-data                                        # bring back the data kept off this machine (public data from its source, our runs from Drive)
PYTHONPATH=.:backend python -m core.ml.forecasting.transfer_dhaka.run summary   # rebuild RQ1's summary from its scores
PYTHONPATH=.:backend python -m core.simulation.ambulance.study summary          # rebuild RQ3's summary from its runs
python scripts/paper_map/build.py && python scripts/readme/build.py            # rebuild docs/PAPER_MAP.md and this README
make app                                               # the web app on http://127.0.0.1:8000
make check && make demo-ambulance                      # offline supervisor demos: also demo-forecast, demo-mesh (docs/DEMO.md)
make present                                           # every feature live, computed now, checked against the thesis (docs/LIVE_RUNS.md)
make demo                                              # the talk's live parts one after another on Enter; make run-routing-quick ARGS="--quick", make sweep-v2x ARGS="--quick"
PYTHONPATH=.:backend python scripts/live_twin/learning_run.py --minutes 180      # the live twin's forecasters over 3 simulated hours (docs/EXPLAIN.md)
```

## The system that applies the research

The web app is the research put to use, and it states which result each feature rests on.
- **Main map** (`/`): Headway's frontend on our Valhalla routing, OpenFreeMap tiles and Photon search, with Bangla turn-by-turn, the nearest hospitals and SOS.
- **Traffic on the map** (Traffic chip): Los Angeles replays recorded METR-LA speeds at the same weekday and time with D2STGNN's forecast made then (measured on every moment of the test weeks: MAE 2.56 / 2.91 / 3.35 mph at 15 / 30 / 60 min against 3.51 / 4.21 / 5.38 for no change, `results/forecasting/layer/summary.json`); Dhaka shows each DhaTraX site at this hour on its one recorded day with RQ1's per-site errors. "Best time to leave" appears only where the model beats no change at every horizon (Los Angeles), so not in Dhaka. Build: `PYTHONPATH=.:backend python -m core.ml.forecasting.layer.build_la`.
- **Research pages** (`/app/lab`): every table above with its sources and caveats; the everyday pages show one plain sentence per result, tagged Simulation, Real recorded or Forecast, with a "How we know" link here.
- **Live twin** (`/app/lab/live-twin`): a running SUMO simulation of the Dhaka corridor, seeded from the clock and labelled Simulation; a click places a crash or starts an ambulance (V2X alert, make-way v2, green signals), a slider changes the demand, and three forecasters (River online, Chronos-Bolt zero-shot, no change) predict each road 15 minutes ahead and are scored live. How it works and what was measured: [`docs/EXPLAIN.md`](docs/EXPLAIN.md).
- **City-agnostic:** every city-specific value lives in `config/cities/<city>.yaml`; a city without data for a feature says so.
- **Privacy:** opt-in only, hashed device IDs, raw positions deleted after 24 hours; alerts and SOS run in TEST mode only.

Run commands, deployment and the system's earlier record are in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Licence

MIT (see `LICENSE`). Reused code keeps its own licence; every source is listed in `third_party/SOURCES.md`.
