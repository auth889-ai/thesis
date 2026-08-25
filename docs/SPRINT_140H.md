# DhakaFlow Nexus — 140-Hour Sprint Plan

**Clock start `H+0` = 2026-08-25 15:00 Asia/Dhaka.  Clock end `H+140` = 2026-08-31 11:00.**
Presentation preparation begins after `H+140`.

"140 hours" is **project wall-clock**, not human hours. Three lanes run inside the
same 140 hours:

| Lane | Budget | Runs when |
|---|---|---|
| **HUMAN** (you) | ~78 h active, 7 h sleep/night | daytime blocks below |
| **BUILD** (assistant) | interleaved, no wall-clock cost to you | continuous |
| **COMPUTE** (Colab + AWS spot) | ~430 GPU-h across parallel arms | **24/7, including while you sleep** |

The plan is ordered by **dependency**, not by preference. Two rules govern the order:

1. **Anything that accrues by wall-clock starts first.** The road511 recorder cannot
   be caught up later — an hour not recorded is data that never exists.
2. **The longest compute job must launch by `H+60`.** FA-MAPPO needs ~50 h of
   wall-clock across 5 parallel arms. Launched later, it cannot finish before the
   presentation.

---

## Critical path

```
P2 twin data ──> P3 forecasting ──┐
                                  ├──> FA-MAPPO (LONG POLE, launch by H+60)
Twin calibration part A ──────────┘
        │
        └──> RL baselines (launch H+48, no forecaster needed)

Datasets ──> P1 detector ──> ByteTrack ──> sensing ──> twin calibration part B
```

**The decoupling that makes 6 days feasible:** twin calibration splits into
**part A** (network-level, validated against the live speed reference — needs no
detector) and **part B** (demand refinement from detector counts). Part A alone is
enough to start the RL baselines, so control work begins on Day 2 instead of Day 3.

---

## DAY 1 · `H+0 → H+24` — everything that accrues starts now

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+0 → H+1` | HUMAN | Keys into `dhakaflow/.env`; `python scripts/verify_keys.py`; **drag P2 bundle + `P2_sensor_graph_colab_drive.ipynb` to Drive, Run all** | Kaggle + road511 green; Colab job running |
| `H+0 → H+3` | BUILD | `road511_provider.py` (multi-jurisdiction, generalized from `ny511_provider.py`), rate-limited poller (30 req/min), incident delta-writer, camera snapshot grabber, fixture tests + live smoke | recorder launched |
| `H+3 → H+140` | COMPUTE | **road511 recorder runs continuously** — incident timeline + camera frames | 137 h of real data at presentation time |
| `H+1 → H+3` | HUMAN | Kaggle pulls: BNVD, Poribohon-BD, TFP-BD → checksums, licence capture, real-file audit; resolve the `Van` / `Easybike` taxonomy traps from real annotated crops | datasets pinned, taxonomy locked |
| `H+3 → H+5` | HUMAN+BUILD | VOC→YOLO conversion, frozen splits applied, class map locked, upload to Drive | P1 training set ready |
| `H+5 → H+6` | HUMAN | **P2 acceptance check** — MANIFEST, frozen-network checksum, acceptance gates | **P2 → PASS** |
| `H+6 → H+8` | BUILD | AWS spot bootstrap: launch template, S3 checkpoint bucket, 5-arm launcher, auto-resume on reclamation | infra ready *before* it is urgent |
| `H+8 → H+10` | HUMAN | Launch P1 fine-tunes (RT-DETR baseline + 2 variants), fair training-budget policy enforced | 3 arms training |
| `H+10 → H+13` | HUMAN | **REACT prototype on real live video** — pick a road511 camera whose incident feed says `cause: congestion`, run COCO-pretrained RT-DETR on the stream | a real jam detected on real live video, Day 1 |
| `H+13 → H+24` | COMPUTE | P1 fine-tunes + P2 remaining seeds + recorder | you sleep 7 h |

---

## DAY 2 · `H+24 → H+48` — perception and forecasting land

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+24 → H+26` | HUMAN | P1 triage → **detector winner**, per-class AP on rickshaw / CNG / easybike | **P1 gate** |
| `H+26 → H+28` | HUMAN | P2 output → BasicTS dual-format export (already validated); re-run floors on the full tensor | export verified |
| `H+28 → H+30` | HUMAN | **Launch P3 sweep on AWS** — STID → GWNet → DCRNN → STAEformer, official configs, 3 horizons, parallel arms | 4 arms training |
| `H+30 → H+34` | HUMAN+BUILD | ByteTrack wired to the winner; tracks → counting line → `TrafficObservation` on a TFP-BD clip **and** a live road511 stream | both paths produce observations |
| `H+34 → H+38` | HUMAN+BUILD | Sensing module: flow, speed proxy, queue, occupancy proxy, turning, vehicle mix | sensing gate |
| `H+38 → H+41` | HUMAN | **Twin calibration part A** — network-level against the live speed reference, no detector dependency | RL unblocked |
| `H+41 → H+43` | HUMAN | RL environment wiring; fixed-time + max-pressure smoke on the calibrated twin | baselines run clean |
| `H+43 → H+48` | HUMAN | **Launch 3 RL baseline arms on spot**, then sleep | training overnight |

---

## DAY 3 · `H+48 → H+72` — the long pole starts

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+48 → H+51` | HUMAN | P3 results → **forecasting winner**; masked MAE/RMSE at 5/15/30 min, MAPE with validity mask | **P3 gate** |
| `H+51 → H+54` | HUMAN+BUILD | Forecast feature plumbed into the RL observation — this is the *FA* in FA-MAPPO | observation contract updated |
| `H+54 → H+58` | HUMAN | **Twin calibration part B** — demand refinement from detector counts | **twin gate** |
| `H+58 → H+60` | HUMAN | **⚠ LAUNCH FA-MAPPO — 5 ablation arms in parallel on spot. THIS IS THE DEADLINE.** Missing it means no RL result at the presentation | 5 arms training, ~50 h ahead |
| `H+60 → H+64` | HUMAN | Routing joint gate — E4 DUE-vs-DSO (19.5–22.2%) re-evaluated with signal control active | **routing gate** |
| `H+64 → H+68` | HUMAN+BUILD | road511 incident → congestion-event labeller; build the real-jam evaluation set from 60+ h of recorded feed | labelled jam events |
| `H+68 → H+72` | — | sleep | |

---

## DAY 4 · `H+72 → H+96` — integration while RL trains

This is the day the system becomes the thing you described: *real traffic in, best
route out, works on a jam that already exists and on one that has not formed yet.*

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+72 → H+78` | HUMAN+BUILD | **REACT path, one command**: video or live stream → detect → track → sense → observe → reroute → delay metric | real number printed |
| `H+78 → H+84` | HUMAN+BUILD | **PREVENT path**: forecast 15/30 min → pre-emptive signal retiming + route spreading → delay metric | real number printed |
| `H+84 → H+88` | BUILD | Live-stream hardening: reconnect, dropped frames, dead streams. **Several cotrip cameras already return `video_url: null`** — filter on `is_active` + stream present, plus a health check | demo survives a dead stream |
| `H+88 → H+92` | HUMAN | **Domain-shift measurement** — Dhaka-trained detector on US road511 streams, reported as a finding (rickshaw/CNG/easybike do not exist there; degradation is *expected and measured*) | domain-shift table |
| `H+92 → H+96` | — | sleep | |

---

## DAY 5 · `H+96 → H+120` — results

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+96 → H+100` | HUMAN | RL triage. If arms are incomplete, report at the last checkpoint with an honest wall-clock note — **never extrapolate a curve** | control gate, honest |
| `H+100 → H+106` | HUMAN | Full benchmark matrix: every arm, multi-seed, identical demand (`BenchmarkSpec.assert_fair()`), significance tests | results table |
| `H+106 → H+110` | HUMAN+BUILD | NLP incident extractor on road511 incident text + grounded copilot (`ANTHROPIC_API_KEY`) | **NLP/GenAI gate** |
| `H+110 → H+114` | BUILD | Figures: MFD, forecast curves, RL learning curves, before/after routing, live-demo captures | figure set |
| `H+114 → H+120` | — | sleep | |

---

## DAY 6 · `H+120 → H+140` — evidence and freeze

| Hours | Lane | Task | Done when |
|---|---|---|---|
| `H+120 → H+126` | HUMAN+BUILD | `INTERVIEW_CARD.md` per component — all 12 questions, **including the result actually obtained and the main weakness** | LEARNING_PASS ×N |
| `H+126 → H+130` | BUILD | Provenance bundle: checksums, upstream pins, one-command reproduce script | reproducible |
| `H+130 → H+134` | HUMAN | Results tables + **limitations section**: domain shift, synthetic demand, `IMPORTED_HEURISTIC` signal timings, no real Dhaka signal plans, OSM attribute gaps (lanes 22.1%, maxspeed 12.8%) | limitations written |
| `H+134 → H+138` | HUMAN | **Dry-run the live demo three times.** It must survive a dead stream on stage | demo rehearsed |
| `H+138 → H+140` | HUMAN | Freeze, tag, final status board | sprint closed |

---

## Compute lane — what runs when

| Job | Window | Parallelism | GPU-h |
|---|---|---|---|
| road511 recorder | `H+3 → H+140` | 1 (CPU) | — |
| P2 twin generation | `H+1 → H+10` | Colab CPU | — |
| P1 detector fine-tune | `H+8 → H+26` | 3 arms | ~54 |
| P3 forecasting sweep | `H+30 → H+48` | 4 arms | ~72 |
| RL baselines | `H+43 → H+96` | 3 arms | ~110 |
| **FA-MAPPO ablation** | `H+60 → H+110` | **5 arms** | **~250** |
| | | **Total** | **~430 GPU-h** |

Cost on `g5.xlarge` spot at ~$0.30–0.40/h ≈ **$110–140** of the $200 AWS credit.
Every job checkpoints to S3 — spot instances get reclaimed, and a reclaimed job
that cannot resume is a lost day.

---

## Scope cuts, made deliberately

| Cut | Kept instead | Why |
|---|---|---|
| 11-model forecasting sweep | 4 graph models + 2 floors | Four models with honest masked metrics beat eleven half-run |
| Multi-city generalization study | One extra jurisdiction as a domain-shift table | One table, not a work stream |
| More datasets for their own sake | **6 sources, each with a defined role** | Every source must survive "why is this here?" |

**The six sources and their roles:** UTD19 (frozen traffic science) · BNVD +
Poribohon-BD + TFP-BD (Dhaka perception) · twin-generated 250-node graph
(forecasting, per risk R1) · road511 (live streams, incidents, real jam labels).

---

## Honesty locks — non-negotiable

* **road511 is US data.** Classification `PROVIDER_INTEGRATION_VALIDATION` and
  **domain-shift measurement**. Never `DHAKA_LIVE_CAMERA_VALIDATION`. Every Dhaka
  claim rests on BD datasets + the frozen R1 twin. A committee member will ask;
  "we measured domain shift deliberately" is a strong answer, "we validated on
  Colorado" is a fatal one.
* **Frozen labs stay frozen** — `git diff paper_labs/00* 01* 02*` must be empty.
  *(Currently NOT empty — `Lab00_UTD19_Colab.ipynb` has uncommitted changes.
  Resolve before `H+6`.)*
* No PASS without its acceptance tests actually passing.
* Mock/fixture data verifies integration only — never marks an experiment PASS.
* Partial RL results are reported at their checkpoint. No extrapolated curves.

---

## Sprint risk register

| # | Risk | Mitigation |
|---|---|---|
| S1 | **FA-MAPPO launches after `H+60`** | Hard deadline. Twin part A/B split exists precisely to protect it |
| S2 | Spot reclamation mid-run | Checkpoint every N steps to S3; auto-resume in the launcher |
| S3 | Colab session limits kill the P2 job | Output to Drive, never session storage |
| S4 | road511 rate limit (30/min) | 1 incident sweep/min + round-robin camera snapshots |
| S5 | Dead camera streams | Filter `is_active` + non-null `video_url`; live health check; demo fallback clip |
| S6 | RL does not converge in 50 h | Baselines + routing + forecasting already carry a defensible system. RL is upside, not foundation |
| S7 | Sleep debt → silent errors | 7 h/night is in the plan. A tired mistake on Day 5 costs more than the hours it saves |
