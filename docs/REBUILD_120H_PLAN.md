# DhakaFlow — 120-Hour Rebuild Plan (3 people × 5 days × 8 h)

**Written 2026-09-01. Deadline assumed 2026-09-06 morning.**
**Thesis in one sentence:** *Predict congestion 15–60 min ahead with a spatio-temporal
GNN, route vehicles on the **predicted** (not current) travel times, deliver the
advice over V2X, ingest incident text with NLP — and prove, in a SUMO twin of real
Dhaka roads with paired seeds, that vehicles wait less.*

---

## 0. Why the current repo reads as "0" (verified today, not guessed)

| Problem | Evidence |
|---|---|
| **Nothing headline is reproducible from a clone.** No trained weights are in the repo (`artifacts/p1_winner/` holds only a `.sha256`; GWNet checkpoint only in a dead `/workspace`; the P2 sensor dataset is 48 KB of manifests). An examiner cannot regenerate mAP 0.711, MAE 0.44 or −19.5 %. | `ls artifacts/p1_winner`, `docs/CURRENT_SYSTEM_GAP_AUDIT.md` F17/F24 |
| **Scope drift.** Last 2 weeks went to Athens drone data + signal-timing calibration (STEP1–3). The stated topic is *prediction + route optimisation*. | git log `f6aea59…be937d0` |
| **The audit itself lists 6 BLOCKERs**, incl. "UI claims nothing pre-baked while the twin runs canned demand + fixed seed". | `docs/CURRENT_SYSTEM_GAP_AUDIT.md` F1,F2,F10,F14,F16,F19,F25 |
| **Unreadable surface.** 47 scripts, 22 sub-packages, 8 "gates", 20 docs, honesty labels everywhere. A reader cannot find *the model / the dataset / the results table / the demo* in 5 minutes. | `ls scripts dhakaflow docs` |
| **Forecasting numbers are on simulated data only**; no standard benchmark (METR-LA / PEMS) comparison exists, so the ML chapter has nothing an examiner can compare to literature. | `docs/RESULTS_MATRIX.md` |
| Tests: 158/163 pass; the 5 failures are structural (missing `model_registry/`, `dashboard/`, `deployment/`, large files). | `pytest tests` today |

**What is genuinely good and will be reused (do not rebuild):**

* `paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml` — real Dhaka R1 SUMO network, 6,527 edges, left-hand, frozen.
* `research/twin/sensor_graph.py` — 250 virtual sensors + DCRNN-recipe adjacency → METR-LA-shaped dataset from the twin.
* `research/forecasting/basicts_adapter.py`, `notebooks/P3_forecasting_colab.ipynb` — BasicTS export + Colab path (already ran once).
* `scripts/run_due_dso.py` (duaIterate DUE/DSO), `scripts/gate7_dynamic_routing.py` (TraCI compliance ladder), `research/routing/r1_router.py` (TD-Dijkstra on R1), `artifacts/gates/routes_repeat_1h.rou.xml.gz` (1 h demand).
* `artifacts/mosaic_dhaka/dhaka_r1` — **official Eclipse MOSAIC 25.2 already runs on the Dhaka net** (DENM broadcast → 886 route switches). `research/networking/v2x_bus.py` latency injector.
* `dhakaflow/live/google_providers.py` + Google Routes key — live Dhaka *reference verdicts* (Google ToS forbids caching/ML-training on their content; keep it as validation only).
* Upstream pins in `~/.dhakaflow/upstream`: BasicTS, Graph-WaveNet, DCRNN, STID, STAEformer, sumo-rl, mosaic, chronos-forecasting.

**Dropped from the 5-day critical path:** RT-DETR perception (weights missing
locally), pNEUMA/Athens calibration, FA-MAPPO signal RL, and the 8-gate web app.
They remain in the repo for appendix evidence, but the rebuild does not depend
on them. Do not move working folders into `legacy/` until the rebuild path has
passed.

---

## 1. The papers we build on (all repos verified live on 2026-09-01)

### 1.1 Traffic prediction (ML/DL) — harness: **BasicTS** (TKDE 2024) `github.com/GestaltCogTeam/BasicTS`

| Paper | Venue | Official code | Published MAE (METR-LA 15/30/60 min) | Colab cost |
|---|---|---|---|---|
| **STID** (Shao et al.) | CIKM 2022 | `GestaltCogTeam/STID` | ≈2.8/3.2/3.6 | minutes |
| **Graph WaveNet** (Wu et al.) | IJCAI 2019 | `nnzhan/Graph-WaveNet` | 2.69/3.07/3.53 | 1–2 h |
| **DCRNN** (Li et al.) | ICLR 2018 | `liyaguang/DCRNN` (use BasicTS PyTorch port) | 2.77/3.15/3.60 | 1–2 h |
| **AGCRN** (Bai et al.) | NeurIPS 2020 | `LeiBAI/AGCRN` | no predefined graph needed | 1 h |
| **STAEformer** (Liu et al.) | CIKM 2023 | `XDZhelheim/STAEformer` | SOTA-class transformer | 2–3 h |
| **Chronos-Bolt** zero-shot (Ansari et al., Amazon) | 2024 | `amazon-science/chronos-forecasting` | — (our novelty comparison) | inference only |

Datasets: METR-LA, PEMS-BAY, PEMS08 (auto-download in BasicTS). **There is no public Dhaka
time-series dataset** — Dhaka series come from our twin (`sensor_graph.py`), labelled simulated.

### 1.2 Route optimisation

| Paper / tool | Venue | Code | Role |
|---|---|---|---|
| **SUMO duarouter / duaIterate.py / marouter** (Lopez et al.) | ITSC 2018 | `eclipse-sumo/sumo` `tools/assign/` | time-dependent shortest path with `--weight-files` = **predicted** travel times; DUE and DSO (`--marginal-cost`) baselines |
| **ETA prediction with GNNs in Google Maps** (Derrow-Pinion et al.) | CIKM 2021 | none | motivation: route on forecasts, not current speeds |
| **URB — Urban Routing Benchmark** (Kucharski lab) | NeurIPS 2025 D&B | `COeXISTENCE-PROJECT/URB` | evaluation protocol + the honest finding that MARL routing rarely beats humans (so we do *not* bet the thesis on RL) |
| **RouteRL** | SoftwareX 2025 | `COeXISTENCE-PROJECT/RouteRL` | optional stretch: RL route-choice arm |

### 1.3 Networking (V2X)

| Paper / tool | Code | Role |
|---|---|---|
| **Eclipse MOSAIC** (Fraunhofer FOKUS) | `eclipse-mosaic/mosaic` — already running on Dhaka R1 | DENM broadcast of predicted congestion → NavigationModule reroute; **penetration-rate and latency/loss sweeps** |
| MOSAIC V2X urban case study (Iași, 2025, PMC12431397) | — | reference numbers (−18 % time loss with full V2X) |

### 1.4 NLP

| Paper / dataset | Code | Role |
|---|---|---|
| **L-TWITS** traffic-tweet incident dataset (IIT-H, ITSC 2020) / Belgian traffic tweets (3-class) | public | fine-tune **DistilBERT** → {incident, congestion, irrelevant} + location extraction |
| **TrafficGPT** (Zhang et al. 2023) `lijlansg/TrafficGPT`, **Open-TI** `DaRL-LibSignal/OpenTI` | verified | prompt patterns for the *LLM copilot* that explains reroutes from run logs (stretch) |

---

## 2. Target architecture (one causal chain, four chapters)

```
 twin sensors (250 × 5-min) ──► PREDICT  STGNN (GWNet/STAEformer)  ──► edge × interval travel-time table
                                   │ benchmarked on METR-LA / PEMS-BAY vs literature
 incident text ──► NLP DistilBERT ─┤ (blocked/slow edges injected into the table)
                                   ▼
                          ROUTE   duarouter --weight-files  |  TraCI setAdaptedTraveltime + rerouteTraveltime
                                   │ arms: B1 static · B2 reactive · B3 DUE · B4 DSO · **P predictive**
                                   ▼
                          NETWORK MOSAIC V2X (DENM) delivers advice; penetration p ∈ {0,10,25,50,100}%, latency/loss sweep
                                   ▼
                          PROVE   SUMO Dhaka R1, 10 paired seeds, tripinfo → mean/p95 travel time, waiting time, throughput, Wilcoxon
```

Clean active layer (reuses the existing project; no mass move first):

```
predict/    configs, colab notebook, forecast_to_weights.py, results/
route/      predictive_routing.py (all arms), stats.py, results/
network/    mosaic scenario, penetration_sweep.py, latency_injection.py, results/
nlp/        train_classifier.py, event_feed.py, copilot.py, results/
demo/       streamlit app (map · forecast · before/after · event feed)
results/RESULTS.md   ONE file: every number → one command → one evidence file
paper/      thesis chapters + slides
Makefile    make data · make predict · make route · make network · make nlp · make live-summary · make results
```

Examiner test we design for: **clone → `bash download_assets.sh` → `make results`**
aggregates every checked-in evidence table quickly. Local non-billed
regeneration uses `make local-results`. Live Google reference capture is
separate as `make live-capture` so quota is never spent accidentally.

---

## 3. Team split

| Person | Owns | Machine |
|---|---|---|
| **A — Prediction (ML/DL)** | BasicTS benchmark, Chronos, twin-data forecaster, forecast→weights export | Colab Pro (A100/L4), Drive |
| **B — Routing + Twin** | SUMO experiment harness, 5 arms, paired seeds, stats, before/after movie | Mac + AWS c6i/c7g spot (SUMO is CPU-bound) |
| **C — NLP + Networking + Integration** | DistilBERT incident classifier, MOSAIC sweeps, demo app, RESULTS.md, thesis/slides | Mac + Colab (small GPU) |

Daily 15-min sync at 09:00 and 21:00. Every deliverable = a command + a JSON/CSV in `*/results/` + one line in `results/RESULTS.md`.

---

## 4. Hour-by-hour (each person 8 h/day; H = hours into the sprint for that person)

### DAY 1 (H0–8) — freeze legacy, stand up each pipeline end-to-end on tiny data

| Person | Hours | Task | Done when |
|---|---|---|---|
| ALL | 0–1 | create/confirm branch `rebuild-120h`; keep existing `dhakaflow/`, `research/`, `scripts/`, `paper_labs/` in place; create/confirm the active layer (`predict/`, `route/`, `network/`, `nlp/`, `demo/`, `results/`, `paper/`) and `Makefile` skeleton | `make -n results` lists all targets |
| A | 1–3 | Colab: clone BasicTS @ pinned commit, `pip install -e .`, prepare METR-LA / PEMS-BAY / PEMS08 | data dirs exist, 1 epoch STID runs |
| A | 3–8 | Launch **STID + GWNet on METR-LA and PEMS-BAY** (full epochs, official configs). Save ckpts + test logs to Drive | 4 runs training; Drive folder `predict/ckpt/` |
| B | 1–4 | `route/predictive_routing.py`: load R1 net + `routes_repeat_1h`, run arm B1 (static) and B2 (reactive `rerouteTraveltime(currentTravelTime=True)`, p=30 %), parse `tripinfo` → JSON | both arms run 1 seed, metrics JSON written |
| B | 4–8 | Add B3 DUE / B4 DSO via `duaIterate.py` (reuse `run_due_dso.py`), cap iterations, log convergence; add `--seeds` and paired-run driver (multiprocessing) | 4 arms × 1 seed complete |
| C | 1–3 | Download L-TWITS / Belgian tweets; clean to 3 classes; frozen train/val/test split with sha256 | `nlp/data/MANIFEST.json` |
| C | 3–6 | Fine-tune DistilBERT (Colab T4, ~20 min); report accuracy/F1 vs TF-IDF+LogReg baseline | `nlp/results/classifier.json` |
| C | 6–8 | Re-run existing MOSAIC Dhaka scenario once to confirm the stack still works; record wall time | `network/results/smoke.json` |

### DAY 2 (H8–16) — the predictive arm exists; full benchmark running

| Person | Hours | Task | Done when |
|---|---|---|---|
| A | 8–10 | Collect Day-1 results into `predict/results/benchmark.csv` (model × dataset × horizon: MAE/RMSE/MAPE) next to published numbers | table has 2 models × 2 datasets |
| A | 10–13 | Launch **STAEformer + AGCRN + DCRNN** (METR-LA, PEMS-BAY, PEMS08) — overnight compute | 9 runs queued (~10 GPU-h) |
| A | 13–16 | **Chronos-Bolt zero-shot** on the same test windows; add row to benchmark | MAE row for Chronos |
| B | 8–12 | Generate twin sensor data on R1 with `sensor_graph.py`: 8 h × 3 seeds × 250 sensors at the SAME demand scale as the routing arms (`route/results/SCALE_CHOICE.json` = 0.25), sensors placed by observed flow (`--place-by-flow`, 84 % coverage); export BasicTS format; hand to A (Drive) | `predict/data/dhaka_twin/` + sha256, `MANIFEST.acceptance.verdict = PASS` |
| B | 12–16 | **Arm P (predictive)**: `predict/forecast_to_weights.py` converts a forecast (start with the *oracle*: next-interval true edge times from the twin, then the real model) into SUMO `--weight-files` `<interval>` XML; TraCI loop every 60 s: `setAdaptedTraveltime` + `rerouteTraveltime(currentTravelTime=False)` for equipped vehicles, staggered | Arm P runs with oracle forecast, 1 seed |
| C | 8–11 | `nlp/event_feed.py`: classifier + spaCy/regex location → JSON event; map named places to R1 edges (Karwan Bazar, Shahbagh, Farmgate…); event ⇒ edge slowdown factor in the weight table | 20 test tweets → correct edges |
| C | 11–16 | `network/penetration_sweep.py`: parametrise MOSAIC mapping config for p ∈ {0,10,25,50,100} %, 3 seeds; parse MOSAIC output for **delivery ratio, mean latency, route switches, travel time** | 1 sweep point runs end-to-end |

### DAY 3 (H16–24) — real forecaster in the loop; all sweeps launched

| Person | Hours | Task | Done when |
|---|---|---|---|
| A | 16–20 | Train GWNet (+STID) on **Dhaka twin data**; horizons 5/15/30/60 min; vs persistence & historical-average floors | `predict/results/dhaka_twin.csv` |
| A | 20–24 | Export the Dhaka model's rolling forecasts for the routing scenario window as the weight table (`forecast_to_weights.py --model gwnet`); hand to B | `route/weights/gwnet_*.xml` |
| B | 16–20 | Run **all 5 arms × 10 seeds** on AWS spot (8–16 vCPU); `route/stats.py`: mean & p95 travel time, total waiting time, throughput, teleports; paired Wilcoxon + bootstrap CI | `route/results/arms_10seeds.json` |
| B | 20–24 | Compliance/penetration sweep for arm P (p = 10/25/50/100 %) — Braess/oscillation check (staggered rerouting) | curve JSON |
| C | 16–20 | Launch full MOSAIC sweep on AWS/Mac overnight (15 runs × ~35 min); **latency/loss injection** via `v2x_bus.py` distribution → routing benefit vs latency curve | sweep running |
| C | 20–24 | `demo/app.py` (Streamlit): Dhaka map (pydeck), sensor forecast plot, before/after trajectories, event feed panel, arms comparison chart | demo runs locally on Day-3 artefacts |

### DAY 4 (H24–32) — results locked, writing starts

| Person | Hours | Task | Done when |
|---|---|---|---|
| A | 24–28 | Ablations: horizon vs routing gain (5/15/30/60 min forecasts as weights); forecast error → routing benefit plot | `predict/results/ablation_horizon.csv` |
| A | 28–32 | Write **Chapter 4 Prediction** (method, benchmark table, Dhaka-twin table, Chronos discussion, limits) | draft in `paper/` |
| B | 24–28 | Re-run arm P with real GWNet weights + NLP incident scenario (one blocked edge at Karwan Bazar, 10 seeds); final table | `route/results/final.json` |
| B | 28–32 | Before/after SUMO movie (reuse `render_branch_movie.py`) + write **Chapter 5 Routing** | movie mp4 + draft |
| C | 24–28 | Collect MOSAIC sweep → `network/results/penetration.csv`, latency curve figure; write **Chapter 6 Networking** | draft |
| C | 28–32 | Write **Chapter 7 NLP**; `results/RESULTS.md` (every number → command → file); LLM copilot stretch (Claude API over run logs, 2 h max) | RESULTS.md complete |

### DAY 5 (H32–40) — reproducibility, presentation, buffer

| Person | Hours | Task | Done when |
|---|---|---|---|
| ALL | 32–34 | **Fresh-clone test** on a clean machine/Colab: `bash download_assets.sh && make results` must rebuild the evidence index; `make local-results` regenerates non-billed tables where local dependencies are installed | passes, timed |
| A | 34–38 | Slides 1–8 (problem, data, prediction results) + speaker notes | deck |
| B | 34–38 | Slides 9–14 (routing proof, movie, stats) + live demo rehearsal | deck |
| C | 34–38 | Slides 15–20 (V2X, NLP, architecture, limitations, future work); README rewrite (1 page: what, how to run, results table, figures) | README |
| ALL | 38–40 | Buffer / Q&A drill (`docs/INTERVIEW_CARDS.md` pattern) | — |

---

## 5. Compute & budget plan

| Resource | Use | Estimate |
|---|---|---|
| **Colab Pro** (A100/L4) | BasicTS runs: STID ×3 (0.5 h), GWNet ×4 (6 h), STAEformer ×3 (7 h), AGCRN/DCRNN ×4 (5 h), Dhaka-twin runs (3 h), Chronos (0.5 h) | ≈ 22 GPU-h over Days 1–3 (run overnight) |
| **AWS credit ($200)** | SUMO paired runs: 5 arms × 10 seeds × 1 h sim ≈ 50 runs × ~6 min on c6i.4xlarge (16 vCPU, spot ≈ $0.25/h) ≈ 1 h wall; sweeps ≈ 3 h; MOSAIC 15 runs ≈ 9 h on 1 box | < $20 |
| **Google Routes ($600 credit)** | 6 R1 corridors every 15 min for 5 days ≈ 2,900 calls ≈ $15 — used **only as a live reference verdict** (ToS: no caching/ML) | $15 |
| **2 TB Drive** | METR-LA/PEMS (≈1 GB), checkpoints (≈2 GB), twin sensor data (≈1 GB), MOSAIC logs (≈5 GB) | trivial |
| **Claude API** (optional) | copilot stretch | $5 |

---

## 6. Acceptance criteria (what "not 0" means, in numbers)

1. **Prediction table**: ≥ 4 models × 2 real benchmarks × 3 horizons, each within 10 % of the published MAE (proves the pipeline is correct), + Chronos zero-shot row, + Dhaka-twin table with floors.
2. **Routing table**: 5 arms × 10 paired seeds on real Dhaka R1; predictive arm beats reactive on mean *and* p95 travel time with p < 0.05 (Wilcoxon) — or an honest negative result with the horizon ablation explaining why.
3. **Networking curve**: delivery ratio and routing benefit vs penetration rate (5 points × 3 seeds) and vs injected latency (3 points).
4. **NLP**: classifier F1 on held-out test vs TF-IDF baseline; 1 end-to-end incident scenario (text → edge → reroute → measured delay change).
5. **Reproducibility**: fresh clone + `make results` rebuilds the evidence index in < 30 min; `make local-results` regenerates local non-billed tables where dependencies are installed.
6. **Demo**: 3-minute live run in Streamlit + a 60-second movie.

## 7. Risks & fallbacks

| Risk | Fallback |
|---|---|
| Predictive arm ≠ better than reactive | Report it honestly with the oracle-forecast arm as the upper bound; the horizon ablation *is* a result |
| duaIterate does not converge on 6,527 edges in time | cap at 20 iterations, report convergence curve; use `marouter` for DSO reference |
| MOSAIC sweep too slow (35 min/run dense) | reduce to 3 penetration points × 2 seeds, 600 s horizon |
| STAEformer too slow on Colab | drop to GWNet + STID + AGCRN (still 3 models) |
| Tweet datasets unavailable | scrape 500 traffic posts (Dhaka Traffic Update FB/X pages), label 3 classes in 2 h with 3 people |
| Colab session limits | checkpoints to Drive every epoch (BasicTS does this); resume |

## 8. First 60 minutes (start now)

```bash
git status --short
git checkout -b rebuild-120h  # only if the branch does not already exist
mkdir -p predict route network nlp demo results paper
PYTHONPATH=. pytest tests/platform/test_interfaces.py tests/platform/test_repo_architecture.py -q
# Person B: smoke the routing harness on the real network today
python route/predictive_routing.py --arm static --seed 11 --horizon 1800   # created below
# Person A: open notebooks/Predict_BasicTS_Colab.ipynb in Colab Pro, Run all
# Person C: start the Google reference recorder (accrues by wall-clock) and download the tweet datasets
```
