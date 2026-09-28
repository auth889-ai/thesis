# Detector-based flow calibration — availability check (2026-09-09)

The METR-LA release used by this project (`data/forecasting/cities/METR-LA/metr-la.h5`, 34,272 × 207) is a
**speed-only** table (one block of mph values, no flow / occupancy columns). Vehicle counts per detector
are therefore NOT available, so the SUMO demand cannot be calibrated to observed flows (routeSampler /
flowrouter need counts).

Consequence: every demand used in `results/v2x/stress/` is **SYNTHETIC_WHAT_IF** — randomTrips on the real
OSM network, scaled by a multiplier chosen with the frozen rule in `pipeline/v2x/stress_sweep.py`. The
observed METR-LA speeds are used only as the forecasting input (held-out weekday at the chosen moment) and
as lane-speed caps on the mapped detector edges. No number derived from these runs describes real Los
Angeles traffic volumes, and none is labelled as such.

If a count-bearing release (PeMS flow/occupancy for the same 207 stations) is added under a research
licence, `stress_sweep.py` should be replaced by routeSampler calibration against those counts; the OD rule
and the selection rule stay the same.
