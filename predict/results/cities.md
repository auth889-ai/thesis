# City dataset registry — the forecasting stack is not Dhaka-specific

Every city resolves to the same object (values, mask, adjacency, coords, reality label), so the models, the floors and the federated experiment take a `--city` flag and nothing else changes.

| city | present | sensors | bins | span (days) | coverage | quantity | reality | source paper |
|---|---|---|---|---|---|---|---|---|
| METR-LA | yes | 207 | 34272 | 119.0 | 91.9% | speed_mph | **REAL** | Li et al., DCRNN, ICLR 2018 |
| PEMS-BAY | yes | 325 | 52116 | 180.96 | 100.0% | speed_mph | **REAL** | Li et al., DCRNN, ICLR 2018 |
| PEMS04 | no | 307 (expected) | | | | | | Guo et al., ASTGCN, AAAI 2019 |
| PEMS08 | no | 170 (expected) | | | | | | Guo et al., ASTGCN, AAAI 2019 |
| DHAKA-TWIN | yes | 250 | 288 | 1.0 | 84.3% | speed_ms | **SIMULATED** | this project (simulated) |
| DHAKA-LIVE | yes | 6 | 3 | 0.01 | 66.7% | congestion_level | **REAL** | this project (live API) |

Add a city by registering a loader in `predict/city_datasets.py`; no model code changes.

Regenerate: `python predict/city_datasets.py --list`.
