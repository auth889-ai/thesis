# METHOD_SPEC — Lab 00

## Classification

**Independent paper-faithful reconstruction; not authors' official analysis code.**

## PUBLISHED

- Detector measurements are typically about 300 s intervals.
- Primary observed fields: detector flow `q_i(t)` and occupancy `o_i(t)`; some cities have speed.
- Roads considered in paper: OSM trunk, primary, secondary, tertiary.
- 2019 paper uses a re-sampling method with **300 draws at 80% sample size**.
- Upper boundary is determined using high flow quantiles, reported as 95th–97.5th percentile by density bins.
- Critical point is the maximum of a nonlinear MFD fit to the upper boundary.
- Paper uses a two-step speed/occupancy calibration; the second step used historical Google Directions queries.
- Paper scales detector-level average flow/density to production/accumulation using network length.

## INFERRED / implementation choice

- `softmin_trapezoid` is implemented as a physically interpretable functional form consistent with the cited Ambühl functional-form paper. Before an exact-paper claim, Claude must cross-check the exact equation/parameterization against the accessible full paper.
- Both q95 and q97.5 fits are retained as sensitivity outputs rather than silently picking one.

## UNKNOWN / requires verification

- Exact mapping from every current released detector to the paper's 107 hand-defined regional networks.
- Exact historical Google Directions calibration inputs from 2019.
- Any city-specific manual cleaning not encoded in released metadata.

## Guardrail

If the exact region metadata or calibration inputs are unavailable, outputs must be labelled `RECONSTRUCTION`, not `EXACT_REPRODUCTION`.
