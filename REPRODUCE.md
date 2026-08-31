# REPRODUCE — every headline number, one command each

(Pattern per the Geneva Motorway twin repository: this file + pinned upstreams
is everything needed to regenerate the results.)

| Claim | Command | Evidence file |
|---|---|---|
| pNEUMA d8 real data (2,110 vehicles, sha `93bfbae8…`) | official endpoint POST (see `notebooks/DhakaFlow_Urban_Pipeline.ipynb` cell 2) | `artifacts/urban_real_site/real_trajectory_state.json` |
| 368/401 vehicles map-matched, 21 signals, 3 alt paths | `python scripts/gate_urban_site.py` | same file + `real_trajectories.png` |
| Published calibration on our junction: J 6.0→2.37, nABC 16.2→11.8% | stage tree `python scripts/build_d8_cycles.py`, then authors' `optimization_process_nevergrad.py` (repo @9e25290, unmodified) | `artifacts/gates/d8_calibration/STEP1_RECORD.json` |
| Authors'-example reproduction (J→17.7, arithmetic exact) | same optimizer in the reproduction workspace | `artifacts/gates/pneuma_calibration/REPRODUCTION_RECORD.json` |
| Held-out twin validation: speed MAE 3.0 m/s, 0 teleports | `python scripts/gate_pneuma_twin.py` | `artifacts/urban_real_site/STEP2_RECORD.json` |
| Dhaka onset finding: −4.1% network delay, 3/3 paired seeds | `python scripts/predictive_planner.py --routes artifacts/gates/routes_repeat_1h.rou.xml.gz --scale 0.584 --seeds 11,12,13` | `artifacts/gates/PREDICTIVE_PLANNER_PASS.json` |
| Networked actuation: 100% ACK, improves all seeds | `python scripts/gate_networked_actuation.py` | `artifacts/gates/NETWORKED_ACTUATION_PASS.json` |
| MOSAIC V2X on the Dhaka net (585→2,593→886) | `mosaic.sh -s dhaka_r1` (pinned MOSAIC 25.2) | `artifacts/gates/MOSAIC_DHAKA_V2X.json` |
| I-70 same-site partial validation + honest NO_SAFE_ACTION | `python scripts/site_twin.py …` / `gate_motorway_control.py` | `artifacts/gates/REAL_SITE_TWIN_PASS.json`, `MOTORWAY_CONTROL.json` |

Upstream pins: `upstream/UPSTREAM_PINS.yaml`. Honest FAILs and deviations are
inside each record — they are part of the result, not noise.
