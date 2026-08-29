# Results Matrix (auto-generated — rerun scripts/build_results_matrix.py)

| Gate | Method | Result | Protocol | Domain |
|---|---|---|---|---|
| Perception | RT-DETR r50 (official, fine-tuned) | mAP50:95 0.711 | BNVD paper best 0.643 | REAL Poribohon-BD test set |
| Forecasting | Graph WaveNet (official) | MAE 0.44 m/s @15 min | persistence floor 1.39 | SIMULATED twin graph |
| Forecasting | DCRNN / STID | 0.53 / 1.09 @15 min | same floor | SIMULATED |
| Routing | System-optimal vs selfish (SUMO twin) | −19.5% delay (p=1e-05, d=2.98) | 10 seeds/arm | SIMULATED twin, real network |
| Signal control | fixed_time | 535.9 s mean time-loss | 3 seeds, fair FIXED demand (calibration wiring pending) | SIMULATED |
| Signal control | max_pressure | 586.7 s mean time-loss | 3 seeds, fair FIXED demand (calibration wiring pending) | SIMULATED |
| Signal control (learned) | mappo | 558.9 s (-4.3% vs paired fixed-time) | PAIRED held-out seeds 11-13 | SIMULATED |
| Signal control (learned) | mappo_forecast | PENDING/training | — | — |
| Signal control (learned) | mappo_pressure | 551.3 s (-2.9% vs paired fixed-time) | PAIRED held-out seeds 11-13 | SIMULATED |
| Signal control (learned) | mappo_fp | PENDING/training | — | — |
| Signal control (learned) | mappo_full | PENDING/training | — | — |
| PREVENT mode | persistence-trigger rerouting | +1.2% (finding: gated by forecast quality) | 3 seeds | SIMULATED |
| Domain shift | Dhaka detector on US cameras | conf 0.60 vs home 0.711 mAP; 44 Dhaka-class FPs/60 frames | measured, not hidden | REAL foreign domain |
| Twin calibration A | live-reference speed matching | scale 0.584 | 3 captures | REAL live reference |

## Gate stack (video -> decision, rebuilt on published architectures)

| Gate | Verdict | Headline | Evidence |
|---|---|---|---|
| REAL_STATE_PASS | **PASS** | stationary-start video CONGESTED from t=0; official ByteTrack; honest LOCATION_REQUIRED | artifacts/gates/REAL_STATE_PASS.json |
| TWIN_SYNC_PASS | **PASS** | observed queue+flow construct the twin; GEH=0.0; calibration 0.584 consumed | artifacts/gates/TWIN_SYNC_PASS.json |
| FORECAST_PASS | **PASS** | GWNet history preloaded; availability 100%; official pipeline evidence | artifacts/gates/FORECAST_PASS.json |
| COUNTERFACTUAL_PASS | **PASS** | same saved state incl. RNG; A0==A0 determinism proven | artifacts/gates/COUNTERFACTUAL_PASS.json |
| NETWORK_GUARD_PASS | **PASS** | local-only wins labeled LOCAL_RELIEF_NETWORK_FAIL; old 32->8 claim retracted | artifacts/gates/NETWORK_GUARD_PASS.json |
| SIGNAL_CONTROL_PASS | **PASS** | fixed/actuated/Varaiya-MP, correct semantics, 3 seeds; actuated best at saturation | artifacts/gates/SIGNAL_CONTROL_PASS.json |
| DYNAMIC_ROUTING_PASS | **PASS** | official device + measured costs; ladder 0-40%; p10 accepted; no x5 penalties | artifacts/gates/DYNAMIC_ROUTING_PASS.json |
| PREDICTIVE_PLANNER_PASS | **PASS** | onset: A2 max-pressure -4.1% network delay 3/3 seeds; saturation: NO SAFE INTERVENTION | artifacts/gates/PREDICTIVE_PLANNER_PASS.json |

Research grounding: docs/RESEARCH_ARCHITECTURE_REVIEW.md · defect ledger: docs/CURRENT_SYSTEM_GAP_AUDIT.md

RL research arms (Gate 9): mappo + mappo_pressure trained (cloud, DONE markers); FA arms (forecast/fp/full) FAILED AT STARTUP on the VMs (missing dataset path) and are reported as NOT COMPLETED — no FA-MAPPO claim is made. Known env defects (hold no-op, seed off-by-one) documented in the gap audit; fixes are future work.
