# DhakaFlow Nexus — Progress Snapshot (2026-08-25, ~21:00 Dhaka)

**Goal:** AI traffic management for Dhaka — observe real traffic (CV), predict
congestion (graph forecasting), prevent/react via signal control (FA-MAPPO) and
routing, prove delay reduction in a SUMO digital twin of the real R1 corridor
(Farmgate–Karwan Bazar–Bangla Motor–Shahbagh, 6,527 edges).

**Sprint window:** 25 Aug 15:00 → 31 Aug 11:00 (140 h wall-clock, hour-by-hour
plan in `docs/SPRINT_140H.md`). Presentation prep after.

## Where we are (end of Day 1, H+6)

| Done | Evidence |
|---|---|
| Frozen foundations: UTD19/MFD science, SUMO platform, real Dhaka R1 network | `paper_labs/00–02`, checksummed |
| E4 routing result: system-optimal vs selfish, **19.5–22.2% delay reduction**, 10 seeds, p ≤ 1.3e-03 | `artifacts/due_dso_stats` |
| All credentials active: Kaggle, road511 (live US cameras+incidents), AWS, GCP ($300), Google Maps | `scripts/verify_keys.py` |
| First live Dhaka Routes+Weather capture executed | `artifacts/p_live/` |
| Live data recorder running 24/7 (US incident labels + camera frames → 2 TB Drive) | `scripts/record_road511.py` |
| Both perception datasets fetched at datacenter speed, audited vs published specs, converted (26,853 boxes, 0 unknown labels), frozen split | S3 + `research/perception/` |
| **P2 twin sensor-graph generation (24 h × 3 seeds) RUNNING on GCP** | acceptance checks gate PASS |
| **Two RT-DETR fine-tunes (r18, r50) RUNNING on AWS GPUs** — official pipeline @ pinned SHA, 24-epoch fair budget | S3 checkpoints |

## Phases remaining (6)

| # | Phase | When | Deliverable |
|---|---|---|---|
| 1 | P1 detectors finish + winner | Aug 26 | per-class AP on rickshaw/CNG/easybike |
| 2 | P3 forecasting sweep (STID/GWNet/DCRNN/STAEformer via BasicTS) | Aug 26–27 | benchmark winner, masked metrics 5/15/30 min |
| 3 | Twin calibration + FA-MAPPO launch | Aug 27 → deadline 03:00 Aug 28 | calibrated twin, 5-arm RL ablation training |
| 4 | Integration: REACT + PREVENT | Aug 28 | one command: any video/live stream → best route → delay number |
| 5 | Results matrix | Aug 29–30 | multi-seed statistics across all arms |
| 6 | Freeze + evidence | Aug 30–31 | reproducible repo, rehearsed live demo |

## Method guarantees (why it is not shallow)

* Official implementations only, pinned by commit (`upstream/UPSTREAM_PINS.yaml`):
  RT-DETR (CVPR'24), ByteTrack (ECCV'22), DCRNN (ICLR'18), Graph WaveNet
  (IJCAI'19), STID/STAEformer (CIKM), MAPPO, SUMO 1.27.1, BasicTS fair harness.
* Every model must reproduce its published number on the authors' benchmark
  before touching Dhaka data; classical→ML→DL ladder — DL must beat the floors.
* Three evidence domains never merged (real benchmark / simulated graph / real
  Dhaka anchors); simulated-only results cannot support real-world claims
  (enforced in code).
* US live data (road511) is domain-shift measurement only, never Dhaka validation.
