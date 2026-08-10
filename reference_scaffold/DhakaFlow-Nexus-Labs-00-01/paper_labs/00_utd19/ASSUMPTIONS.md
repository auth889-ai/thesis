# ASSUMPTIONS — Lab 00

## PUBLISHED

- 2019 method: 300 resampling draws, 80% detector sample size.
- Upper-bound high quantiles: 95th–97.5th percentile in density bins.
- Critical point from maximum of fitted nonlinear MFD function.

## INFERRED

- A fixed pseudo-random seed is used to make the paper-required statistical resampling reproducible. This does not remove the resampling method; it makes reruns deterministic.

## ASSUMED

- None of the current released dataset's error flag semantics are assumed. The pipeline audits distinct values first and can stop until semantics are confirmed.

## MODIFIED_BY_US

- Full public-release city audit is broader than the minimum required to reproduce one regional MFD and is included to make the project research-grade.
- Raw city-level MFD plots are teaching/sanity artifacts only and are labelled as such.

## UNREPRODUCIBLE FROM AVAILABLE HISTORICAL INPUTS

- Exact 2019 Google Directions calibration unless the original query outputs are obtained.
