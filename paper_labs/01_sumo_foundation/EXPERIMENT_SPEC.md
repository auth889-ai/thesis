# Experiment Specification

## Experiment 1 — unit network construction

- Build network with `netconvert`.
- Validate input/network files.
- Confirm traffic-light id `C` and four controlled straight movements.
- Confirm phase sequence contains two green stages and yellow transitions.

## Experiment 2 — controller comparison

Default full configuration:

- seeds: 11, 22, 33, 44, 55
- demand duration: 1800 s
- clearance / drain period: 300 s
- simulation end: 2100 s
- step length: 1 s
- min green: 10 s
- max green: 45 s
- decision interval: 5 s

Controllers:
1. `fixed_time`
2. `actuated`
3. `max_pressure`

Metrics:
- average travel time
- p95 travel time
- average waiting time
- average time loss
- mean queue
- p95 queue
- max queue
- throughput
- mean waiting episodes / stops proxy
- spillback proxy fraction

Report per-seed results and aggregated mean/std. Never compare controllers using different route realizations.

## Experiment 3 — official Bologna/Acosta

1. clone `DLR-TS/sumo-scenarios`;
2. checkout pinned SHA;
3. record tree status;
4. run `sumo -c bologna/acosta/run.sumocfg` without modifying upstream;
5. capture SUMO version, command, exit code, stdout/stderr log, runtime and output manifest;
6. hash relevant upstream config/network/route files.

## PASS gate

Lab 01 is PASS only when all are true:

- learning gate completed;
- official references documented;
- official repos pinned;
- unit network validates;
- all three controllers execute for all required seeds;
- metrics are independently recalculated from raw outputs;
- controller safety invariants pass;
- unit/integration tests pass;
- official Bologna/Acosta runs unmodified;
- artifacts and manifests exist;
- limitations are documented;
- `REPRODUCTION_REPORT.md` is completed from actual evidence.
