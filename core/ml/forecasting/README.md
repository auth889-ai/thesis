# core/ml/forecasting — traffic forecasting and its transfer to Dhaka (RQ1)

**RQ1:** do traffic forecasting models built on Western loop-detector data (METR-LA, PEMS-BAY) beat "no change"
(persistence) on Dhaka's recorded speeds, and why does Dhaka differ? This folder also holds the model adapters,
training harnesses (local and AWS), evaluation protocols and federated experiments that the app and RQ2 use. Result
files keep their earlier path (`results/forecasting/rq1/`).

## Papers and official repositories
From `third_party/SOURCES.md` ("Forecasting model", "Forecasting comparison, RQ1") and `results/upstream/REPRODUCTIONS.json`.

| Paper (venue) | Repository and version | Licence |
|---|---|---|
| Chronos: Ansari et al., TMLR 2024; Chronos-2: arXiv:2510.15821 (2025) | amazon-science/chronos-forecasting, `v2.3.1` = `7dc4435706a4454feb79df44ca9f33631f3027bf`. Weights `amazon/chronos-2` rev `29ec3766…`; `amazon/chronos-bolt-small` rev `772f3d25…`. Evaluation from checkout `8589d1988e9676817548e9626738ff06b6ca6370` | Apache-2.0 |
| TimesFM: Das, Kong, Sen, Zhou, ICML 2024 (2.5 is the 2025 release) | google-research/timesfm, checkout `e51928e27119cb17bebc005be2696b75e0a9e688`; weights `google/timesfm-2.5-200m-pytorch` rev `1d952420…` | Apache-2.0 (code and weights up to 2.5; 3.0 weights not used) |
| BasicTS: Shao et al., IEEE TKDE 2024 | GestaltCogTeam/BasicTS (legacy), `4c3e2d373c647667c2123e1591f2d79c229dfcc6` | Apache-2.0 |
| Graph WaveNet, STID, STAEformer (trained through BasicTS) | same BasicTS commit; STAEformer's own repo is pinned in `upstream/UPSTREAM_PINS.yaml` | see BasicTS |
| OpenCity: Li et al. 2024, arXiv 2408.10269 | HKUDS/OpenCity, `eca64c9d9c65ff803d0f9d02c65e2544a0d2e96f` (REPRODUCTIONS.json) | MIT (third_party/SOURCES.md, "Model Lab on the hosted app") |
| PatchSTG: Fang et al., SIGKDD 2025 (arXiv 2412.09972) | https://github.com/LMissher/PatchSTG @ `8b298b230227a304a082e05241c69dca3740a73d` | Code MIT; the authors' pre-processed LargeST data and weights: licence not stated (third_party/SOURCES.md) |
| CNFGNN (KDD 2021), FedGTP (KDD 2024) | `mengcz13/KDD2021_CNFGNN` `505660846e04…`; `LarryHawkingYoung/KDD2024_FedGTP` `ff128f5bed77…` (REPRODUCTIONS.json, NOT_ATTEMPTED) | not recorded in third_party/SOURCES.md |
| Data: METR-LA, PEMS-BAY (DCRNN release, Li et al., ICLR 2018); DhaTraX v1.0 (Roy, Zenodo) | DCRNN `602afd9d767d3aa1c9b3eac51710d6aeee12c227`; DhaTraX DOI 10.5281/zenodo.22157752 | MIT; CC BY 4.0 |

## Which file implements which part
| File / folder | Part |
|---|---|
| `transfer_dhaka/run.py` | RQ1 end to end, one stage at a time, each writing its own JSON under `results/forecasting/rq1/`. |
| `transfer_dhaka/baselines.py` | The weekday-aware historical average: the mean speed per road at the same time of day. |
| `transfer_dhaka/metrics.py` | BasicTS's masked MAE, RMSE and MAPE, loaded unchanged from the pinned checkout. |
| `transfer_dhaka/dhaka.py` | Dhaka's recorded days: one day per DhaTraX camera site, 5-minute median speeds. |
| `transfer_dhaka/transfer.py` | The unseen-city test: models trained on one Western city, run on another. |
| `transfer_dhaka/character.py` | Why Dhaka differs, measured from the data (jumps, variability). |
| `transfer_dhaka/summary.py` | Tables (mean ± sd over seeds), figures, and "The finding" / "Why" sentences computed from the stage files. |
| `adapters/` | One interface for every model: Chronos, checkpoints (Graph WaveNet, STID, STAEformer), OpenCity, and labelled arithmetic baselines. |
| `evaluation/` | Protocol B (`checkpoint_stage.py`, `foundation_stage.py`, `protocol_b/`), floors, conformal intervals, and the recorded backtest. |
| `training/` | BasicTS training on a city's own data; PatchSTG through the authors' code (`patchstg_official.py`, resumable `patchstg_resume.py`); AWS spot jobs (`aws/`). |
| `opencity/` | OpenCity's own harness and released weights run on our cities, without editing their source. |
| `federated/` | Federated forecasting under a simulated V2X link; a thin impairment adapter around official FedGTP. |
| `operations/`, `live/` | What the app serves: section forecasts, departure advice, the model registry, live capture and backtests. |

## Substitutions and why
- **Zero-shot foundation models are run as released**, one series at a time; nothing is fine-tuned.
- **BasicTS configs: one change**, `CFG.EVAL.HORIZONS = [1, 3, 6, 12]`, recorded per run.
- **OpenCity under a modern NumPy** through a boot shim (`opencity/_opencity_boot.py`), with no source line edited. One configuration
  value the authors tell users to set, `dataset_use` in `conf/general_conf/pretrain.conf`, is set per city by `opencity/opencity_city_eval.py`
  and restored afterwards. **The pinned checkout on this laptop still holds the value of a run that did not restore it** (found in the
  audit of 2026-10-10; file dated 2026-09-06 04:01): `dataset_use = ['PEMS07M']` (upstream) → `dataset_use = ['DF_METR_LA_R5']`. Restore with
  `git -C ~/.dhakaflow/upstream/OpenCity checkout conf/general_conf/pretrain.conf`. METR-LA and PEMS-BAY are in its pre-training corpus, so they cannot support a zero-shot claim.
- **Dhaka has three camera sites with one day each.** The authors did not validate the camera calibration.

## Reproduced first (`results/upstream/REPRODUCTIONS.json`)
| Model | Dataset | Metric | Published | Ours | Verdict |
|---|---|---|---|---|---|
| Graph WaveNet | METR-LA | MAE@15min | 2.69 | 2.719 | REPRODUCTION_PASS |
| Graph WaveNet | PEMS-BAY | MAE@15min | 1.3 | 1.3083 | REPRODUCTION_PASS |
| OpenCity-plus | PEMS07M (zero-shot) | MAE | 4.5 | 4.5 | REPRODUCTION_PASS |

Also:
- STID and STAEformer: REFERENCE_UNKNOWN (published value not yet read out of the paper).
- CNFGNN and FedGTP: NOT_ATTEMPTED.
- Chronos-Bolt: reproduced with the repository's own `evaluate.py` (`evidence/forecasting/reproduce/`).
- PatchSTG on LargeST: `results/forecasting/patchstg_largest.json`.

## Tests
| File | What it checks |
|---|---|
| `backend/tests/forecasting/test_rq1.py` | RQ1 building blocks on toy series with known answers. |
| `backend/tests/forecasting/test_forecast_adapters.py` | A baseline is never presented as the model; adapters refuse cities they cannot serve. |
| `backend/tests/forecasting/test_recorded_backtest.py` | Model and persistence are scored on the same pairs; no gap is filled. |
| `backend/tests/forecasting/test_patchstg_official.py`, `test_patchstg_resume.py`, `test_largest_job.py` | The authors' config is translated exactly; resumed training ends where an uninterrupted run ends; the job reads only the authors' printed metric. |
| `backend/tests/forecasting/test_training_watchdog.py` | The hang watchdog fires on a silent log, not on a growing one. |
| `backend/tests/rebuild/test_basicts_train.py`, `test_opencity_city_eval.py`, `test_federated.py` | Training through the pinned BasicTS harness; OpenCity's own gates; FedAvg and byte accounting. |
| `backend/tests/federated/test_v2x_impairment.py`, `test_summarise_impairment.py` | The impairment adapter, and the impairment table's arithmetic. |
| `tests/platform/test_p3_baselines.py`, `test_p3_basicts_adapter.py` | Split hygiene, masked metrics and the leakage guard; BasicTS export format. |

## Results
- Summary: `results/forecasting/rq1/summary.json` and `summary.md`.
- One line of its `findings.lab`, verbatim: "Dhaka (DhaTraX, three camera sites, one day each), the best model other than persistence: at 15 minutes Chronos-Bolt-small (zero-shot) 2.225 km/h against persistence 2.385 (better); at 30 minutes Chronos-2 (zero-shot) 2.41 km/h against persistence 2.623 (better); at 60 minutes Chronos-2 (zero-shot) 2.877 km/h against persistence 2.717 (not better)."
- Caveats are in the same file (`caveats`).
