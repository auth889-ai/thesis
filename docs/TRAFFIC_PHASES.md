# Road-traffic thesis: the phases, each one paper, its official code, and the web feature it delivers

Written 2026-10-02. Every repository below was checked on that date (exists, licence from the GitHub API, last push).
Rule for every phase: pin commit + licence in `upstream/UPSTREAM_PINS.yaml` → run the official example unchanged →
reproduce the published table → score on our shared protocol → wire ONE web feature → tests → mini-report → commit → stop.
Training runs on AWS GPU (g5 / g4dn, inside `docs/RESOURCES.md`) or Colab; nothing heavy runs on the local PC.

Licence note. Repos marked **NONE** have no LICENSE file. We never copy their code. Where BasicTS (Apache-2.0,
[GestaltCogTeam/BasicTS](https://github.com/GestaltCogTeam/BasicTS)) ships the same model as an official baseline, we run
it through BasicTS; otherwise the repo is used only as a pinned external checkout, never vendored.

## Part A · The web project: every feature, and the phase that makes it real

| # | Feature (what the person sees) | Backed by | Phase |
|---|---|---|---|
| F1 | Live traffic map of any city: speed per road now, data age shown | OSM + Amazon Location + recorded corridors | exists |
| F2 | Forecast map: every sensor/road 15, 30, 60 min ahead, slider over time | the serving model from the phase table | P1 → P9 |
| F3 | Model leaderboard page: every reproduced paper, our number vs published, gap % | `results/forecasting/trained_results.csv` | every phase adds a row |
| F4 | Congestion-onset page: which model sees the jam first, lead time, per road | onset scorecard | P2 |
| F5 | Uncertainty band on every forecast: p10 / p50 / p90, calibrated, coverage shown | conformal layer | P8 |
| F6 | Route and departure advice: "leave by 8:12, arrive by 9:00 with 90 %" | forecast + routing engine | P8 |
| F7 | Large-scale mode: thousands of sensors (California) rendered and forecast | LargeST models | P6, P7 |
| F8 | Zero-shot city: upload a CSV of any city's sensors, get a forecast without training | foundation models | P9 |
| F9 | Cross-city transfer page: model trained on LA applied to Dhaka corridor, gap reported | adapters | P11 |
| F10 | Train-your-own: pick model + dataset, launch on AWS, watch the log, auto-register the result | existing `/api/train` | exists, extended each phase |
| F11 | Evidence page: checkpoint hashes, logs, protocol check (HA floor vs paper), reproducibility command | `results/forecasting/` | exists |
| F12 | Digital-twin replay: forecast fed into SUMO, reroute effect in vehicle-hours | existing closed loop | exists |
| F13 | Assistant and Alexa: ask "will Mirpur Road be jammed at 6?" → answer from the same forecast API | Bedrock + MCP | exists, re-pointed |
| F14 | Regime-aware alerts: notify when onset probability crosses a threshold on a watched road | onset + conformal | P10 |

## Part B · The phases

Benchmarks: METR-LA (207 sensors, speed), PEMS-BAY (325, speed), PEMS04/08 (flow), LargeST-SD (716) and GLA (3,834).
Protocol: chronological 70/10/20, 12 input steps, horizons 15/30/60 min, observed entries only (validated against the
published historical-average floor, `results/forecasting/benchmark_floors.md`).

Already done and kept: GWNet, STID, STAEformer (METR-LA, PEMS-BAY), OpenCity exact zero-shot reproduction, Chronos-Bolt
negative result. These rows stay on the leaderboard.

### P1 · DCRNN — the protocol-defining model
- Paper: Li et al., *Diffusion Convolutional Recurrent Neural Network*, ICLR 2018, https://arxiv.org/abs/1707.01926
- Code: https://github.com/liyaguang/DCRNN (MIT) · run via BasicTS `baselines/DCRNN` (Apache-2.0)
- Implement: official config on METR-LA and PEMS-BAY; reproduce 2.77/3.15/3.60 MAE; add to leaderboard.
- Web feature: F3 leaderboard row; F2 forecast map gets a model selector.
- Compute: g4dn.xlarge ≈ 4 h per dataset.

### P2 · The onset scorecard — our evaluation on every model so far
- Papers: the regime-failure finding, *Do TSFM benchmarks hide regime-dependent failures?*, ICML 2026 workshop,
  https://arxiv.org/abs/2606.18367; metric definitions follow Li et al. 2018 masking.
- Code: ours (`core/ml/forecasting/evaluation`), extended; no upstream.
- Implement: congestion-regime MAE, onset detection rate, lead time, interval coverage at transitions for GWNet, STID,
  STAEformer, DCRNN, persistence, HA, Chronos.
- Web feature: F4 onset page.
- Compute: CPU.

### P3 · D2STGNN — decoupled diffusion and inherent signals
- Paper: Shao et al., VLDB 2022, https://arxiv.org/abs/2206.09112
- Code: https://github.com/GestaltCogTeam/D2STGNN (NONE) → run only through BasicTS `baselines/D2STGNN`.
- Implement: reproduce METR-LA / PEMS-BAY; onset row.
- Web feature: F3, F4 rows.

### P4 · MegaCRN — meta-graph memory for non-stationary traffic
- Paper: Jiang et al., AAAI 2023, https://arxiv.org/abs/2212.05989
- Code: https://github.com/deepkashiwa20/MegaCRN (MIT) · BasicTS baseline.
- Implement: reproduce; onset row (the paper claims robustness to incidents, which is exactly onset).
- Web feature: F3, F4.

### P5 · STD-MAE and HimNet — 2024 state of the art
- Papers: Gao et al., *Spatial-Temporal-Decoupled Masked Pre-training*, IJCAI 2024, https://arxiv.org/abs/2312.00516;
  Dong et al., *Heterogeneity-Informed Meta-Parameter Learning* (HimNet), KDD 2024, https://arxiv.org/abs/2405.10800
- Code: https://github.com/Jimmy-7664/STD-MAE (NONE), https://github.com/XDZhelheim/HimNet (NONE) → both via BasicTS.
- Implement: STD-MAE pre-train then fine-tune STID/STAEformer (the paper's recipe); HimNet on PEMS04/08.
- Web feature: F3, F4; F2 default model becomes the best of the table.
- Compute: g5.xlarge ≈ 6–8 h for pre-training.

### P6 · BigST on LargeST — thousands of sensors
- Papers: Han et al., *BigST*, VLDB 2024, https://dl.acm.org/doi/10.14778/3641204.3641217;
  Liu et al., *LargeST benchmark*, NeurIPS 2023, https://arxiv.org/abs/2306.08259
- Code: https://github.com/usail-hkust/BigST (NONE) → BasicTS large-scale configs; data from
  https://github.com/liuxu77/LargeST (code MIT, data CC BY-NC 4.0, research use only).
- Implement: LargeST-SD reproduction; then GLA if budget allows.
- Web feature: F7 large-scale map (MapLibre with 716 → 3,834 points, vector tiles).
- Compute: g5.2xlarge ≈ 10 h.

### P7 · PatchSTG and STGformer — 2025 large-scale state of the art
- Papers: Fang et al., *Efficient Large-Scale Traffic Forecasting with Transformers*, KDD 2025,
  https://arxiv.org/abs/2412.09972; Wang et al., *STGformer*, 2024, https://arxiv.org/abs/2410.00385
- Code: https://github.com/LMissher/PatchSTG (MIT, pretrained weights provided), https://github.com/Dreamzz5/STGformer (MIT)
- Implement: official test commands with their checkpoints first (no training), then one training run on SD.
- Web feature: F7 gets the current best model; F3 rows.

### P8 · Conformal uncertainty and departure advice — the method chapter
- Papers: MAPIE conformal prediction, https://github.com/scikit-learn-contrib/MAPIE (BSD-3);
  precedent *Reliable Train Delay Forecasting with Conformal Prediction*, 2025,
  https://link.springer.com/chapter/10.1007/978-3-032-15120-9_17; the bimodal-mixture idea from arXiv 2606.18367.
- Code: MAPIE (used as a package); our regime split.
- Implement: per-regime conformal intervals on every model in the table; coverage and sharpness at transitions;
  latest safe departure = the time whose p90 arrival still meets the deadline.
- Web feature: F5 uncertainty bands; F6 departure advice.
- Compute: CPU.

### P9 · Foundation models zero-shot — Chronos-2, TimesFM 2.5, Moirai, TimeMoE
- Papers: *Chronos-2*, https://arxiv.org/abs/2510.15821; *TimesFM*, ICML 2024, https://arxiv.org/abs/2310.10688;
  *Moirai*, ICML 2024, https://arxiv.org/abs/2402.02592; *Time-MoE*, ICLR 2025, https://arxiv.org/abs/2409.16040;
  benchmark reference *Time Series Foundation Models as Strong Baselines in Transportation*, 2026, https://arxiv.org/abs/2602.24238
- Code: https://github.com/amazon-science/chronos-forecasting (Apache-2.0), https://github.com/google-research/timesfm
  (Apache-2.0), https://github.com/SalesforceAIResearch/uni2ts (Apache-2.0), https://github.com/Time-MoE/Time-MoE (Apache-2.0);
  all four are BasicTS universal baselines too.
- Implement: zero-shot on METR-LA / PEMS-BAY under our protocol; reproduce the 2026 paper's Chronos-2 numbers; onset rows.
- Web feature: F8 zero-shot city upload.
- Compute: g4dn.xlarge inference only.

### P10 · Regime-aware alerts
- Paper basis: P2 + P8.
- Code: ours; SNS for delivery (exists).
- Implement: onset probability per watched road from the calibrated model; threshold with hysteresis; notification.
- Web feature: F14.

### P11 · Cross-city and the live corridor — UniST / OpenCity transfer to Dhaka
- Papers: *UniST*, KDD 2024, https://arxiv.org/abs/2402.11838; *OpenCity*, 2024, https://arxiv.org/abs/2408.10269;
  *UrbanGPT*, KDD 2024, https://arxiv.org/abs/2403.00813
- Code: https://github.com/tsinghua-fib-lab/UniST (NONE, external checkout only), https://github.com/HKUDS/OpenCity (MIT,
  already reproduced), https://github.com/HKUDS/UrbanGPT (Apache-2.0)
- Implement: best three supervised models + OpenCity + UniST on the recorded Dhaka corridor (5-minute bins); the honest
  cross-city gap; Google-Routes history never used for training.
- Web feature: F9 cross-city page; F2 live city uses the winner.

### P12 · Serving and the closed loop
- Code: ONNX Runtime export of the winner; existing SUMO closed loop (F12) re-run with the new forecaster.
- Web feature: F2/F6/F13 all read one `/api/forecast` backed by the served model; F12 updated vehicle-hours table.

## Part C · Supporting benchmarks and harnesses (pinned once, used throughout)

| Resource | Link | Licence | Use |
|---|---|---|---|
| BasicTS | https://github.com/GestaltCogTeam/BasicTS | Apache-2.0 | training/eval harness for P1, P3–P6, P9 |
| LibCity | https://github.com/LibCity/Bigscity-LibCity | Apache-2.0 | second harness to cross-check a reproduction when a BasicTS number disagrees with the paper |
| LargeST | https://github.com/liuxu77/LargeST | MIT / CC BY-NC 4.0 | large-scale data |
| METR-LA, PEMS-BAY | https://github.com/liyaguang/DCRNN | MIT | the canonical benchmarks |

## Part D · The thesis chapters this produces

1. Background and protocol (P1, floors).
2. Reproduction of twelve world-best models with official code (P1, P3–P7, P9).
3. The regime-transition problem: who sees congestion onset (P2 across all).
4. Calibrated uncertainty per regime and departure advice (P8).
5. Transfer to a live, sensor-poor city (P11).
6. The web system and the closed-loop twin (P12, F1–F14).

Next action: P1. Say "go".
