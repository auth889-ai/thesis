# DATA_SPEC — Lab 00

## Official source

UTD19 portal: https://utd19.ethz.ch/

The public portal currently describes 40 cities, 23,541 detectors, around 170 million rows, and typical 3–5 minute aggregation.

## Expected measurement schema

Prior verified runs and UTD19 documentation indicate fields such as:

- `day`
- `interval`
- `detid`
- `flow`
- `occ`
- `error`
- `city`
- `speed`

**The code does not trust this blindly.** It reads the actual headers and resolves aliases. Unknown required fields cause a clear error.

## Full-release audit outputs

- city row counts
- detector counts
- time coverage
- flow/occupancy/speed availability
- negative-flow counts
- occupancy scale diagnostics
- error-flag value distribution
- duplicates by `(detid, day, interval)`
- detector metadata coverage

## Data policy

Full raw dataset lives in Drive. Only audit summaries, small figures, manifests and code are version-controlled.
