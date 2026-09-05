# R1 — forecast-to-action sensitivity (same net, demand, OD, seed, horizon)

## seed 11, pricing coverage 0 hops

| forecast | status | served / checkpoint | raw hash | classes → multipliers (6 corridors) | priced edges | cost hash | % edge costs ≠ persistence | % edge costs ≠ oracle | advised | cand./veh | candidate-set hash | selected hash | % routes ≠ persistence | Jaccard vs persistence | % routes ≠ oracle | Jaccard vs oracle | top-20 concentration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle | ok | — / — | (baseline edge travel times) | — | None | — | None | — | 2263 | 1.0 | d24b3007d5d51a31 | 14c78e5e82c0cdea | 43.08 | 0.816 | — | — | 0.1367 |
| GWNet | REFUSED: GWNet/METR-LA: GWNet was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for | | | | | | | | | | | | | | | | |
| STID | REFUSED: STID/METR-LA: STID was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for | | | | | | | | | | | | | | | | |
| Chronos-Bolt | ok | Chronos-Bolt / amazon/chronos-bolt-small | 124feb1c4ec51d6e | 2.395, 2.814, 1.967, 2.57, 1.906, 2.335 → 2.046, 2.361, 1.736, 2.177, 1.711, 2.001 | 79 | 0df0f03d5516513f | 100.0 | None | 2263 | 1.0 | 7bcc798d065c7562 | 2439d0a336c819ba | 18.82 | 0.8835 | 39.59 | 0.8048 | 0.1409 |
| persistence | ok | persistence / — | 20f58b79f737d01d | 3.0, 3.0, 2.0, 3.0, 2.0, 3.0 → 2.5, 2.5, 1.75, 2.5, 1.75, 2.5 | 79 | b5a9785cd8cc8a57 | — | None | 2263 | 1.0 | e673b46b29924661 | 657496045744bc8c | — | — | 43.08 | 0.816 | 0.1462 |
| historical_average | ok | historical_average / — | 7c87b1b1f9c30501 | 0.581, 0.63, 0.663, 0.499, 0.506, 0.653 → 1.225, 1.238, 1.246, 1.205, 1.207, 1.243 | 79 | f833b8a1136f978b | 100.0 | None | 2263 | 1.0 | 837ad8285a2e2826 | 5ac8f462bf050c8d | 18.87 | 0.8833 | 39.55 | 0.8051 | 0.1407 |
| random | ok | random / — | 787226417a9ae312 | 1.804, 2.785, 0.086, 0.386, 1.498, 0.444 → 1.668, 2.339, 1.102, 1.177, 1.539, 1.191 | 79 | 8ac2fdc0ee825bac | 100.0 | None | 2263 | 1.0 | 7bcc798d065c7562 | 2439d0a336c819ba | 18.82 | 0.8835 | 39.59 | 0.8048 | 0.1409 |

Collapse by stage (distinct hashes among the forecasts that ran; identical groups listed):
- raw_forecast: 4 distinct
- mapped_classes: 4 distinct
- mapped_multipliers: 4 distinct
- edge_costs: 4 distinct
- candidate_sets: 3 distinct — identical: [['Chronos-Bolt', 'random']]
- candidate_costs: 4 distinct
- selected_routes: 3 distinct — identical: [['Chronos-Bolt', 'random']]

**First collapse stage: candidate_sets.**

Uniform-class sweep (every corridor at the same level): where the selected routes move
| level | multiplier | selected hash | % routes ≠ level 0 |
|---|---|---|---|
| 0.0 | 1.08 | 35c87bcb5d71d0eb | 0.0 |
| 0.5 | 1.205 | 5ac8f462bf050c8d | 0.53 |
| 1.0 | 1.33 | 82faaf61f8948df9 | 0.49 |
| 1.5 | 1.54 | 82faaf61f8948df9 | 0.49 |
| 2.0 | 1.75 | 2439d0a336c819ba | 0.57 |
| 2.5 | 2.125 | 2439d0a336c819ba | 0.57 |
| 3.0 | 2.5 | 657496045744bc8c | 19.4 |

## seed 11, pricing coverage 8 hops

| forecast | status | served / checkpoint | raw hash | classes → multipliers (6 corridors) | priced edges | cost hash | % edge costs ≠ persistence | % edge costs ≠ oracle | advised | cand./veh | candidate-set hash | selected hash | % routes ≠ persistence | Jaccard vs persistence | % routes ≠ oracle | Jaccard vs oracle | top-20 concentration |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle | ok | — / — | (baseline edge travel times) | — | None | — | None | — | 2263 | 1.0 | d24b3007d5d51a31 | 14c78e5e82c0cdea | 71.37 | 0.5989 | — | — | 0.1367 |
| GWNet | REFUSED: GWNet/METR-LA: GWNet was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for | | | | | | | | | | | | | | | | |
| STID | REFUSED: STID/METR-LA: STID was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for | | | | | | | | | | | | | | | | |
| Chronos-Bolt | ok | Chronos-Bolt / amazon/chronos-bolt-small | 124feb1c4ec51d6e | 2.395, 2.814, 1.967, 2.57, 1.906, 2.335 → 2.046, 2.361, 1.736, 2.177, 1.711, 2.001 | 1324 | 49d6b30b26a71ca0 | 100.0 | None | 2263 | 1.0 | 48de41bf6b986899 | a1f63a698385d930 | 17.63 | 0.8675 | 58.64 | 0.715 | 0.1436 |
| persistence | ok | persistence / — | 20f58b79f737d01d | 3.0, 3.0, 2.0, 3.0, 2.0, 3.0 → 2.5, 2.5, 1.75, 2.5, 1.75, 2.5 | 1324 | 478cd3faf69f4b84 | — | None | 2263 | 1.0 | ebb235c32be1040f | 2ad583cca9c99b6f | — | — | 71.37 | 0.5989 | 0.1169 |
| historical_average | ok | historical_average / — | 7c87b1b1f9c30501 | 0.581, 0.63, 0.663, 0.499, 0.506, 0.653 → 1.225, 1.238, 1.246, 1.205, 1.207, 1.243 | 1324 | 55021e1cd6359351 | 100.0 | None | 2263 | 1.0 | 3135c779d1fed0e7 | 6924beca88af3364 | 36.15 | 0.8236 | 53.65 | 0.7151 | 0.1201 |
| random | ok | random / — | 787226417a9ae312 | 1.804, 2.785, 0.086, 0.386, 1.498, 0.444 → 1.668, 2.339, 1.102, 1.177, 1.539, 1.191 | 1324 | 52aab1fe8ded2a74 | 100.0 | None | 2263 | 1.0 | d064e791d4294a5e | 33fdb42ee74a2c4a | 30.49 | 0.8124 | 51.44 | 0.7487 | 0.1382 |

Collapse by stage (distinct hashes among the forecasts that ran; identical groups listed):
- raw_forecast: 4 distinct
- mapped_classes: 4 distinct
- mapped_multipliers: 4 distinct
- edge_costs: 4 distinct
- candidate_sets: 4 distinct
- candidate_costs: 4 distinct
- selected_routes: 4 distinct

**First collapse stage: none — every stage stays distinct.**

Uniform-class sweep (every corridor at the same level): where the selected routes move
| level | multiplier | selected hash | % routes ≠ level 0 |
|---|---|---|---|
| 0.0 | 1.08 | cc86d6fdf37fe3b0 | 0.0 |
| 0.5 | 1.205 | 9db6b72e049dc0b3 | 0.18 |
| 1.0 | 1.33 | a37e5aab2c60d03e | 12.46 |
| 1.5 | 1.54 | 3ededfad0c8c4671 | 24.13 |
| 2.0 | 1.75 | 9cdf5046f4eee274 | 24.04 |
| 2.5 | 2.125 | 2721e15b1b955bd6 | 31.33 |
| 3.0 | 2.5 | 2ad583cca9c99b6f | 41.94 |
