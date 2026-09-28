# References

Every external research artifact the TrafficTwin code uses, with the files that use it. Generated from `docs/references.json` (`python -m app.api.references`); the same data is served at `/api/references` and shown on the References page of the web application.

## A · Traffic forecasting (ML / DL)

1. **Graph WaveNet for Deep Spatial-Temporal Graph Modeling** — Wu, Z., Pan, S., Long, G., Jiang, J., Zhang, C.. *IJCAI 2019*, 2019. DOI 10.24963/ijcai.2019/264 · https://arxiv.org/abs/1906.00121
   Used for: The canonical forecaster: 207-node METR-LA checkpoint, verified against the published MAE, drives every predictive arm of the closed loop.
   Code: nnzhan/Graph-WaveNet (pinned in upstream/UPSTREAM_PINS.yaml); trained through BasicTS
   Files: `backend/app/forecasting/service.py`, `backend/app/forecasting/evaluation/benchmark_floors.py`, `backend/app/protocols/learned_gate.py`, `src/pipeline/v2x/closed_loop.py`

2. **Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting** — Li, Y., Yu, R., Shahabi, C., Liu, Y.. *ICLR 2018*, 2018. https://arxiv.org/abs/1707.01926
   Used for: Source of the METR-LA and PEMS-BAY releases, the Gaussian-kernel sensor graph, the chronological 70/10/20 split and the published Historical-Average floors.
   Code: liyaguang/DCRNN (pinned)
   Files: `src/pipeline/adapters/twin/sensor_graph.py`, `backend/app/data/datasets.py`, `backend/app/forecasting/evaluation/benchmark_floors.py`

3. **Exploring Progress in Multivariate Time Series Forecasting: Comprehensive Benchmarking and Heterogeneity Analysis** — Shao, Z., Wang, F., Xu, Y., et al.. *IEEE TKDE 2024*, 2024. https://arxiv.org/abs/2310.06119
   Used for: BasicTS is the training and evaluation harness for Graph WaveNet, DCRNN, STID and STAEformer; no per-model training loop is written in this repository.
   Code: GestaltCogTeam/BasicTS (two pins)
   Files: `src/pipeline/adapters/forecasting/basicts_adapter.py`, `backend/app/forecasting/training/basicts_train.py`, `backend/app/forecasting/configs/benchmark.yaml`

4. **Spatial-Temporal Identity: A Simple yet Effective Baseline for Multivariate Time Series Forecasting** — Shao, Z., Zhang, Z., Wang, F., Wei, W., Xu, Y.. *CIKM 2022*, 2022. https://arxiv.org/abs/2208.05233
   Used for: Benchmark model run under the same protocol (Phase-1 gate G3).
   Files: `backend/app/forecasting/training/basicts_train.py`, `backend/app/forecasting/evaluation/comparison_table.py`

5. **STAEformer: Spatio-Temporal Adaptive Embedding Makes Vanilla Transformer SOTA for Traffic Forecasting** — Liu, H., Dong, Z., Jiang, R., et al.. *CIKM 2023*, 2023. https://arxiv.org/abs/2308.10425
   Used for: Benchmark model, and the source of the one-protocol leaderboard the comparison table is checked against.
   Files: `backend/app/forecasting/evaluation/comparison_table.py`

6. **Chronos: Learning the Language of Time Series** — Ansari, A. F., Stella, L., Turkmen, C., et al.. *Transactions on Machine Learning Research 2024*, 2024. https://arxiv.org/abs/2403.07815
   Used for: Pretrained zero-shot univariate forecaster offered for cities with only a short recorded corridor history (Dhaka); kept pretrained, never retrained; its negative result is reported.
   Code: amazon-science/chronos-forecasting (pinned), weights amazon/chronos-bolt-small
   Files: `backend/app/forecasting/adapters/chronos_adapter.py`, `backend/app/forecasting/adapters/registry.py`

7. **OpenCity: Open Spatio-Temporal Foundation Models for Traffic Prediction** — Li, Z., Xia, L., Shao, Z., et al.. *arXiv 2024*, 2024. https://arxiv.org/abs/2408.10269
   Used for: Cross-city foundation-model comparison; its pre-training corpus decides which cities may be called zero-shot.
   Code: HKUDS/OpenCity (pinned)
   Files: `backend/app/forecasting/opencity/opencity_crosscity.py`, `backend/app/forecasting/adapters/opencity.py`

8. **XGBoost: A Scalable Tree Boosting System** — Chen, T., Guestrin, C.. *KDD 2016*, 2016. DOI 10.1145/2939672.2939785
   Used for: Classical non-deep baseline on the same chronological split (with scikit-learn RandomForest).
   Files: `backend/app/forecasting/training/research_baselines.py`

9. **Scikit-learn: Machine Learning in Python** — Pedregosa, F., et al.. *JMLR 12:2825–2830*, 2011. https://jmlr.org/papers/v12/pedregosa11a.html
   Used for: RandomForest baseline and metric utilities.
   Files: `backend/app/forecasting/training/research_baselines.py`

10. **Attention Based Spatial-Temporal Graph Convolutional Networks for Traffic Flow Forecasting** — Guo, S., Lin, Y., Feng, N., Song, C., Wan, H.. *AAAI 2019*, 2019. DOI 10.1609/aaai.v33i01.3301922
   Used for: Provenance of the PEMS04 / PEMS08 releases used in the cross-city corpus bookkeeping.
   Files: `backend/app/data/city_datasets.py`

11. **Cross-Node Federated Graph Neural Network for Spatio-Temporal Data Modeling** — Meng, C., Rambhatla, S., Liu, Y.. *KDD 2021*, 2021. https://arxiv.org/abs/2106.05223
   Used for: Reference federated forecaster that the V2X-impairment study degrades.
   Files: `backend/app/forecasting/federated/federated_forecast.py`

12. **Communication-Efficient Learning of Deep Networks from Decentralized Data** — McMahan, H. B., Moore, E., Ramage, D., Hampson, S., Agüera y Arcas, B.. *AISTATS 2017*, 2017. https://arxiv.org/abs/1602.05629
   Used for: The FedAvg aggregation rule implemented in the federated forecast.
   Files: `backend/app/forecasting/federated/federated_forecast.py`

13. **STGCN, MTGNN, GTS, GMAN, STNorm, PDFormer, AGCRN, HI (published METR-LA / PEMS-BAY numbers)** — various. *as re-run under one protocol by STAEformer (Liu et al., CIKM 2023, Table 1)*, 2023. https://arxiv.org/abs/2308.10425
   Used for: Leaderboard context only: their published MAE values appear in the comparison table; none of these models runs here. *(context only — quoted numbers, no code runs here)*
   Files: `backend/app/forecasting/evaluation/comparison_table.py`

## Datasets and road data

1. **METR-LA — 207 loop detectors, Los Angeles, 5-minute speeds, March–June 2012** — released with DCRNN (Li et al., ICLR 2018). *github.com/liyaguang/DCRNN*, 2018. https://github.com/liyaguang/DCRNN
   Used for: The only dataset the headline forecast claim rests on; the 207-node checkpoint is validated on its held-out split. Speed-only: no flow counts, so SUMO demand cannot be calibrated from it (src/pipeline/v2x/METR_LA_FLOW_NOTE.md).
   Files: `data/forecasting/cities/METR-LA/`, `backend/app/data/datasets.py`, `backend/app/twin/sensor_map.py`

2. **PEMS-BAY — 325 detectors, Bay Area, 5-minute speeds** — released with DCRNN (Li et al., ICLR 2018). *github.com/liyaguang/DCRNN*, 2018. https://github.com/liyaguang/DCRNN
   Used for: Second benchmark city for the forecasting gate.
   Files: `backend/app/data/datasets.py`, `backend/app/forecasting/evaluation/benchmark_floors.py`

3. **UTD19 — Understanding traffic capacity of urban networks** — Loder, A., Ambühl, L., Menendez, M., Axhausen, K. W.. *Scientific Reports 9, 16283 (paper); ETH Research Collection (data)*, 2019. DOI 10.1038/s41598-019-51539-5 · data DOI 10.3929/ethz-b-000437802
   Used for: Traffic-science foundation: flow, occupancy, accumulation, production and the macroscopic fundamental diagram carried into the platform's invariants and units.
   Files: `src/pipeline/core/evaluation/traffic_science.py`, `src/pipeline/core/common/units.py`, `paper_labs/00_utd19/`

4. **OpenStreetMap, queried through the Overpass API** — OpenStreetMap contributors. *ODbL 1.0*, 2026. https://www.openstreetmap.org/copyright
   Used for: Road network of every simulated city (Dhaka R1, the four Los Angeles corridors): netconvert with the OSM typemap, left-hand traffic for Dhaka.
   Files: `backend/app/twin/scenario_builder.py`, `backend/app/datasets/city_corridors.py`, `paper_labs/02_dhaka_osm/`

5. **Nominatim geocoder (OpenStreetMap)** — OpenStreetMap contributors. *https://nominatim.org — usage policy: 1 request/s, attribution required*, 2026. https://operations.osmfoundation.org/policies/nominatim/
   Used for: Free-text origin and destination → coordinates for the trip analysis; falls back to the built-in place list.
   Files: `backend/app/routing/trip_analysis.py`

6. **Traffic-related tweets dataset (with Dabiri & Heaslip, 'Developing a Twitter-based traffic event detection model using deep learning architectures', ESWA 2019)** — Dabiri, S., Heaslip, K.. *Mendeley Data, CC BY 4.0*, 2018. DOI 10.17632/c3xvj5snvv.1
   Used for: Training data for the incident / congestion text classifier (off the canonical closed-loop path).
   Files: `backend/app/nlp/get_data.py`, `backend/app/nlp/train_classifier.py`

## B · Networking and V2X

1. **Modeling an ITS Management Solution for Smart Highways with Eclipse MOSAIC** — Schrab, K., Protzmann, R., Radusch, I.. *IEEE Access 10:82007–82019*, 2022. DOI 10.1109/ACCESS.2022.3193765
   Used for: Eclipse MOSAIC 25.2 is the only empirical grounding of the V2X latency and loss profiles: the official Barnim example was reproduced and its ITS-G5 latency distribution feeds the `mosaic` channel profile; the Dhaka R1 penetration sweep (DENM tx/rx, delivery ratio) runs in MOSAIC.
   Code: eclipse-mosaic/mosaic 25.2 @005fa1f3 (EPL-2.0)
   Files: `src/pipeline/networking/`, `backend/app/networking/channel.py`, `src/pipeline/adapters/networking/v2x_bus.py`

2. **ETSI EN 302 663 — Intelligent Transport Systems (ITS); ITS-G5 Access layer specification for Intelligent Transport Systems operating in the 5 GHz frequency band** — ETSI. *ETSI standard*, 2020. https://www.etsi.org/deliver/etsi_en/302600_302699/302663/
   Used for: The ITS-G5 access layer that MOSAIC's ad-hoc (SNS) channel model represents; every latency number labelled ITS-G5 in this project inherits that model, not a radio measurement.
   Files: `src/pipeline/networking/README.md`, `backend/app/networking/channel.py`

3. **ETSI EN 302 637-2 — ITS; Vehicular Communications; Basic Set of Applications; Part 2: Specification of Cooperative Awareness Basic Service (CAM)** — ETSI. *ETSI standard*, 2019. https://www.etsi.org/deliver/etsi_en/302600_302699/30263702/
   Used for: The periodic vehicle status uplink (VEHICLE_STATUS every 10 s) is the project's simplified analogue of the CAM service.
   Files: `src/pipeline/v2x/closed_loop.py`

4. **ETSI EN 302 637-3 — ITS; Vehicular Communications; Basic Set of Applications; Part 3: Specifications of Decentralized Environmental Notification Basic Service (DENM)** — ETSI. *ETSI standard*, 2019. https://www.etsi.org/deliver/etsi_en/302600_302699/30263703/
   Used for: The hazard broadcast (DENM, 1 Hz re-broadcast, geocast radius) in the MOSAIC penetration sweep; ROUTE_RECOMMENDATION with a TTL follows the same expiry idea.
   Files: `backend/app/networking/mosaic/penetration_sweep.py`, `backend/app/networking/mosaic/latency_injection.py`

5. **Simulated V2X channel (this project)** — TrafficTwin. *deterministic emulator: latency, jitter, loss, TTL, penetration by seeded hash*, 2026. 
   Used for: Explicitly a SIMULATED V2X EMULATOR, not radio hardware and not a 5G / DSRC stack; profiles ideal, mosaic, lat100…lat5000, loss05…loss20, degraded.
   Files: `backend/app/networking/channel.py`, `research/networking/channel_sweep.py`

## C · Traffic simulation and control (digital twin)

1. **Microscopic Traffic Simulation using SUMO** — Alvarez Lopez, P., Behrisch, M., Bieker-Walz, L., Erdmann, J., Flötteröd, Y.-P., Hilbrich, R., Lücken, L., Rummel, J., Wagner, P., Wießner, E.. *IEEE ITSC 2018*, 2018. DOI 10.1109/ITSC.2018.8569938
   Used for: Eclipse SUMO 1.27.1 is the simulator behind every outcome number; TraCI (setRoute, setMaxSpeed, saveState/loadState with --save-state.rng) is the only actuation path; duarouter, randomTrips, netconvert and sumolib are its tools.
   Code: eclipse-sumo/sumo v1_27_1 (pip eclipse-sumo==1.27.1, EPL-2.0)
   Files: `backend/app/twin/`, `src/pipeline/v2x/closed_loop.py`, `backend/app/protocols/oracle_gate.py`, `backend/app/routing/local_routes.py`

2. **Traffic Simulation for All: A Real World Traffic Scenario from the City of Bologna** — Bieker, L., Krajzewicz, D., Morra, A., Michelacci, C., Cartolano, F.. *Modeling Mobility with Open Data, Springer*, 2015. DOI 10.1007/978-3-319-15024-6_4
   Used for: Official SUMO scenario run unmodified as the Lab-01 baseline; source of the warm-up lesson in the control benchmark config.
   Files: `paper_labs/01_sumo_foundation/`, `backend/app/signals/configs/benchmark.yaml`

3. **A digital twin in transportation: Real-time synergy of traffic data streams and simulation for virtualizing motorway dynamics** — Kušić, K., Schumann, R., Ivanjko, E.. *Advanced Engineering Informatics 55, 101858*, 2023. DOI 10.1016/j.aei.2022.101858
   Used for: Method pattern for synchronising a SUMO twin from measured counts (calibrator-based dynamic demand).
   Code: SiLab-group/DigitalTwin_GenevaMotorway @5d2f6c2 (GPL-3.0)
   Files: `src/pipeline/adapters/twin/scenario_sync.py`

4. **Modeling and Analyzing Urban Networks and Amenities with OSMnx** — Boeing, G.. *Geographical Analysis 57(4):567–577*, 2025. DOI 10.1111/gean.70009
   Used for: Cross-validation of the netconvert road graph against an independent OSM extraction (Lab 02).
   Files: `paper_labs/02_dhaka_osm/`

5. **Max pressure control of a network of signalized intersections** — Varaiya, P.. *Transportation Research Part C 36:177–195*, 2013. DOI 10.1016/j.trc.2013.08.014
   Used for: Classical signal-control baseline in the control benchmark.
   Files: `src/pipeline/adapters/control/signal_baselines.py`

6. **Traffic Assignment Manual** — Bureau of Public Roads, U.S. Department of Commerce. *Washington, D.C.*, 1964. 
   Used for: The BPR volume-delay function whose alpha/beta coefficients price background load in the generalized route cost.
   Files: `backend/app/routing/route_optimizer.py`, `backend/app/routing/network_assignment.py`

7. **The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games** — Yu, C., Velu, A., Vinitsky, E., Gao, J., Wang, Y., Bayen, A., Wu, Y.. *NeurIPS 2022 Datasets and Benchmarks*, 2022. https://arxiv.org/abs/2103.01955
   Used for: MAPPO signal-control arms of the control benchmark (pinned official code).
   Code: marlbenchmark/on-policy (pinned)
   Files: `src/pipeline/adapters/control/`

8. **URB: Urban Routing Benchmark for RL-equipped Connected Autonomous Vehicles** — Psarou, A., et al.. *NeurIPS 2025 Datasets and Benchmarks*, 2025. https://arxiv.org/abs/2505.17734
   Used for: Routing benchmark challenger pinned for the control gate.
   Code: pinned in upstream/UPSTREAM_PINS.yaml
   Files: `backend/app/routing/configs/benchmark.yaml`

## Experimental protocol and statistics

1. **The Probable Error of a Mean** — Student (W. S. Gosset). *Biometrika 6(1):1–25*, 1908. DOI 10.1093/biomet/6.1.1
   Used for: The paired-seed 95 % confidence interval on percentage change in vehicle-hours uses the t critical value for n−1 degrees of freedom (table hard-coded for n = 2…13).
   Files: `backend/app/protocols/oracle_gate.py`

2. **An Introduction to the Bootstrap** — Efron, B., Tibshirani, R. J.. *Chapman & Hall/CRC*, 1993. DOI 10.1201/9780429246593
   Used for: Percentile bootstrap (10 000 resamples over seeds) as the alternate interval on the mean per-arm change.
   Files: `backend/app/protocols/statistics.py`

3. **Individual Comparisons by Ranking Methods** — Wilcoxon, F.. *Biometrics Bulletin 1(6):80–83*, 1945. DOI 10.2307/3001968
   Used for: Two-sided signed-rank test on paired seeds (with the honest note that n = 3 gives a minimum p of 0.25, so the interval is the informative statistic).
   Files: `backend/app/protocols/statistics.py`

4. **SciPy 1.0: fundamental algorithms for scientific computing in Python** — Virtanen, P., et al.. *Nature Methods 17:261–272*, 2020. DOI 10.1038/s41592-019-0686-2
   Used for: scipy.stats implementation of the signed-rank test.
   Files: `backend/app/protocols/statistics.py`

5. **Array programming with NumPy** — Harris, C. R., et al.. *Nature 585:357–362*, 2020. DOI 10.1038/s41586-020-2649-2
   Used for: All numerics.
   Files: `requirements.txt`

6. **PyTorch: An Imperative Style, High-Performance Deep Learning Library** — Paszke, A., et al.. *NeurIPS 2019*, 2019. https://arxiv.org/abs/1912.01703
   Used for: Model training and inference for every deep forecaster.
   Files: `requirements.txt`, `backend/app/forecasting/`

## Web application and external services

1. **Google Maps Platform — Routes API (computeRoutes, TRAFFIC_AWARE_OPTIMAL)** — Google. *https://developers.google.com/maps/documentation/routes*, 2026. https://developers.google.com/maps/documentation/routes
   Used for: External LIVE reference travel time for the trip analysis when a key is configured. Never ground truth, never a training or validation target; recorded corridor states are replayed (labelled RECORDED) when the key is absent or denied.
   Files: `backend/app/live/google_routes.py`, `backend/app/routing/trip_analysis.py`

2. **MapLibre GL JS 4.7.1** — MapLibre contributors. *BSD-3-Clause*, 2024. https://maplibre.org/
   Used for: All map rendering in the web application.
   Files: `frontend/index.html`, `frontend/pages/prediction.js`, `frontend/pages/control_room.js`

3. **Esri World Street Map tiles (ArcGIS Online)** — Esri. *basemap tiles, attribution required*, 2026. https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer
   Used for: Background tiles behind the traffic layers.
   Files: `frontend/services/basemap.js`, `backend/app/api/system.py`

4. **FastAPI / Uvicorn** — Ramírez, S.; Encode. *MIT*, 2026. https://fastapi.tiangolo.com/
   Used for: The API server that serves the application and every evidence endpoint.
   Files: `backend/app/main.py`, `backend/app/api/`
