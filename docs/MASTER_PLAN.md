# Master plan: the road-traffic thesis as a web app, built from the world's best papers and their official code

One page. Written 2026-10-03. Everything is software: public datasets, public APIs, AWS services, simulators.
Repositories were verified on the GitHub API today (exist, licence, last push). Details per pillar live in
`TRAFFIC_SOTA_PAPERS.md`, `TRAFFIC_PHASES.md`, `TRAFFIC_FULL_SCOPE.md`.

## 1. The workflow, in plain words

```
 DATA IN                     THE ENGINE (one city state, one API)                          WHAT A PERSON GETS
 ─────────                   ─────────────────────────────────────                         ──────────────────
 public sensor datasets ──▶  1 SENSE     video → vehicle counts, speeds (RT-DETR, ByteTrack)   camera page
 (METR-LA, PEMS-BAY,         2 ESTIMATE  fill roads with no sensor (ImputeFormer, IGNNK, LWR)  sparse-sensing page
  LargeST, PEMS04/08)        3 PREDICT   15/30/60 min ahead, 14 models, calibrated bands       forecast map, leaderboard,
 public camera feeds ──▶     4 DETECT    congestion onset and incidents (IncidentNet, onset)     onset page, bands
 (511 APIs, BMD-45 video)    5 CONTROL   signals in simulation (max-pressure, MAPPO, Adv-MP)    incident page
 Amazon Location API ──▶     6 ADVISE    map matching, ETA, "leave by 8:07, 91 %" (FMM, MAPIE)  signal page
 (live roads, any city)      7 VERIFY    SUMO twin + V2X replay: does the advice help the city  departure advice, alerts
 OSM, GTFS, Open-Meteo ──▶                                                                        twin replay, assistant,
 your Dhaka recordings ──▶   OUTCOMES feed back: recalibration, leaderboard refresh              Alexa, zero-shot upload
```

Every stage is a reproduced paper. Every number on screen is read from a model run, a dataset or an API. Training runs
on AWS GPUs; the app runs on AWS (Bedrock, Location, S3, EC2, SNS, Cognito, ECS).

## 2. All features

| # | Feature | Pillar |
|---|---|---|
| F1 | Live map of any city, speed per road, data age shown | 6 |
| F2 | Forecast map 15/30/60 min ahead, time slider, model picker | 3 |
| F3 | Leaderboard: each paper, our number vs published, gap % | 3 |
| F4 | Onset page: which model sees the jam first, lead minutes | 4 |
| F5 | Calibrated p10/p50/p90 band with measured coverage | 3 |
| F6 | Departure advice with a probability | 6 |
| F7 | Large-scale mode, thousands of sensors | 3 |
| F8 | Zero-shot: upload any city's sensor CSV, forecast without training | 3 |
| F9 | Cross-city page: LA models on the Dhaka corridor, honest gap | 3 |
| F10 | Train-your-own on AWS from the page, result self-registers | 3 |
| F11 | Evidence page: checkpoint hashes, logs, protocol check | all |
| F12 | Twin replay: vehicle-hours with and without the advice | 7 |
| F13 | Assistant and Alexa on the same forecast | 6 |
| F14 | Regime-aware alerts on watched roads | 4 |
| F15 | Camera page: counts per class per minute from a feed or video | 1 |
| F16 | Sparse-sensing page: switch sensors off, watch the estimate, error curve | 2 |
| F17 | Incident page: anomaly score, location, severity, detection delay | 4 |
| F18 | Signal page: controllers compared on the same simulated day | 5 |
| F19 | Probe page: a GPS trace map-matched into segment speeds | 6 |

## 3. All papers with official code (42; ✓ = already reproduced here)

### Pillar 3 · Prediction
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 1 | DCRNN | ICLR 2018 | https://arxiv.org/abs/1707.01926 | https://github.com/liyaguang/DCRNN | MIT | |
| 2 | Graph WaveNet | IJCAI 2019 | https://arxiv.org/abs/1906.00121 | https://github.com/nnzhan/Graph-WaveNet | MIT | ✓ |
| 3 | STGCN | IJCAI 2018 | https://arxiv.org/abs/1709.04875 | https://github.com/VeritasYin/STGCN_IJCAI-18 | BSD-2 | |
| 4 | AGCRN | NeurIPS 2020 | https://arxiv.org/abs/2007.02842 | https://github.com/LeiBAI/AGCRN | MIT | |
| 5 | MTGNN | KDD 2020 | https://arxiv.org/abs/2005.11650 | https://github.com/nnzhan/MTGNN | MIT | |
| 6 | STID | CIKM 2022 | https://arxiv.org/abs/2208.05233 | https://github.com/GestaltCogTeam/STID | Apache-2.0 | ✓ |
| 7 | STAEformer | CIKM 2023 | https://arxiv.org/abs/2308.10425 | https://github.com/XDZhelheim/STAEformer | none → via BasicTS | ✓ |
| 8 | D2STGNN | VLDB 2022 | https://arxiv.org/abs/2206.09112 | https://github.com/GestaltCogTeam/D2STGNN | none → via BasicTS | |
| 9 | MegaCRN | AAAI 2023 | https://arxiv.org/abs/2212.05989 | https://github.com/deepkashiwa20/MegaCRN | MIT | |
| 10 | STD-MAE | IJCAI 2024 | https://arxiv.org/abs/2312.00516 | https://github.com/Jimmy-7664/STD-MAE | none → via BasicTS | |
| 11 | HimNet | KDD 2024 | https://arxiv.org/abs/2405.10800 | https://github.com/XDZhelheim/HimNet | none → via BasicTS | |
| 12 | BigST | VLDB 2024 | https://dl.acm.org/doi/10.14778/3641204.3641217 | https://github.com/usail-hkust/BigST | none → via BasicTS | |
| 13 | PatchSTG | KDD 2025 | https://arxiv.org/abs/2412.09972 | https://github.com/LMissher/PatchSTG | MIT | |
| 14 | STGformer | 2024 | https://arxiv.org/abs/2410.00385 | https://github.com/Dreamzz5/STGformer | MIT | |
| 15 | OpenCity | 2024 | https://arxiv.org/abs/2408.10269 | https://github.com/HKUDS/OpenCity | MIT | ✓ |
| 16 | UniST | KDD 2024 | https://arxiv.org/abs/2402.11838 | https://github.com/tsinghua-fib-lab/UniST | none, external only | |
| 17 | UrbanGPT | KDD 2024 | https://arxiv.org/abs/2403.00813 | https://github.com/HKUDS/UrbanGPT | Apache-2.0 | |
| 18 | Chronos-2 | 2025 | https://arxiv.org/abs/2510.15821 | https://github.com/amazon-science/chronos-forecasting | Apache-2.0 | Bolt ✓ (negative) |
| 19 | TimesFM | ICML 2024 | https://arxiv.org/abs/2310.10688 | https://github.com/google-research/timesfm | Apache-2.0 | |
| 20 | Moirai | ICML 2024 | https://arxiv.org/abs/2402.02592 | https://github.com/SalesforceAIResearch/uni2ts | Apache-2.0 | |
| 21 | Time-MoE | ICLR 2025 | https://arxiv.org/abs/2409.16040 | https://github.com/Time-MoE/Time-MoE | Apache-2.0 | |
| 22 | LargeST benchmark | NeurIPS 2023 | https://arxiv.org/abs/2306.08259 | https://github.com/liuxu77/LargeST | MIT / CC BY-NC data | |
| 23 | BasicTS harness | TKDE 2024 | https://arxiv.org/abs/2310.06119 | https://github.com/GestaltCogTeam/BasicTS | Apache-2.0 | ✓ in use |
| 24 | TSFMs as strong baselines in transportation | 2026 | https://arxiv.org/abs/2602.24238 | (benchmark numbers to reproduce) | — | |
| 25 | Regime-dependent failures of TSFMs | ICML 2026 wksh | https://arxiv.org/abs/2606.18367 | (the onset question) | — | |
| 26 | MAPIE conformal prediction | — | https://mapie.readthedocs.io | https://github.com/scikit-learn-contrib/MAPIE | BSD-3 | |

### Pillar 1 · Sense
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 27 | RT-DETR | CVPR 2024 | https://arxiv.org/abs/2304.08069 | https://github.com/lyuwenyu/RT-DETR | Apache-2.0 | ✓ |
| 28 | ByteTrack | ECCV 2022 | https://arxiv.org/abs/2110.06864 | https://github.com/FoundationVision/ByteTrack | MIT | ✓ |
| 29 | BoT-SORT | 2022 | https://arxiv.org/abs/2206.14651 | https://github.com/NirAharon/BoT-SORT | MIT | |
| 30 | BMD-45 dataset | CVPR 2026 wksh | https://arxiv.org/abs/2604.24419 | https://huggingface.co/datasets/iisc-aim/BMD-45 | dataset card | |

### Pillar 2 · Estimate
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 31 | ImputeFormer | KDD 2024 | https://arxiv.org/abs/2312.01728 | https://github.com/tongnie/ImputeFormer | MIT | |
| 32 | SPIN | NeurIPS 2022 | https://arxiv.org/abs/2205.13479 | https://github.com/Graph-Machine-Learning-Group/spin | MIT | |
| 33 | GRIN | ICLR 2022 | https://arxiv.org/abs/2108.00298 | https://github.com/Graph-Machine-Learning-Group/grin | none → via tsl | |
| 34 | IGNNK kriging | AAAI 2021 | https://arxiv.org/abs/2006.07527 | https://github.com/Kaimaoge/IGNNK | none, external only | |
| 35 | Torch Spatiotemporal (tsl) | library | https://arxiv.org/abs/2311.11003 | https://github.com/TorchSpatiotemporal/tsl | MIT | |
| 36 | Physics-informed traffic state estimation (survey + DGAE) | TITS 2023 | https://arxiv.org/abs/2303.02063 | https://github.com/ZJU-TSELab/DGAE | none, reference | |

### Pillar 4 · Detect
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 37 | IncidentNet | 2024 | https://arxiv.org/abs/2408.00996 | https://github.com/MPSLab-ASU/IncidentNet | Apache-2.0 | |

### Pillar 5 · Control
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 38 | Max-pressure (Varaiya) | TR-C 2013 | https://doi.org/10.1016/j.trc.2013.08.014 | ours, thin | — | ✓ |
| 39 | MAPPO | NeurIPS 2022 | https://arxiv.org/abs/2103.01955 | https://github.com/marlbenchmark/on-policy | MIT | ✓ |
| 40 | Advanced-XLight (Advanced-MP / CoLight) | ICML 2022 | https://arxiv.org/abs/2112.10107 | https://github.com/LiangZhang1996/Advanced_XLight | GPL-3.0, separate process | |
| 41 | CoSLight | KDD 2024 | https://arxiv.org/abs/2405.17152 | https://github.com/bonaldli/CoSLight | none, reference | |
| 42 | LLMLight | KDD 2025 | https://arxiv.org/abs/2312.16044 | https://github.com/usail-hkust/LLMTSCS | none, recipe with Bedrock | |
| 43 | LibSignal harness | NeurIPS 2022 wksh | https://arxiv.org/abs/2211.10649 | https://github.com/DaRL-LibSignal/LibSignal | none | |
| 44 | RESCO protocol | NeurIPS 2021 wksh | https://arxiv.org/abs/2110.09450 | https://github.com/Pi-Star-Lab/RESCO | GPL-3.0 | ✓ protocol |
| 45 | CityFlow simulator | WWW 2019 | https://arxiv.org/abs/1905.05217 | https://github.com/cityflow-project/CityFlow | Apache-2.0 | |
| 46 | sumo-rl | — | — | https://github.com/LucasAlegre/sumo-rl | MIT | ✓ pinned |

### Pillar 6 · Advise
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 47 | Fast Map Matching | IJGIS 2018 | https://doi.org/10.1080/13658816.2017.1400548 | https://github.com/cyang-kth/fmm | Apache-2.0 | |
| 48 | DeepTTE | AAAI 2018 | https://ojs.aaai.org/index.php/AAAI/article/view/11877 | https://github.com/UrbComp/DeepTTE (via LibCity) | none → LibCity | |
| 49 | LibCity harness | SIGSPATIAL 2021 | https://arxiv.org/abs/2304.14343 | https://github.com/LibCity/Bigscity-LibCity | Apache-2.0 | |
| 50 | Bounded-compliance rerouting | ACM TOMACS 2023 | https://doi.org/10.1145/3579842 | SUMO rerouting device | EPL-2.0 | ✓ |

### Pillar 7 · Verify
| # | Paper | Venue | Paper | Code | Licence | |
|---|---|---|---|---|---|---|
| 51 | SUMO | ITSC 2018 | https://doi.org/10.1109/ITSC.2018.8569938 | https://github.com/eclipse-sumo/sumo | EPL-2.0 | ✓ |
| 52 | Eclipse MOSAIC (V2X) | IEEE Access 2022 | https://doi.org/10.1109/ACCESS.2022.3193765 | https://github.com/eclipse-mosaic/mosaic | EPL-2.0 | ✓ |
| 53 | Geneva motorway digital twin | AEI 2023 | https://doi.org/10.1016/j.aei.2022.101858 | https://github.com/SiLab-group/DigitalTwin_GenevaMotorway | per repo | ✓ |
| 54 | MATSim | book 2016 | https://doi.org/10.5334/baw | https://github.com/matsim-org/matsim-libs | GPL-2.0, separate process | |
| 55 | Flow (mixed autonomy) | CoRL 2018 | https://arxiv.org/abs/1710.05465 | https://github.com/flow-project/flow | MIT | |

Count: 55 entries, 50 with runnable code, 13 already reproduced or in use.

## 4. Build order (one paper per phase; each ends with a reproduction table, a web feature, tests, a commit)

P1 DCRNN · P2 onset scorecard · P3 D2STGNN · P4 MegaCRN · P5 STD-MAE + HimNet · P6 BigST on LargeST · P7 PatchSTG + STGformer ·
P8 conformal + departure advice · P9 Chronos-2 / TimesFM / Moirai / Time-MoE zero-shot · P10 alerts · P11 UniST / OpenCity on Dhaka ·
P12 serving + twin — then Q1 ImputeFormer · Q2 IGNNK · Q3 IncidentNet · Q4 Advanced-MP via LibSignal · Q5 LLMLight with Bedrock ·
Q6 FMM + DeepTTE · Q7 BMD-45 + BoT-SORT · Q8 physics-informed TSE · Q9 MATSim herding.

Rules: official code unchanged and pinned; licence read at pin time; GPL tools run as separate processes; unlicensed repos are
reference only; no Google APIs; Google-Routes recordings never used for training; AWS for compute; one phase at a time.

## 6. The workflow with the signature features in place (added 2026-10-03; features in `SIGNATURE_FEATURES.md`)

```
 DATA IN                          ENGINE STAGE              SIGNATURE FEATURES                 PAPERS / CODE THAT POWER IT
 ──────────────────────           ────────────────          ──────────────────────────────     ─────────────────────────────────────────
 sensor datasets, 511 cameras,    1 SENSE                   S1 your phone is the sensor        FMM (map matching), RT-DETR, ByteTrack, BoT-SORT, BMD-45
 users' phones (GPS), Amazon      2 ESTIMATE                S16 equity map (who is sensed)     ImputeFormer, SPIN/GRIN (tsl), IGNNK, physics-informed TSE
 Location, OSM, GTFS, weather,    3 PREDICT                 S11 event-aware forecasts          DCRNN … STAEformer, STD-MAE, HimNet, BigST, PatchSTG, STGformer,
 holidays, events                                           S3 "why will it be slow?"          OpenCity, UniST, Chronos-2, TimesFM, Moirai, Time-MoE;
                                                            S9 open regime leaderboard         verbal explanations of STGNNs; TSFM-baselines 2026; regime-failure 2026
                                  4 DETECT                  S13 incident radar                 IncidentNet; regime-failure 2026 (onset protocol)
                                                            S10 time machine
                                  5 CONTROL (simulated)     S14 signal lab with reasons        max-pressure, MAPPO, Advanced-XLight, CoSLight, LLMLight, LibSignal, CityFlow
                                  6 ADVISE                  S12 reliability index per route    MAPIE (conformal), DeepTTE via LibCity, bounded-compliance rerouting
                                                            S7 herding guard                   Nature Comms 2026 (navigation concentration), popularity-based alternative routing
                                                            S4 ask the city                    TrafficGPT pattern, UrbanGPT; Bedrock agent + MCP
                                  7 VERIFY                  S2 the living twin                 SUMO, MOSAIC, Geneva twin, deck.gl TripsLayer
                                                            S5 what-if planner                 SUMO paired counterfactuals, DiTAT
                                                            S6 CO2 and fuel meter              SUMO HBEFA emission models
                                  8 LEARN / OPERATE         S15 model health                   Michelangelo-style monitoring, Evidently
                                                            S8 world congestion pulse          TomTom index methodology on Amazon Location samples
 ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 what a person does: open a city → see live + forecast with a band → ask why → get a departure time with 95 % buffer → watch the twin →
                     try a what-if → get warned at onset → see the model's health → submit a model to the leaderboard
```

Build order is unchanged: P1–P12 (prediction, the thesis core), then Q1–Q9 (other pillars), with each signature
feature attached to the phase listed in `SIGNATURE_FEATURES.md`.
