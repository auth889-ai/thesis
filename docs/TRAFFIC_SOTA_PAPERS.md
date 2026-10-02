# Road-traffic forecasting: the world's best papers with official code, and the order we implement them

Thesis topic: **road traffic forecasting** (speed and flow on sensor networks, then on a live city). Everything below is a
paper with an official implementation that we run unchanged (`official-implementation-policy`), scored under one
protocol (`results/forecasting/benchmark_floors.md`: chronological 70/10/20, 12 input steps, horizons 15/30/60 min,
observed entries only). One model per phase; a phase ends with its reproduction table, checkpoint hash, log and commit.

Written 2026-10-02 from a fresh literature search. Verified links and licences are re-checked at the start of each phase.

## 1. What is already reproduced (do not redo)

| Model | Venue | Dataset | Our MAE 15/30/60 | Published | Status |
|---|---|---|---|---|---|
| GWNet | IJCAI 2019 | METR-LA | 2.72 / 3.11 / 3.59 | 2.69 / 3.07 / 3.53 | reproduced within 2 %, `trained_results.csv` |
| GWNet | IJCAI 2019 | PEMS-BAY | 1.31 / 1.64 / 1.95 | 1.30 / 1.63 / 1.95 | reproduced |
| STID | CIKM 2022 | METR-LA, PEMS-BAY | 2.82 / 3.21 / 3.59 ; 1.32 / 1.64 / 1.92 | 2.82 / 3.19 / 3.55 (METR-LA) | reproduced |
| STAEformer | CIKM 2023 | METR-LA | 2.67 / 2.98 / 3.35 | 2.65 / 2.97 / 3.34 | reproduced |
| OpenCity | arXiv 2024 (HKUDS) | PEMS07M zero-shot | exact published figure | exact | gate closed, four cities |
| Chronos (Bolt) | TMLR 2024 | METR-LA 80-node protocol | worse than persistence at 15 min | — | negative result, kept |
| Floors | — | METR-LA, PEMS-BAY | HA matches published within 1–5 % | — | protocol validated |

## 2. The catalogue: best papers, official code, licence, why it matters

### Tier A — the models every traffic paper compares against (BasicTS has all of them, official configs)

| # | Paper | Venue | Official code | Licence | Why it is in the list |
|---|---|---|---|---|---|
| A1 | DCRNN, Li et al. | ICLR 2018 | liyaguang/DCRNN; BasicTS baseline | MIT | defined METR-LA / PEMS-BAY and the protocol everyone uses |
| A2 | STGCN, Yu et al. | IJCAI 2018 | VeritasYin/STGCN_IJCAI-18; BasicTS | BSD-2 | first graph-conv traffic model |
| A3 | Graph WaveNet | IJCAI 2019 | nnzhan/Graph-WaveNet; BasicTS | MIT | adaptive adjacency; **done** |
| A4 | AGCRN | NeurIPS 2020 | LeiBAI/AGCRN; BasicTS | MIT | node-adaptive parameters |
| A5 | MTGNN | KDD 2020 | nnzhan/MTGNN; BasicTS | MIT | graph learning without a prior graph |
| A6 | STNorm | KDD 2021 | JLDeng/ST-Norm; BasicTS | MIT | normalisation as the model |
| A7 | D2STGNN | VLDB 2022 | zezhishao/D2STGNN; BasicTS | Apache-2.0 | decoupled diffusion / inherent signals |
| A8 | STID | CIKM 2022 | zezhishao/STID; BasicTS | Apache-2.0 | MLP + identity embeddings beats most GNNs; **done** |
| A9 | STAEformer | CIKM 2023 | XDZhelheim/STAEformer; BasicTS | Apache-2.0 | vanilla Transformer + adaptive embedding; **done** |
| A10 | MegaCRN | AAAI 2023 | deepkashiwa20/MegaCRN; BasicTS | MIT | meta-graph memory, robust to non-stationarity |

### Tier B — 2024–2025 state of the art (official code, mostly in BasicTS)

| # | Paper | Venue | Official code | Licence | Why |
|---|---|---|---|---|---|
| B1 | STD-MAE, Gao et al. | IJCAI 2024 | Jimmy-7664/STD-MAE; BasicTS | Apache-2.0 | masked pre-training that lifts STID / STAEformer |
| B2 | HimNet, Dong et al. | KDD 2024 | XDZhelheim/HimNet; BasicTS | Apache-2.0 | heterogeneity-informed meta-parameters; strong on PEMS |
| B3 | BigST, Han et al. | VLDB 2024 | usail-hkust/BigST; BasicTS | MIT | linear-complexity for thousands of sensors |
| B4 | STPGNN | AAAI 2024 | BasicTS | — | pivotal-node graph |
| B5 | STDN | AAAI 2025 | BasicTS | — | newest BasicTS spatial-temporal baseline |
| B6 | STGformer, Wang et al. | arXiv 2024 | Dreamzz5/STGformer | MIT | one-layer graph transformer, efficient on LargeST |
| B7 | PatchSTG, Fang et al. | KDD 2025 | LMissher/PatchSTG | unspecified → ask authors / use as reference only | current best on LargeST; KD-tree spatial patching |
| B8 | RPMixer, Yeh et al. | KDD 2024 | authors' site | — | all-MLP random projections for large graphs |
| B9 | LargeST benchmark, Liu et al. | NeurIPS 2023 | liuxu77/LargeST | code MIT, data CC BY-NC 4.0 | 8,600-sensor California; SD / GBA / GLA / CA |

### Tier C — foundation models and zero-shot (official checkpoints)

| # | Paper | Venue | Official code | Licence | Why |
|---|---|---|---|---|---|
| C1 | OpenCity, Li et al. (HKUDS) | arXiv 2024 | HKUDS/OpenCity + HF checkpoints | — | spatio-temporal foundation model; **reproduced exactly** |
| C2 | UniST, Yuan et al. | KDD 2024 | tsinghua-fib-lab/UniST | MIT | prompt-empowered universal model, grid data |
| C3 | UrbanGPT, Li et al. | KDD 2024 | HKUDS/UrbanGPT | — | LLM + spatio-temporal instruction tuning |
| C4 | UniFlow, Yuan et al. | 2025 | YuanYuan98/UniFlow | — | unified grid + graph flow foundation model |
| C5 | Chronos-2 (Amazon) | 2025 | amazon-science/chronos-forecasting | Apache-2.0 | strongest zero-shot univariate; probabilistic |
| C6 | TimesFM 2.5 / 3 (Google) | 2025–26 | google-research/timesfm | Apache-2.0 | zero-shot, beats supervised baselines on periodic traffic |
| C7 | Moirai 2 (Salesforce) | 2025 | SalesforceAIResearch/uni2ts | Apache-2.0 | in BasicTS universal set |
| C8 | TimeMoE | ICLR 2025 | Time-MoE/Time-MoE; BasicTS | Apache-2.0 | mixture-of-experts foundation model |
| C9 | "Time Series Foundation Models as Strong Baselines in Transportation", Yanes-Pulido & Rodrigues | 2026 | arXiv 2602.24238 | — | Chronos-2 zero-shot: METR-LA MAE 18.83 at 1 h horizon protocol; defines the FM-vs-supervised comparison |
| C10 | "Do TSFM benchmarks hide regime-dependent failures?" | ICML 2026 wksh | arXiv 2606.18367 | — | transition MAE 11 mph vs 3 overall; 90 % intervals cover 55 % at transitions — **this is our gap** |

### Tier D — uncertainty, the thesis contribution layer

| # | Paper / tool | Official code | Licence | Use |
|---|---|---|---|---|
| D1 | MAPIE (conformal prediction) | scikit-learn-contrib/MAPIE | BSD-3 | calibrated p10/p50/p90 on top of any Tier A–C model |
| D2 | Conformal train-delay forecasting (Springer 2025) | — | — | the methodology precedent: 90 % window validated on 12.8 M records |
| D3 | Bimodal mixture augmentation (from C10) | — | — | post-hoc fix for transition coverage; we reproduce the idea against our onset metric |

## 3. The thesis gap, stated once

Every leaderboard reports aggregate MAE. The 2026 regime paper shows aggregate MAE hides the thing a traveller cares
about: the **transition** from free flow to congestion, where errors triple and intervals collapse. Our evaluation
already scores exactly that (`model_comparison.md`: congestion MAE, onset detection, mean lead), and it already shows
Chronos losing to persistence on onset. The thesis question becomes:

> Across the best supervised spatio-temporal models (Tier A–B) and the best foundation models (Tier C), who detects
> congestion onset, how early, and with calibrated intervals? And does conformal calibration per regime (Tier D) repair the
> coverage without hurting aggregate accuracy?

This is a question nobody has answered on a shared protocol with official code, and every row of the answer is a
reproduction of a world-best model, which is what the user asked for.

## 4. The phases (one model each, official code unchanged)

Each phase: pin the official repo (commit + licence in `upstream/UPSTREAM_PINS.yaml`), run the official example
unchanged, reproduce the published table on METR-LA and PEMS-BAY, then score it on our onset protocol, write the
mini-report, commit, stop.

| Phase | Model | Code | Compute | Exit |
|---|---|---|---|---|
| T1 | DCRNN (A1) | BasicTS `baselines/DCRNN` | Colab T4, ~3 h | MAE within 3 % of published; onset row added |
| T2 | D2STGNN (A7) | BasicTS | Colab, ~4 h | same |
| T3 | MegaCRN (A10) | BasicTS | Colab | same |
| T4 | STD-MAE (B1) | BasicTS | Colab, pre-train + fine-tune | same; lifts STID/STAEformer rows |
| T5 | HimNet (B2) | BasicTS | Colab | same |
| T6 | BigST (B3) on LargeST-SD (B9) | BasicTS large-scale configs | Colab A100 or g5.2xlarge | LargeST-SD published row reproduced |
| T7 | STGformer (B6) on LargeST-SD | official repo | same | published row |
| T8 | PatchSTG (B7) | official repo, reference only until licence answered | same | published row or documented block |
| T9 | Chronos-2 (C5) and TimesFM 2.5 (C6) zero-shot | official checkpoints | Colab | reproduce C9's METR-LA numbers; onset rows |
| T10 | UniST (C2) | official repo | Colab | published grid result reproduced |
| T11 | Conformal per regime (D1, D3) | MAPIE | CPU | coverage 90 % at transitions on every model in the table |
| T12 | Cross-city: best three models on the recorded Dhaka corridor | our adapters | CPU/Colab | the live-city table; Google-Routes history never used for training |

Compute: Colab first (`colab-execution-policy`), AWS g5 only for LargeST (within `docs/RESOURCES.md`).

## 5. Sources checked for this catalogue

BasicTS model list (GestaltCogTeam/BasicTS README, read 2026-10-02); LargeST README; PatchSTG README; OpenCity README;
arXiv 2602.24238; arXiv 2606.18367; arXiv 2412.09972 (PatchSTG); arXiv 2410.00385 (STGformer); arXiv 2405.10800
(HimNet); arXiv 2312.00516 (STD-MAE); arXiv 2402.11838 (UniST); arXiv 2403.00813 (UrbanGPT); arXiv 2411.12972 (UniFlow);
arXiv 2510.15821 (Chronos-2). Licences marked "—" are to be read from the LICENSE file at pin time; a repo without a
licence is reference-only.
