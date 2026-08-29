# Lab 01 — SUMO Foundation + TraCI + Official Bologna Scenario

**Primary source:** SUMO's current canonical reference publication, not an arbitrary paper.

## Two tracks in this lab

### Track A — controlled unit-validation intersection
A deterministic one-signal scenario used to prove that network, demand, signal phases, TraCI, queue measurement, safety transitions and baseline controllers work correctly.

Controllers:
- Fixed-Time
- Queue-actuated
- Max-Pressure

This is a **unit validation environment**, not the final thesis evidence.

### Track B — official real-world Bologna/Acosta scenario
The canonical SUMO paper uses a real-world Bologna scenario. The paper reports that its traffic demand was derived from real induction-loop counts from Bologna (11 and 13 November 2008) and that a representative 8–9am rush-hour demand was constructed. The maintained official scenario is fetched from the DLR-TS SUMO scenarios repository.

This track demonstrates that the project can run a real official scenario and collect reproducible outputs before Dhaka adaptation.

## Correct execution order

1. Install SUMO in Colab and record exact version.
2. Run official SUMO Hello/TraCI smoke checks.
3. Build deterministic unit intersection.
4. Validate network/routes with SUMO tools.
5. Run Fixed-Time.
6. Run queue-actuated.
7. Run Max-Pressure.
8. Compare same demand / same seed / same metrics.
9. Fetch and run official Bologna/Acosta scenario.
10. Generate Lab 01 report.

## Pass gates

- SUMO + netconvert + TraCI import work.
- Unit network validates.
- No invalid routes.
- Signal phase order + yellow/all-red transitions are documented.
- Fixed/Actuated/Max-Pressure run on identical deterministic demand.
- Queue, waiting, travel time, time loss and throughput are measured.
- Official Bologna/Acosta scenario runs from the official repository.
- SUMO version and upstream commit SHA are recorded.
