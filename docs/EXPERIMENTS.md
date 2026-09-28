# Experiments

## Canonical Command

```bash
make canonical
```

This executes `research/closed_loop/canonical.py --execute --stage oracle`, which invokes Scenario A with the valid frozen stress setting. It runs BASELINE, REACTIVE, and ORACLE from an identical state before any learned arm is admissible.

## Outputs

The wrapper promotes a completed run to `results/current/closed_loop/<run>/`:

- `report.json`: paired experiment result from the closed-loop logs.
- `summary.md`: log-derived scientific summary.
- `plots/paired_vehicle_hours.png`: paired outcome plot when matplotlib is available.
- `vehicle_trace.json`: one applied end-to-end causal trace.
- `provenance.json`: hashes and source paths.

`make canonical-package` packages the selected frozen run without executing SUMO.
