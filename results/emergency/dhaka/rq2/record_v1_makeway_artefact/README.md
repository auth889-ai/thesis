# Record: RQ2 and RQ2b with make-way rule v1 (kept, not used)

**Make-way rule v1, known circular-wait artefact; not used in any current claim.**

These are the RQ2 summary, figures, PAPER_MAP section and RQ2b slowdown inspection as they stood on 2026-10-09, before the
make-way rule was corrected (RQ2c). Under v1 every alerted vehicle up to 1,000 m ahead kept SUMO's bluelight settings,
including `lcStrategic -1`, until the ambulance passed it; a vehicle at a lane end could then never make its route's lane
change while the ambulance waited behind it (`SLOWDOWN.md`). The alerting runs themselves stay in `../runs/`; the current
results use `../runs_v2/` (make-way v2, `backend/app/emergency/configs/ambulance.yaml`).
