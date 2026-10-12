# Live twin: live forecasting alongside the simulation, with optional steering

**Goal.** A SUMO corridor that keeps running in the web app, labelled SIMULATION, seeded from the clock: the viewer places a crash or
starts an ambulance with a click, moves the demand, and watches three forecasters predict every road's speed 15 minutes ahead and be
scored live. A toggle (off by default) closes the loop and reroutes a share of vehicles on the forecast, SUMO `device.rerouting` style.
Everything below is SIMULATION on RQ2b's corridor demand (DhaTraX counts at two sections, 07:00-08:00) at scale 0.78.

## Pipeline

```
config/cities/dhaka.yaml live_twin: (corridor net, demand file, scale 0.78)     core/common/data/city_config.py:LiveTwin
        │
        ▼  the demand hour repeated 12×; E1 loops generated on every lane of trunk/primary/secondary roads ≥ 50 m (Dhaka: 170 roads, 373 loops)
SUMO 1.27.1 + TraCI, 15 min warm-up at full speed, then 8 simulated s per s         core/simulation/live_twin/{session,demand,detectors}.py
        │
        ├─▶ every simulated minute: road speeds → online (River), Chronos-Bolt-small, no change; scored at m+15 only   core/ml/forecasting/live/online.py
        ├─▶ clicks: crash (nearest car stops), ambulance (RQ2 AmbulanceRun: V2X alert, make-way v2, green signals)   session.py _crash/_ambulance/LiveAmbulance
        ├─▶ steer (off by default): prediction → edge.adaptTraveltime; informed share → rerouteTraveltime             session.py _steer/informed
        │
        ▼  sumo-web3d deltas (creations, changed fields, removals) over a WebSocket
/app/lab/live-twin: deck.gl vehicles on MapLibre, roads coloured by the forecast, uPlot error chart   frontend/src/features/livetwin/
```

## Upstream (`third_party/SOURCES.md`, "Live twin")

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| Eclipse SUMO + TraCI | pip `eclipse-sumo` | 1.27.1 | EPL-2.0 | The running simulation; E1 loops, `setScale`, stops, `adaptTraveltime`, `rerouteTraveltime` |
| sumo-web3d (Sidewalk Labs) | `third_party/sumo-web3d/fetch.sh` (tarball); copy in `core/simulation/live_twin/deltas.py` | `d89fe8014879153d30632996f35b68efb4d8c086` | EPL-2.0 | `deltas.py` copied unchanged with its header; its tests 4 of 4 reproduced (`evidence/live_twin/upstream/`) |
| River | pip 0.26.1 | tag `64285b9d…` | BSD-3-Clause | `StandardScaler` + `LinearRegression` online forecaster; README example reproduced (89.28 % = published) |
| Chronos-Bolt | `amazon/chronos-bolt-small` | revision `772f3d25d38aec6d914c8949dab4462e2d46f5d8` | Apache-2.0 | Zero-shot 15-step forecasts through `BaseChronosPipeline` (same revision as RQ1) |
| deck.gl | npm 9.3.11 | tag `c631a222…` | MIT | `MapboxOverlay` layers; MapLibre example reproduced |
| uPlot | npm 1.6.32 | tag `e995b061…` | MIT | The error chart; basic example reproduced |
| SUMO rerouting docs (`Automatic_Routing.md`, TraCI edge/vehicle state) | sumo `v1_27_1` | `7717f237…` | EPL-2.0 | The steering design follows `device.rerouting` (period, probability, travel-time source) |

## Files

- `core/simulation/live_twin/session.py`: `Session` (49-81), `_prepare` (151-167; bluelight off 157-160), `_run` (169-220), `_minute` (239-244), `_publish` (257-283), `_steer` (283-304), `_do` (312-346), `_crash` (356-370), `_ambulance` (372-390), `LiveAmbulance` (401-430).
- `core/simulation/live_twin/{manager.py (one twin per visitor, at most 3), detectors.py (24-45), demand.py (13-25), deltas.py (upstream)}`.
- `core/ml/forecasting/live/online.py`: `Forecasters.observe` (91-114), Chronos thread (117-135), `_score_and_learn` (150-177).
- `backend/app/live_twin/router.py`: `start` (29-37), `stream` (69-104); `backend/app/platform/ratelimit.py` (visitor, hosted daily limit).
- `frontend/src/features/livetwin/{LiveTwinPage.tsx, liveTwin.ts, ErrorChart.tsx, SteerControl.tsx}`.
- `scripts/live_twin/{learning_run.py, crash_check.py, steer_compare.py}`; `scripts/live/run_twin.py`.
- Tests: `backend/tests/live_twin/test_live_twin.py`, `frontend/src/features/livetwin/liveTwin.test.ts`; browser check `frontend/tests/qa/live_twin.cjs`.

## Commands

    make run-twin                                             # starts the app server if needed, opens /app/lab/live-twin, prints what to do
    make app && open http://127.0.0.1:8000/app/lab/live-twin  # the same by hand (hosted: the same path)
    PYTHONPATH=.:backend python scripts/live_twin/learning_run.py --minutes 180     # one twin, no viewer, forecasters scored → evidence/live_twin/learning_run.json
    PYTHONPATH=.:backend python scripts/live_twin/crash_check.py --twins 20         # 20 twins, one ambulance each, SUMO must not stop
    PYTHONPATH=.:backend python scripts/live_twin/steer_compare.py                  # steering arms × seeds 11-15 → evidence/live_twin/steer_compare.json
    LOCAL_URL=http://127.0.0.1:8011/ node frontend/tests/qa/live_twin.cjs           # the browser check

## Results (every number from `evidence/live_twin/`)

**Learning run** (`learning_run.json`, sha256 `50108ea2…`): seed 1791595594, 180 simulated minutes. Error since the start, km/h:
online 14.33, Chronos-Bolt 13.58, no change 14.58. Over the last 10 scored minutes the online model equals "no change" at minute 29
(18.06 and 18.06) and is below it from about two simulated hours (minute 149: 10.81 against 12.04; minute 179: 13.04 against 13.51).

**Crash check** (`crash_check.json`, sha256 `1d924938…`): 20 twins, 20 distinct seeds, ambulance without the bluelight device:
SUMO stopped 0 of 20, ambulances arrived 20 of 20. **Browser check** (`browser_check.json`): 14 of 14 pass locally.

**Steering** (`steer_compare.json`, sha256 `be0ae1f3…`; seeds 11-15 paired, 30 % informed, window minute 15 to 60, cohort = every
trip that departed in the window, a trip still driving at minute 60 counts its time so far; `docs/QA_PREP.md` §2 has the per-seed table):

| Steering with | Cohort mean trip time, s | Paired difference vs off, s (mean ± sd over seeds) | Seeds better than off |
|---|---|---|---|
| off | 963.7 | — | — |
| current travel times (no forecast) | 1 046.8 | +83.1 ± 98.3 | 1 of 5 |
| no change (last speed) | 932.6 | −31.1 ± 92.2 | 4 of 5 |
| online (River) | 951.9 | −11.8 ± 124.0 | 2 of 5 |
| Chronos-Bolt | 927.5 | −36.2 ± 115.4 | 3 of 5 |

About 64 % of the cohort is still driving at minute 60 in every arm (`summary.off.still_driving_mean` 1 571.8 of about 2 450).

## The finding

**The forecasters run and learn live, but steering on them is not reliably different from not steering.** The online model starts
equal to "no change" and is slightly below it after about two simulated hours; Chronos-Bolt has the lowest error over the one run.
With 30 % of vehicles informed, the mean differences of −36 to −12 s are far inside the spread between seeds (sd 92-124 s), and the
sign changes from seed to seed; rerouting on current travel times is worse on average (+83 s) but with a 95 % interval covering 0.
The corridor is gridlocked (two thirds of trips still in the jam at minute 60), so little free capacity exists to reroute into, which
is consistent with RQ2's "inconclusive against reactive" in Los Angeles. The cause of the sign is not established (`docs/QA_PREP.md`).

## Honest limits

- **No bluelight device** in the twin's ambulance (live twin only; every thesis run keeps it): SUMO 1.27.1's device has a recorded
  segmentation fault on this network (`evidence/emergency/dhaka/sumo_bluelight_crash.json`). Green signals and make-way v2 stay; the
  ambulance no longer runs red lights by itself. The learning run predates this change (it has no ambulance).
- One learning run, one seed; the steering comparison is 5 seeds, one demand level, one informed share; no sweep over share or demand.
- Steering is off by default; `make present` and every saved result are unchanged by it.
- Chronos on the hosted server is optional (`infra/app/setup.sh`, `requirements_chronos.txt`, CPU torch); when it is absent the twin reports
  "Chronos is not installed on this server" (`core/ml/forecasting/live/online.py:44`) rather than leaving the row out silently. A minute in which the previous Chronos call has not
  finished has no Chronos forecast and says so.
- RQ1's graph models (D2STGNN and the others) are tied to METR-LA's 207 sensors and cannot run on these roads.
- A minute in which no vehicle passed a road has no value; it is not filled in. Scores use only road-minutes all three predicted.
- Hosted limits: one twin per visitor, at most 3 simulations on the server, stop after 60 s without a viewer, 10 minutes per twin,
  10 starts per visitor per day.
