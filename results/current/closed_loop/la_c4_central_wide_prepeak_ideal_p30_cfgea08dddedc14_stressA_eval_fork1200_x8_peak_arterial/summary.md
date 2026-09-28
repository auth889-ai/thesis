# Canonical Closed-Loop Experiment — la_c4_central_wide_prepeak_ideal_p30_cfgea08dddedc14_stressA_eval_fork1200_x8_peak_arterial

**Question:** Can predicted future traffic, communicated through a simulated V2X channel, improve routing compared with reactive traffic management?

- Arms: baseline, reactive, oracle_v2x, persistence_v2x, predictive_v2x, predictive_corrected_v2x, random_v2x
- Seeds: [201, 202, 203, 204, 205]
- Identical state fork: True
- Oracle-vs-reactive future-information gate: HELPED (-1.83 %, 95 % CI [-3.52, -0.14])
- Learned predictive-vs-reactive secondary result: HELPED (-0.68 %, 95 % CI [-1.21, -0.15])

All values above come from `report.json`; the selected vehicle's causal chain is in `vehicle_trace.json`.
