# R2 — route-decision sensitivity (seed 11, horizon 1800 s, forecast +15 min, compliance 0.3, 2655 equipped vehicles, as-of peak)

Production cost builder (`pipeline/routing/edge_costs.py`) and optimizer (`pipeline/routing/route_optimizer.py`); config hash `ea08dddedc14`.

| arm | hops | priced edges (direct+derived) | raw forecast hash | edge-cost hash | % costs ≠ persistence | mean |Δcost| % | cand/veh | admitted | % best path ≠ pers. | % decisions ≠ pers. | Jaccard vs pers. | % decisions ≠ oracle | Jaccard vs oracle | top-route share | top-edge conc. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| oracle | all (measured) | 902 (902+0) | `(measured ` | `cbfaff9a76` | 100.0 | 53.4 | 2.934 | 1024/2655 | 53.67 | 27.95 | 0.8542 | — | — | 0.0618 | 0.7324 |
| Chronos-Bolt | 0 | 79 (79+0) | `124feb1c4e` | `05151d12c7` | 100.0 | 13.7 | 2.583 | 608/2655 | 20.6 | 3.92 | 0.9668 | 31.79 | 0.8211 | 0.0588 | 0.8849 |
| persistence | 0 | 79 (79+0) | `20f58b79f7` | `0fd55d2360` | — | — | 2.629 | 571/2655 | — | — | — | 27.95 | 0.8542 | 0.0414 | 0.8774 |
| historical_average | 0 | 79 (79+0) | `7c87b1b1f9` | `88f9d119d8` | 100.0 | 50.47 | 2.45 | 458/2655 | 20.6 | 9.53 | 0.9211 | 33.11 | 0.7852 | 0.0588 | 0.8472 |
| random | 0 | 79 (79+0) | `787226417a` | `0376bfda0e` | 100.0 | 26.74 | 2.511 | 608/2655 | 20.6 | 3.92 | 0.9668 | 31.79 | 0.8211 | 0.0588 | 0.8849 |
| Chronos-Bolt | 1 | 182 (79+103) | `124feb1c4e` | `c146bcfaa5` | 100.0 | 12.03 | 2.453 | 655/2655 | 0.0 | 2.0 | 0.9876 | 34.73 | 0.8226 | 0.0618 | 0.8931 |
| persistence | 1 | 182 (79+103) | `20f58b79f7` | `8f8e35b572` | — | — | 2.407 | 708/2655 | — | — | — | 32.81 | 0.8347 | 0.0621 | 0.9011 |
| historical_average | 1 | 182 (79+103) | `7c87b1b1f9` | `9989150b0b` | 100.0 | 44.58 | 2.498 | 458/2655 | 26.89 | 12.35 | 0.9266 | 34.95 | 0.7826 | 0.0588 | 0.8472 |
| random | 1 | 182 (79+103) | `787226417a` | `90568d5643` | 100.0 | 23.93 | 2.53 | 608/2655 | 6.97 | 3.77 | 0.9759 | 34.73 | 0.8144 | 0.0588 | 0.8849 |
| Chronos-Bolt | 2 | 297 (79+218) | `124feb1c4e` | `e5589ebf07` | 99.66 | 10.35 | 2.492 | 691/2655 | 0.0 | 3.99 | 0.9856 | 34.43 | 0.832 | 0.0603 | 0.8987 |
| persistence | 2 | 297 (79+218) | `20f58b79f7` | `f202cfae4a` | — | — | 2.445 | 746/2655 | — | — | — | 32.58 | 0.8427 | 0.064 | 0.9062 |
| historical_average | 2 | 297 (79+218) | `7c87b1b1f9` | `2538d68662` | 100.0 | 38.58 | 2.472 | 458/2655 | 33.52 | 14.58 | 0.9144 | 34.95 | 0.7826 | 0.0588 | 0.8472 |
| random | 2 | 297 (79+218) | `787226417a` | `a769f962ad` | 99.66 | 20.72 | 2.568 | 608/2655 | 13.86 | 8.51 | 0.9611 | 34.73 | 0.8155 | 0.0588 | 0.8849 |

## Refused arms

- **STID**: REFUSED: STID/METR-LA: STID was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for
- **GWNet**: REFUSED: GWNet/METR-LA: GWNet was trained on METR-LA and its weights encode that sensor graph; it cannot forecast dhaka. A city-specific model does not transfer — that is what a foundation model is for

## Collapse point per coverage

- **0-hop**: first stage where two forecast arms become identical: **selected_routes**; raw_forecast: 4/4 distinct; edge_costs: 4/4 distinct; candidate_sets: 4/4 distinct; candidate_costs: 4/4 distinct; selected_routes: 3/4 distinct (identical: [['Chronos-Bolt', 'random']]); Chronos vs random: costs identical=False, selected identical=True, 0.0 % decisions differ, 0.0 % best paths differ
- **1-hop**: first stage where two forecast arms become identical: **none (all arms distinct through selection)**; raw_forecast: 4/4 distinct; edge_costs: 4/4 distinct; candidate_sets: 4/4 distinct; candidate_costs: 4/4 distinct; selected_routes: 4/4 distinct; Chronos vs random: costs identical=False, selected identical=False, 1.77 % decisions differ, 6.97 % best paths differ
- **2-hop**: first stage where two forecast arms become identical: **none (all arms distinct through selection)**; raw_forecast: 4/4 distinct; edge_costs: 4/4 distinct; candidate_sets: 4/4 distinct; candidate_costs: 4/4 distinct; selected_routes: 4/4 distinct; Chronos vs random: costs identical=False, selected identical=False, 4.97 % decisions differ, 13.86 % best paths differ
