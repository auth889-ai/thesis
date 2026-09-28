# Frozen Scenario A: Coverage Diagnostic

All ten new SUMO interventions and all 60 same-state audit rounds completed.

The existing frozen FULL ORACLE, GWNet, Persistence, Reactive and Baseline outcomes are explicitly reused, not claimed as new simulations. Variants A and C are the same current DIRECT+DERIVED implementation; B and D are the ten new runs.

Accuracy and opportunity summaries use 55 rounds with future Oracle observations. The five simulation-end ticks remain logged but are not accuracy evidence.

## Network Coverage

| Quantity | Min | Mean | Max |
|---|---:|---:|---:|
| routable_edges | 15661.000 | 15661.000 | 15661.000 |
| oracle_priced | 0.000 | 4218.317 | 5424.000 |
| gwnet_direct | 73.000 | 73.983 | 74.000 |
| gwnet_derived | 131.000 | 133.950 | 134.000 |
| unpriced | 15453.000 | 15453.067 | 15457.000 |
| network_priced_pct | 1.303 | 1.328 | 1.328 |
| bottleneck_edges | 0.000 | 2408.083 | 3137.000 |
| bottlenecks_priced | 0.000 | 58.867 | 99.000 |
| bottleneck_priced_pct | 1.057 | 2.608 | 4.925 |

Oracle-priced edges during active future windows range from 2210 to 5424. Pooled bottleneck coverage is 2.44%. Zero Oracle coverage occurs at the simulation-end tick.

## Route Coverage

| Paths | Priced edge occurrences (%) | Fully priced (%) | Partially priced (%) | Zero coverage (%) |
|---|---:|---:|---:|---:|
| all_candidate_paths | 5.91 | 0.23 | 60.92 | 38.85 |
| gwnet_selected_paths | 5.97 | 0.48 | 60.37 | 39.15 |
| oracle_beneficial_paths | 5.02 | 0.00 | 68.14 | 31.86 |

## Traffic Outcomes

| Comparison | Vehicle-hours change (%) | Paired 95% CI | W/L/T |
|---|---:|---|---|
| oracle_v2x_vs_reactive | -1.83 | [-3.52, -0.14] | 5/0/0 |
| oracle_coverage_limited_v2x_vs_reactive | -0.74 | [-1.83, 0.36] | 4/1/0 |
| predictive_v2x_vs_reactive | -0.68 | [-1.21, -0.15] | 5/0/0 |
| persistence_v2x_vs_reactive | -0.69 | [-1.98, 0.59] | 4/1/0 |
| gwnet_direct_v2x_vs_predictive_v2x | 0.21 | [-0.51, 0.93] | 2/3/0 |
| oracle_coverage_limited_v2x_vs_oracle_v2x | 1.12 | [0.06, 2.19] | 1/4/0 |
| oracle_coverage_limited_v2x_vs_predictive_v2x | -0.06 | [-0.86, 0.74] | 3/2/0 |

## Gap Contrast

Coverage contrast: 94.43% of the aggregate GWNet-to-Oracle gap; forecast-value contrast: 5.57%.
These contrasts include downstream changes in candidates, admission and V2X. They cannot be added to separate mechanism percentages. Negative contributions are retained.

## Same-State Ranking

| Source | Oracle top-route agreement (%) | Pairwise accuracy (%) | False positive reroutes | False negative reroutes |
|---|---:|---:|---:|---:|
| gwnet | 14.45 | 30.10 | 2527 | 4943 |
| persistence | 14.63 | 30.42 | 2611 | 4951 |

Candidate-path identity is strict. Of 5226 Oracle-admitted shadow opportunities, 1 exact Oracle paths exist in GWNet's set, but 2533 have some Oracle-cheaper candidate in that set. Missing the exact Oracle path does not prove that no useful alternative was generated.

## Matched Routing-Relevant Edge Errors

Both sources use the same GWNet coverage labels and oracle-observed candidate edges. UNPRICED is fallback error, not DL forecast error. Edge errors use frozen 15-minute cost tables; route costs use each source's frozen horizon handling. Oracle truth is a baseline future-window estimate, not observed counterfactual route travel time.

| Source | GWNet coverage class | Edge-round observations | MAE (s) | RMSE (s) | Signed bias (s) |
|---|---|---:|---:|---:|---:|
| gwnet | DERIVED | 6601 | 7.265 | 121.542 | -2.629 |
| gwnet | DIRECT | 3500 | 11.056 | 38.542 | -6.882 |
| gwnet | UNPRICED | 207530 | 16.565 | 430.093 | -16.565 |
| persistence | DERIVED | 6601 | 7.510 | 121.729 | -2.435 |
| persistence | DIRECT | 3500 | 8.974 | 26.548 | -4.815 |
| persistence | UNPRICED | 207530 | 16.565 | 430.093 | -16.565 |

## Missed Oracle Reroutes: Primary Classification

Population: 4943 cases where Oracle admits a reroute and GWNet does not. All 5226 Oracle-admitted opportunities, including different GWNet reroutes, are separately classified in report.json.

| Primary blocker | Count | Percent |
|---|---:|---:|
| A_FORECAST_ERROR | 0 | 0.00 |
| B_COVERAGE_MISSING | 1 | 0.02 |
| C_DERIVATION_ERROR | 0 | 0.00 |
| D_CANDIDATE_MISSING | 4942 | 99.98 |
| E_OPTIMIZER_REJECTION | 0 | 0.00 |
| F_V2X_FAILURE | 0 | 0.00 |
| G_NO_ACTION_DIFFERENCE | 0 | 0.00 |

## Actual Reference V2X Outcomes

| Source | Delivered | Applied | Past fork | Vehicle gone |
|---|---:|---:|---:|---:|
| oracle_v2x | 4974 | 1422 | 3545 | 7 |
| predictive_v2x | 1673 | 1031 | 613 | 29 |
| persistence_v2x | 1737 | 1088 | 624 | 25 |

baseline snapshot shadow recommendations after admission/budget, no delivery simulated; F=0 means not evaluated in this population, not absence of real V2X failures. Ordered first-blocker labels are not exclusive root causes: D can hide simultaneous coverage, ranking and control failures; A=0 does not mean forecasts are correct.

## Computed Gates

| Gate | Status |
|---|---|
| FORECAST_VALIDATED | PASSED |
| FUTURE_INFORMATION_VALUE | ESTABLISHED |
| PREDICTIVE_CONTROL_VS_REACTIVE | ESTABLISHED |
| LEARNED_FORECAST_ADVANTAGE_VS_PERSISTENCE | NOT_ESTABLISHED |
| DHAKA_DEPLOYMENT_READY | NOT_READY |

## Identifiability Limits

- individual actual future savings on untaken routes are not observed
- separate additive candidate/admission/V2X vehicle-hour shares require additional interventions
- post-hoc diagnostics on existing evaluation seeds are not new independent confirmation
- source-specific DIRECT/DERIVED validity masks differ slightly; matched_population_scoring fixes labels to GWNet and missing source values use explicit free-flow fallback
- coverage-limited Oracle retains GWNet values where the baseline future window has no measurement; it is not perfect ground truth on every covered edge
- shadow replay compares recommendations on baseline states, not causal attribution of missed actions along divergent historical trajectories

Oracle observations replace 10687 of 11440 covered edge-round costs (93.42%) during active future windows. The remainder retains the original learned value. Thus the coverage-limited arm is an observed-Oracle substitution, not a perfect-information bound on all covered edges.

## Scientific Verdict

Coverage is the leading measured constraint in these diagnostic interventions.

The full Oracle reduces vehicle-hours by 1.83% versus Reactive. Persistence recovers 38.38% of aggregate Oracle headroom; GWNet recovers 37.02%; coverage-limited Oracle recovers 40.53%.

With the current coverage mask, 59.47% of the full Oracle advantage remains unrecovered by this intervention. This is a descriptive point estimate, not a confidence bound or theoretical ceiling.

- No significant difference is not evidence of equivalence or proof GWNet already uses available information optimally.
- Native METR-LA forecast validation does not establish calibrated SUMO edge-cost prediction: DIRECT routing-relevant error can be worse than persistence.
- Large real applicability losses remain even with ideal radio transport; these experiments do not separately identify their vehicle-hour effect.

## Next Intervention: Proposal Only

On development seeds and a separate held-out mapping set, evaluate road-class/direction-aware compatible-detector mapping for the uncovered edges occurring on Oracle-beneficial alternatives. Use a shared fixed candidate pool for the mapping/value diagnostic, report DIRECT and proxy calibration against observed SUMO edge costs, and require validation before routing eligibility. Keep the current checkpoint unchanged. Do not fit or choose the mapping on seeds 201-205.

## Reproduction

```sh
python experiments/routing/coverage_diagnostic.py --analyze
```

Completed outputs are reused only after frozen protocol/state checks. The five-seed source reference must be present.

Full edge-error breakdowns, individual decisions, per-round coverage, raw outcomes and computed gates are in report.json and audit/s*/round_*/vehicle_decisions.jsonl.gz.

No new forecasting model, mapping expansion or evaluation-seed tuning was performed.
