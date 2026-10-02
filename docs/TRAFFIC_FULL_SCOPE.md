# Road traffic, the whole field: seven pillars, the best paper with official code in each, and what the web app does with it

Written 2026-10-03. Prediction is one pillar of seven. The project already has working pieces in five of them
(perception, twin, signal control, V2X, prediction); this document puts the best paper of every pillar beside its
official code so each pillar gets reproduced the same way: pin commit + licence → official example unchanged → published
number reproduced → one web feature → tests → commit → stop. Repositories were checked on the GitHub API today
(licence, last push). "NONE" = no LICENSE file: external checkout only, never vendored, or run through a licensed harness.

## The seven pillars and the loop they form

```
 1 SENSE            2 ESTIMATE            3 PREDICT             4 DETECT
 cameras → counts   fill missing sensors  15/30/60 min ahead    incidents and
 (RT-DETR+ByteTrack) (imputation/kriging,  (the 14 models,      congestion onset
                     physics-informed)     conformal bands)      (IncidentNet, onset)
        │                  │                   │                     │
        └──────────────────┴─────── one city state, one API ────────┘
                                          │
         5 CONTROL                 6 ROUTE / ADVISE                7 SIMULATE / VERIFY
         signals: max-pressure,    map matching, ETA,              SUMO twin, paired
         RL (MPLight, CoLight,     departure advice,               counterfactuals, V2X
         Advanced-XLight), LLMLight routing under uncertainty      channel (MOSAIC)
```

## Pillar 1 · Sense: traffic state from video

| Paper | Venue | Official code | Licence | Status / use |
|---|---|---|---|---|
| RT-DETR, Zhao et al. | CVPR 2024 | https://github.com/lyuwenyu/RT-DETR | Apache-2.0 | **done**: fine-tuned on Poribohon-BD, mAP 0.711 vs 0.643 published |
| ByteTrack, Zhang et al. | ECCV 2022 | https://github.com/FoundationVision/ByteTrack | MIT | **done**: tracking adapter |
| BoT-SORT, Aharon et al. | 2022 | https://github.com/NirAharon/BoT-SORT | MIT | next tracker to compare (camera-motion aware) |
| BMD-45 dataset, Sharma et al. | CVPR 2026 workshop | https://huggingface.co/datasets/iisc-aim/BMD-45 | per dataset card | 480 K boxes, 14 classes incl. auto-rickshaw, Bengaluru CCTV: the developing-city benchmark for our detector |
| UA-DETRAC | CVIU 2020 | dataset | per licence | the standard detection+tracking benchmark |

Web feature: **Camera page**: upload or stream a junction video, see counts per class per minute and the derived speed, with the detector's mAP shown.

## Pillar 2 · Estimate: fill what sensors miss

| Paper | Venue | Official code | Licence | Use |
|---|---|---|---|---|
| ImputeFormer, Nie et al. | KDD 2024 | https://github.com/tongnie/ImputeFormer | MIT | low-rank Transformer imputation on METR-LA / PEMS |
| SPIN, Marisca et al. | NeurIPS 2022 | https://github.com/Graph-Machine-Learning-Group/spin | MIT | sparse attention imputation; runs on the `tsl` library |
| GRIN, Cini et al. | ICLR 2022 | https://github.com/Graph-Machine-Learning-Group/grin | NONE → via `tsl` (MIT) | graph recurrent imputation |
| PriSTI, Liu et al. | ICDE 2023 | https://github.com/LMZZML/PriSTI | NONE | diffusion imputation, reference only |
| IGNNK, Wu et al. | AAAI 2021 | https://github.com/Kaimaoge/IGNNK | NONE | inductive kriging: forecast a road with no sensor |
| Torch Spatiotemporal (`tsl`) | library | https://github.com/TorchSpatiotemporal/tsl | MIT | the harness for this pillar |
| Physics-informed TSE survey, Di et al. | TITS 2023 | https://arxiv.org/abs/2303.02063; DGAE code https://github.com/ZJU-TSELab/DGAE (NONE) | — | LWR-constrained estimation from sparse probes: the sensor-poor-city method |

Web feature: **Sparse-sensing page**: switch off sensors on the map and watch the estimate fill them in, with the error curve "how few sensors still beat persistence" (the thesis's sparse-sensing result).

## Pillar 3 · Predict (the catalogue in `TRAFFIC_SOTA_PAPERS.md`, 14 models, 4 done)

Web features: forecast map, leaderboard, onset page, conformal bands, zero-shot upload, cross-city page.

## Pillar 4 · Detect: incidents and congestion onset

| Paper | Venue | Official code | Licence | Use |
|---|---|---|---|---|
| IncidentNet, Sharma et al. (ASU) | 2024 | https://github.com/MPSLab-ASU/IncidentNet | Apache-2.0 | detection, localisation and severity with cameras on < 20 % of junctions; 98 % detection, 197 s |
| Early traffic anomaly detection, "Know Unreported Roadway Incidents" | 2025 | arXiv 2412.10892 (no code found) | — | method reference for unreported incidents |
| Regime-dependent failures (onset) | ICML 2026 wksh | arXiv 2606.18367 | — | the onset protocol we already score |

Web feature: **Incident page**: live anomaly score per road, where and how severe, with the detector's delay measured on replayed days.

## Pillar 5 · Control: traffic signals

| Paper | Venue | Official code | Licence | Status / use |
|---|---|---|---|---|
| Max-pressure, Varaiya | TR-C 2013 | thin faithful implementation (ours) | — | **done**: baseline and accepted candidate |
| MAPPO, Yu et al. | NeurIPS 2022 | https://github.com/marlbenchmark/on-policy | MIT | **done**: trained RL arms |
| PressLight / CoLight, Wei et al. | KDD / CIKM 2019 | https://github.com/wingsweihua/presslight, https://github.com/wingsweihua/colight | NONE | reference; run via LibSignal |
| MPLight, Chen et al. | AAAI 2020 | https://github.com/Chacha-Chen/MPLight | NONE | reference; via LibSignal |
| Advanced-XLight (Advanced-MP, Advanced-CoLight), Zhang et al. | ICML 2022 | https://github.com/LiangZhang1996/Advanced_XLight | GPL-3.0 | state of the art learned control; GPL means run as a separate process, never linked |
| CoSLight, Ruan et al. | KDD 2024 | https://github.com/bonaldli/CoSLight | NONE | collaborator selection; reference |
| LLMLight, Lai et al. | KDD 2025 | https://github.com/usail-hkust/LLMTSCS | NONE | LLM as signal agent; reproduce with Bedrock as the LLM, reference only for code |
| LibSignal | NeurIPS 2022 wksh | https://github.com/DaRL-LibSignal/LibSignal | NONE | the benchmark harness (CityFlow + SUMO backends) |
| RESCO | NeurIPS 2021 wksh | https://github.com/Pi-Star-Lab/RESCO | GPL-3.0 | evaluation protocol (already followed) |
| sumo-rl | — | https://github.com/LucasAlegre/sumo-rl | MIT | environment conventions (pinned) |
| CityFlow | WWW 2019 | https://github.com/cityflow-project/CityFlow | Apache-2.0 | fast simulator for the RL benchmarks |

Web feature: **Signal page**: pick a junction set, compare fixed-time, max-pressure, MAPPO, Advanced-MP on the same SUMO day; delay and queue per arm; the controller that is actually running in the twin.

## Pillar 6 · Route and advise

| Paper / tool | Venue | Official code | Licence | Use |
|---|---|---|---|---|
| Fast Map Matching (FMM), Yang & Gidófalvi | IJGIS 2018 | https://github.com/cyang-kth/fmm | Apache-2.0 | GPS traces → road segments (probe speeds, outcomes) |
| DeepTTE, Wang et al. | AAAI 2018 | https://github.com/UrbComp/DeepTTE | NONE | learned travel-time estimation; run via LibCity (Apache-2.0) |
| LibCity | SIGSPATIAL 2021 | https://github.com/LibCity/Bigscity-LibCity | Apache-2.0 | harness for ETA, OD, trajectory models |
| Bounded-compliance rerouting (ACM TOMACS 2023) | — | SUMO rerouting device | EPL-2.0 | **done**: compliance ladder 0–40 % |
| Valhalla / OTP2 | — | official images | MIT / LGPL | road and transit routing engines |
| MAPIE | — | https://github.com/scikit-learn-contrib/MAPIE | BSD-3 | calibrated arrival windows → latest safe departure |

Web feature: **Departure advice** with a probability; **probe page**: a GPS trace is map-matched and becomes measured segment speeds.

## Pillar 7 · Simulate and verify

| Tool / paper | Official code | Licence | Status |
|---|---|---|---|
| SUMO, Lopez et al., ITSC 2018 | https://github.com/eclipse-sumo/sumo | EPL-2.0 | **done**: twin, paired same-state counterfactuals |
| Eclipse MOSAIC (V2X), IEEE Access 2022 | https://github.com/eclipse-mosaic/mosaic | EPL-2.0 | **done**: Barnim example reproduced, measured ITS-G5 latency |
| Geneva motorway digital twin, Kusic et al., AEI 2023 | https://github.com/SiLab-group/DigitalTwin_GenevaMotorway | per repo | **done**: GEH < 5 sync method |
| MATSim | https://github.com/matsim-org/matsim-libs | GPL-2.0 (NONE on API) | population herding experiment, separate process |
| Flow, Wu et al. | https://github.com/flow-project/flow | MIT | mixed-autonomy reference |

Web feature: **Twin replay** (exists): forecast + controller + advice replayed on the same day, vehicle-hours with and without.

## Build order across pillars (one paper per phase, after the prediction phases P1–P12)

| Phase | Pillar | Paper | Web feature |
|---|---|---|---|
| Q1 | 2 | ImputeFormer on METR-LA | sparse-sensing page |
| Q2 | 2 | IGNNK kriging (via `tsl`) | forecast for a road with no sensor |
| Q3 | 4 | IncidentNet on the SUMO twin | incident page |
| Q4 | 5 | Advanced-MP via LibSignal on our corridor | signal page, arm comparison |
| Q5 | 5 | LLMLight recipe with Bedrock | explainable signal decisions in the assistant |
| Q6 | 6 | FMM map matching + DeepTTE via LibCity | probe page, measured ETA |
| Q7 | 1 | detector evaluated on BMD-45, BoT-SORT vs ByteTrack | camera page with benchmark row |
| Q8 | 2 | physics-informed TSE (LWR) on the Dhaka corridor | sensor-poor estimate with the physics residual shown |
| Q9 | 7 | MATSim herding: 20 % of agents follow the advice | twin page, population effect |

## What the thesis becomes

A road-traffic system, not a forecaster: sense → estimate → predict → detect → control → advise → verify, each stage a
reproduced world-best paper with its official code, all on one city state and one API, with the forecaster's
regime-transition finding and the sparse-sensing curve as the two original results.
