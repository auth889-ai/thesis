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
