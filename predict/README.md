# predict/ — twin sensor data, floors, forecast → SUMO weights

Everything here is **DHAKA_SIMULATED_SENSOR_GRAPH**: simulation on the real frozen R1 network (sha256-checked), never a real measurement. Heavy training (BasicTS GWNet/STID/…) runs on Colab from `data/dhaka_twin/basicts_legacy/`.

| command | output |
|---|---|
| `python predict/make_twin_dataset.py --hours 8 --seeds 11,12,13 --scale 0.15 --place-by-flow` (smoke: `--hours 2 --seeds 11 --out predict/data/dhaka_twin_smoke`) | `data/dhaka_twin/{data.npz (T×250×5: speed_ms, flow_veh, occupancy_pct, tod, dow; mask; seed_index), adj_mx.pkl, sensor_nodes.json, sensor_graph_data.npz, MANIFEST.json (label + sha256 of every file + per-seed wall/teleports/coverage), basicts_legacy/ (data.dat, desc.json, adj_mx.pkl @ BasicTS 4c3e2d3), basicts_v1/}` — demand = the routing scenario's DUE pulse tiled every 600 s; each seed = one independent replay ("day") of the same window. **Scale 0.15 is the accepted 8-hour sensor-data scale.** The route harness separately uses `route/results/SCALE_CHOICE.json` for its 2-hour paired-seed experiments. **Acceptance gate** (every seed: insertion ≥ 0.95, teleports ≤ `--max-teleport-frac` = 1 % of inserted) → `MANIFEST.acceptance.verdict` PASS/FAIL, exit code 2 on FAIL; higher sensor-data scales gridlock R1 over longer windows — sweep in `MANIFEST.scale_sweep_note`. **`--place-by-flow [edgedata.xml]`** places the 250 sensors on the top-250 edges by vehicle count (`entered`) in the longest complete `route/results/static_s11_h*/edgedata.xml`; policy + source sha256 in `MANIFEST.sensor_placement`; DCRNN adjacency recipe unchanged |
| `python predict/baselines_twin.py [--data … --out … --channel speed_ms]` | `results/twin_floors.{json,md}`: persistence + historical-average MAE/RMSE at 5/15/30/60 min, chronological 70/10/20 split (same `ChronoSplit` sha256 as every BasicTS model), test region, validity-masked, no cross-seed pairs |
| `python predict/forecast_to_weights.py --source oracle --edgedata route/results/static_s11_h900/edgedata.xml --out route/weights/oracle_s11.xml` (or `--seeds 11,12,13 --horizon 3600`) | SUMO `<meandata><interval><edge traveltime/>` XML for `route/predictive_routing.py --arm predictive --weights …` (oracle = the static run's own truth = upper bound) |
| `python predict/forecast_to_weights.py --source persistence --lag 300 --edgedata … --out …` | same format; interval [b,e) carries what was measured in [b−lag,e−lag) (no-model forecast) |
| `python predict/forecast_to_weights.py --source model --pred pred.npz --sensor-nodes data/dhaka_twin/sensor_nodes.json --horizon-min 15 --t0 3900 --out …` | same format from a BasicTS speed prediction (T×N or T×H×N): traveltime = length/speed on the 250 sensor edges only (others free-flow); `--horizon-min h` writes each interval from the forecast issued h min earlier → horizon ablation |
| `python predict/pull_colab_results.py --drive <mounted-Drive>/dhakaflow/predict` | copies only `benchmark.csv` and `benchmark.md` from Colab/Drive into `predict/results/` |

## Colab Pro training runner

The notebook is generated from `notebooks/build_predict_basicts_colab.py` and
uploaded to `gdrive2tb:dhakaflow/predict/Predict_BasicTS_Colab.ipynb`.
Open it in Colab at:

`https://colab.research.google.com/drive/1dHhN6ET_LmpqqKIwo_He_2N3Fd7ehuM6`

It uses the BasicTS legacy fair-comparison pin
`4c3e2d373c647667c2123e1591f2d79c229dfcc6`, because that is the pinned layout
containing `baselines/STID`, `baselines/GWNet`, `baselines/DCRNN`,
`baselines/AGCRN`, and `baselines/STAEformer`.

Drive state:

- `gdrive2tb:dhakaflow/predict/raw_data/METR-LA/` exists but currently only
  has `adj_METR-LA.pkl`; the notebook will try the official DCRNN Google Drive
  folder for `METR-LA.h5`.
- `gdrive2tb:dhakaflow/predict/raw_data/PEMS-BAY/` exists but currently only
  has `adj_PEMS-BAY.pkl`; the notebook will try the official DCRNN Google Drive
  folder for `PEMS-BAY.h5`.
- `gdrive2tb:dhakaflow/predict/dhaka_twin/basicts_legacy/` contains the small
  Dhaka R1 BasicTS export for later custom-Dhaka runs.

First run stays one pair: `TARGET_MODEL = 'STID'`,
`TARGET_DATASET = 'METR-LA'`, `RUN_ALL_READY_PAIRS = False`.

Notes: unlisted edges fall back to free-flow in SUMO; speed NaN (no vehicle sampled) is kept NaN in `data.npz` with `mask=False` and filled 0.0 (= BasicTS NULL_VAL) only in the BasicTS exports; BasicTS exports use `period_steps = bins_per_seed` (tod = fraction of the simulated window, day = seed index). Reuses `research/twin/sensor_graph.py`, `research/twin/demand.py`, `research/forecasting/{baselines,basicts_adapter}.py` unchanged.
