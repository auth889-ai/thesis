# Forecasting: RQ1 comparison, the Model Lab and the map's forecast layer

**Goal.** Say honestly how far ahead road speeds can be predicted, in a city with months of loop-detector history (Los Angeles,
San Francisco Bay Area) and in one with a single recorded day per site (Dhaka), with the published models run through their own
code; then let anyone compute one forecast now (Model Lab) and see the sensors coloured on the map (forecast layer). Every number
is checked against RQ1's saved windows.

## Pipeline

```
METR-LA / PEMS-BAY (OpenCity's npz, DCRNN release)       DhaTraX (Dhaka: 3 camera sites, one day each)
        │                                                        │
        ▼  research/forecasting_rq1/scripts/00_reproduce.sh      ▼  core/ml/forecasting/transfer_dhaka/*
each upstream's own example reproduced first                  zero-shot only (nothing to train on)
(evidence/forecasting/reproduce/SUMMARY.json)
        │
        ▼  01_protocol_b.sh: BasicTS's official configs, seeds 11/23/37, horizons 15/30/60 min, masked MAE/RMSE/MAPE
6 graph models + Chronos-2 + Chronos-Bolt + TimesFM 2.5 + XGBoost + random forest + persistence + historical average
        │
        ▼
results/forecasting/rq1/summary.md  (the thesis table)       results/forecasting/protocol_b/METR-LA_test_w120_n207_s*.npz (saved windows)
        │                                                        │
        ▼ Model Lab (computed now)                               ▼ forecast layer (saved files, replayed)
core/ml/forecasting/layer/lab.py: one sensor, one moment,    core/ml/forecasting/layer/build_la.py → results/forecasting/layer/
one model, through RQ1's predict_checkpoints; rq1_check      summary.json; stops if any window differs from RQ1 by > 1e-3
```

## Upstream (`third_party/SOURCES.md`, "Forecasting comparison, RQ1" and "Model Lab on the hosted app")

| What | Where | Commit / version | Licence | How it is used |
|---|---|---|---|---|
| BasicTS (legacy fair-comparison branch) | `~/.dhakaflow/upstream/BasicTS_legacy` | `4c3e2d373c647667c2123e1591f2d79c229dfcc6` | Apache-2.0 | Official architectures, configs and masked metrics, unchanged (`CFG.EVAL.HORIZONS = [1, 3, 6, 12]` recorded per run); DCRNN's `random.randint` fixed in memory only (`infer_from_checkpoint.py:80-84`) |
| Chronos / Chronos-Bolt | pip `chronos-forecasting` 2.3.1; weights `amazon/chronos-bolt-small` rev `772f3d25…`, `amazon/chronos-2` | tag `v2.3.1` = `7dc44357…` | Apache-2.0 | Zero-shot through `BaseChronosPipeline`; its own `evaluate.py` reproduced first (see Results) |
| TimesFM 2.5 | pip `timesfm` 3.0.2, checkout `e51928e2…`, weights rev `1d952420…` | as left | Apache-2.0 (weights up to 2.5; 3.0 weights not used) | Zero-shot; its own example reproduced to 7e-7 |
| OpenCity | `~/.dhakaflow/upstream/OpenCity` | `eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f` | MIT | Its `METR_LA.npz` as released (sha256 `0061438a…`); the checkout keeps one edited config line from an unrestored run (`pretrain.conf`), recorded in `core/ml/forecasting/README.md` |
| DhaTraX | Zenodo 10.5281/zenodo.22157752, v1.0 | checksummed files | see SOURCES.md:125 | Dhaka's three recorded site-days |

## Files

- `core/ml/forecasting/evaluation/protocol_b/*`: data loading, persistence baseline, scoring (the RQ1 protocol).
- `core/ml/forecasting/evaluation/checkpoint_stage.py`: `predict_checkpoints` (z-score on the first 70 %, future zeroed, 65-94).
- `core/ml/forecasting/infer_from_checkpoint.py`: loads BasicTS's own config and checkpoint (`load_official_cfg` 53-87).
- `core/ml/forecasting/transfer_dhaka/*`: the Dhaka zero-shot runs and the summary.
- `core/ml/forecasting/layer/{lab.py,build_la.py,service.py}`: Model Lab (`run` 62-99, `rq1_check` 84-93), layer build (66-73 stop rule), layer service (`best_time` 47-57, Dhaka `recorded_day` 88-115).
- `backend/app/forecasting/routers/layer.py`: `/api/model-lab/run` (44-55), `/api/forecast/layer` (13-25).
- `frontend/src/features/forecast/ModelLabPage.tsx`; `frontend/map/src/traffictwin/TtForecast.vue` (map chip).
- Results: `results/forecasting/rq1/summary.md` (sha256 `c1e2ead3…`), `results/forecasting/layer/summary.json`, `evidence/forecasting/reproduce/SUMMARY.json`.

## Commands

    make run-forecast ARGS="--sensor 5 --at 2012-06-05T08:30 --model D2STGNN"   # LIVE: one forecast computed now, THESIS CHECK against RQ1's window
    open http://127.0.0.1:8000/app/lab/model-lab                               # the same in the browser (also hosted; warm-up at start)
    research/forecasting_rq1/scripts/00_reproduce.sh && research/forecasting_rq1/scripts/01_protocol_b.sh   # the RQ1 pipeline
    python -m core.ml.forecasting.layer.build_la                               # the Los Angeles forecast layer from saved windows

## Results (`results/forecasting/rq1/summary.md`; mean over seeds 11/23/37, 60-minute horizon)

| City, dataset | Best model | MAE | Persistence ("no change") | Best zero-shot |
|---|---|---|---|---|
| Los Angeles, METR-LA (mph) | D2STGNN | **3.779 ± 0.415** | 6.506 ± 0.372 | Chronos-2, all roads together 6.343 |
| SF Bay Area, PEMS-BAY (mph) | STID | **1.234 ± 0.123** | 2.05 ± 0.432 | Chronos-2, all roads together 1.959 |
| Dhaka, DhaTraX (km/h, 3 sites) | Chronos-2 zero-shot | 2.877 ± 0.43 | **2.717 ± 0.674** | (no model beats persistence at 60 min) |

Dhaka at shorter horizons: 15 min Chronos-Bolt-small 2.225 against persistence 2.385 (better); 30 min Chronos-2 2.41 against 2.623 (better).
Unseen city: XGBoost trained on METR-LA scores 2.76 mph on PEMS-BAY against 2.35 trained there (17.4 % worse); on Dhaka it is 72.7 % worse than persistence.

Upstream reproduced first (`evidence/forecasting/reproduce/SUMMARY.json`): Chronos-Bolt's own `evaluate.py` on exchange_rate MASE 1.77722 vs published 1.77484, WQL 0.01133 vs 0.01136 (pass); monash_hospital WQL 0.05812 = published, MASE 0.80083 vs 0.69545 (not reproduced; cause not found, recorded). TimesFM's own example: max difference 7e-7 (pass).

Live checks: `make run-forecast` in the last `make present` (`evidence/live_runs/present_20261011_095038/forecast.log`): sensor 717445, D2STGNN, 2012-06-07 14:30, largest difference from RQ1's window 0.00e+00 mph → REPRODUCED. Forecast layer `rq1_check`: 120 windows, max difference 0.0 mph; card skill at 15/30/60 min 0.268 / 0.308 / 0.377 (`results/forecasting/layer/summary.json`). Hosted Model Lab calls 0.48 s and 0.47 s after warm-up (`evidence/hosting/2026-10-10/load_twin_modellab.txt`).

## The finding

**Trained graph models win where there is history; in Dhaka only zero-shot models can run, and an hour ahead none beats "no change".**
In Los Angeles D2STGNN roughly halves persistence's 60-minute error; the Bay Area is smoother and every model is better there. Dhaka's
speeds jump (6.5-13.1 % of 5-minute steps change by more than 30 % of free-flow, against 0.7 % on a median METR-LA sensor-day), and
each site has one recorded day, so nothing can be trained; the foundation models help a little at 15 and 30 minutes and not at 60.
A model moved from Los Angeles unchanged loses 17.4 % in the Bay Area and fails in Dhaka. The app shows a "best time to leave" only
where a model has skill, which is Los Angeles.

## Honest limits

- The six graph models are fixed to METR-LA's 207 sensors; they cannot run on Dhaka's roads or in the live twin.
- Dhaka has no recorded speed series beyond DhaTraX's three site-days; the Dhaka rows are 3 sites, one day each, zero-shot only.
- The Model Lab is open loop and the map's forecast layer replays saved files; the only closed loop is RQ2's Los Angeles twin
  (`core/simulation/closed_loop/`), which was inconclusive against reactive rerouting and was not run in Dhaka.
- Chronos-Bolt's published monash_hospital MASE was not reproduced (WQL was); Chronos-2 has no published number reproduced by us.
- OpenCity's checkout carries one edited config line from an unrestored run; the npz we read is as released.
- On a single Model Lab window "no change" can win (it does on the window above at 15 and 30 min); the thesis number is the average.

## Live demo (Part D, 2026-10-12): `make gui-routing`, the RQ2 forecast-routing loop in sumo-gui

    make gui-routing                                          # LA twin, seed 201, ideal link, 15 simulated minutes after the fork (scripts/live/gui_routing.py)
    make gui-routing ARGS="--profile its-g5 --minutes 30 --delay 20"
    make gui-routing ARGS="--no-gui"                          # headless, same printouts

The loop (`core/simulation/closed_loop`: Graph WaveNet checkpoint, residual correction, decision rules, V2X channel) runs unchanged through its own
hooks; the script only colours and prints. **Connected cars (30 %) yellow, others white; a car flashes green for a second when its uplink
status is delivered; blue for the rest of the run once a delivered reroute is applied; a red flash when a downlink to it is lost.** Each 300 s
round draws **translucent red polygons on the edges whose corrected forecast speed is below 50 % of the speed limit** (from that round's own
`edge_cost_table.json`) and clears the previous round's. One terminal line per round, also shown on a label in the window: sim time, round,
uplink delivered / lost, the forecast's mean absolute error at 15 min against the recorded METR-LA values (mph, over the mapped sensors),
the decisions as the loop counted them (REROUTE / KEEP / NO_ALTERNATIVE / REJECTED_CAPACITY), downlink delivered / lost, reroutes applied.
At the end the script checks that its counters equal the loop's own message log and reroute count (`CHECK … SAME`;
test `tests/platform/test_gui_routing.py`). Profiles `its-g5` and `c-v2x` are registered at run time from the thesis's radio model (latency,
loss, lifetime; `scripts/routing/run_profile.py`). What is real: the OpenStreetMap network, METR-LA's recorded speeds (the forecast's input
and the error's reference), the trained checkpoint. What is simulated: the vehicles (8x peak demand, generated), the radio link, the reroutes.
Fallback: `--no-gui` prints the same lines; a shorter `--minutes 5` gives one round in about 30 s.
