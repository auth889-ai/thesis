# METHOD_SPEC — Lab 01

## Official reproduction component

Running the maintained official Bologna/Acosta SUMO scenario is classified as **official scenario reproduction**. We record the upstream repository commit and SUMO version.

## DhakaFlow unit-validation component

The deterministic one-intersection scenario and its Fixed/Actuated/Max-Pressure controllers are **DhakaFlow validation code**, not part of the 2018 paper.

## Metrics

Same scenario/demand for all controllers:
- completed trips / throughput
- mean trip duration
- mean waiting time
- mean time loss
- p95 trip duration
- mean/max queue

## Safety

External controllers never jump directly between conflicting green states. They enforce yellow and all-red transitions and a minimum green.
