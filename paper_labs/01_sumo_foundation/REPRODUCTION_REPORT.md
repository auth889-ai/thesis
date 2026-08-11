# Reproduction Report — TEMPLATE UNTIL EXECUTED

**STATUS: NOT YET EXECUTED**

This file must be completed by Claude after actual Colab/SUMO execution. Do not convert this template to PASS based on code inspection.

## Environment
- Date:
- OS / Colab runtime:
- SUMO version:
- SUMO source SHA:
- `sumo-scenarios` SHA:
- Python version:

## Unit network
- netconvert command:
- validation result:
- TLS id/phases verified:

## Controller matrix

| controller | seeds complete | avg travel | p95 travel | avg wait | mean queue | p95 queue | throughput | spillback proxy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_time | | | | | | | | |
| actuated | | | | | | | | |
| max_pressure | | | | | | | | |

## Safety verification
- yellow preserved:
- invalid phase jumps:
- min-green violations:
- max-green violations:

## Bologna/Acosta unmodified run
- command:
- upstream clean before run:
- exit code:
- runtime:
- logs/artifacts:

## Independent metric check
Document at least one hand/independent recomputation from `tripinfo.xml` and one queue metric recomputation from `step_metrics.csv`.

## Limitations

## Final decision
`LAB 01 STATUS: PASS / PARTIAL / FAIL`
