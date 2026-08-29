# PAPERS_AND_CODE — what DhakaFlow follows, with official code pins

Rule (upstream/UPSTREAM_PINS.yaml): official research code is the algorithmic
source of truth; our adapters translate, never alter. Every pin is a commit.

## Perception
| Paper | Venue | Official repo @ pin | Used for |
|---|---|---|---|
| RT-DETR: DETRs Beat YOLOs on Real-time Object Detection | CVPR 2024 | github.com/lyuwenyu/RT-DETR @068dfde6 | vehicle detector; fine-tuned on Poribohon-BD (9,058 BD images) -> mAP 0.711 vs published 0.643 |
| ByteTrack: Multi-Object Tracking by Associating Every Detection Box | ECCV 2022 | github.com/FoundationVision/ByteTrack @d1bf0191 | tracking; we supply detections, consume tracks (research/perception/bytetrack_adapter.py) |
| BNVD (Bangladeshi Native Vehicle Dataset) | data paper | github.com/bipin-saha/BNVD @b4e74d17 | Dhaka vehicle classes |

## Forecasting
| Paper | Venue | Repo @ pin | Used for |
|---|---|---|---|
| Graph WaveNet for Deep Spatial-Temporal Graph Modeling | IJCAI 2019 | BasicTS legacy baselines @4c3e2d37 (GestaltCogTeam/BasicTS) | in-loop forecaster (+5/10/15 min); official training pipeline, z-score scaler; test log + checkpoint SHA in artifacts/gates/FORECAST_PASS.json |
| BasicTS benchmark suite | TKDE 2024 | @c2bb6e31 | training/eval harness (DCRNN/STID/STAEformer floors also run) |

## Digital twin & counterfactuals
| Paper | Venue | Repo @ pin | Used for |
|---|---|---|---|
| Geneva Motorway Digital Twin (Kusic et al.), 10.1016/j.aei.2022.101858 | Adv. Eng. Informatics 2023 | SiLab-group/DigitalTwin_GenevaMotorway | Gate-2 sync method: measured flows construct the twin (GEH<5 acceptance) |
| SUMO (Lopez et al.) | IEEE ITSC 2018 | Eclipse SUMO 1.27.1 (pip pin) | microsimulation; saveState/loadState + --save-state.rng = paired same-state counterfactuals |
| DiTAT: Digital Twin-Aided Municipal Traffic Control | SUMO Conf 2025 | (no public code — closest precedent, gap = our contribution) | related work |

## Signal control
| Paper | Venue | Repo @ pin | Used for |
|---|---|---|---|
| Max pressure control of a network of signalized intersections (Varaiya), 10.1016/j.trc.2013.08.014 | TR-C 2013 | faithful thin implementation (research/control/signal_baselines.py), protocol per RESCO | Gate-6 baseline + the accepted onset candidate A2 |
| RESCO benchmark | NeurIPS 2021 wksh | Pi-Star-Lab/RESCO | evaluation protocol reference |
| The Surprising Effectiveness of PPO / MAPPO | NeurIPS 2022 | marlbenchmark/on-policy @de66d7a4 | RL signal arms (Gate 9; trained mappo + mappo_pressure; FA arms retraining on Colab) |
| sumo-rl | — | LucasAlegre/sumo-rl @86f0fc4 | env conventions |

## Routing
| Paper | Venue | Mechanism | Used for |
|---|---|---|---|
| SUMO rerouting device docs + bounded-compliance literature (ACM TOMACS 2023, 10.1145/3579842) | — | stock --device.rerouting.probability + TraCI rerouteTraveltime (measured costs) | Gate-7 compliance ladder 0-40%; p10 accepted; trapped vehicles never touched |

## Networking / actuation
| Paper | Venue | Repo @ pin | Used for |
|---|---|---|---|
| Eclipse MOSAIC co-simulation, 10.1109/ACCESS.2022.3193765 | IEEE Access 2022 | eclipse-mosaic/mosaic 25.2 (main @005fa1f3) | official Barnim V2X example REPRODUCED (4658 tx/16612 rx); measured ITS-G5 latency (median 1.9ms, p95 7ms) drives the V2X message bus; planner acts only via delivered+ACKed messages |
| SURTRAC (Smith et al.); CIRCLES/MegaVanderTest; Stern et al. 2018 | field deployments | — | real-road actuation precedents; motivate MODE2/MODE3 capability levels (dhakaflow/cities/registry.yaml) |

## The gap = the contribution
No public project chains: real video -> physical traffic state -> synchronized
twin (GEH-checked) -> preloaded forecast -> same-state multi-candidate futures
(paired RNG) -> network-wide guards (local relief rejected) -> networked
actuation with measured latency -> honest NO-ACTION when nothing safely helps.
Every stage has a PASS artifact (artifacts/gates/) and a defect ledger
(docs/CURRENT_SYSTEM_GAP_AUDIT.md, 28 findings adjudicated).
