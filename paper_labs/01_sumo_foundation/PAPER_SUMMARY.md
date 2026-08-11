# Paper Summary

## Core SUMO reference

**Pablo Alvarez Lopez et al. (2018), “Microscopic Traffic Simulation using SUMO,” 21st IEEE ITSC, pp. 2575–2582.**

- DOI: `10.1109/ITSC.2018.8569938`
- Official DLR record: https://elib.dlr.de/127994/
- Public PDF from DLR: https://elib.dlr.de/127994/1/08569938.pdf

### Relevance
The paper describes SUMO's microscopic simulation workflow: network data + traffic infrastructure + demand form a scenario; stochastic scenarios should be simulated repeatedly; outputs support quantitative evaluation; and the real-world Bologna scenario is used as an example.

## Bologna scenario reference

**Laura Bieker et al. (2014/2015), “Traffic Simulation for All: A Real World Traffic Scenario from the City of Bologna.”**

- DOI: `10.1007/978-3-319-15024-6_4`
- Official DLR record: https://elib.dlr.de/89354/
- Official scenario catalog: https://sumo.dlr.de/docs/Data/Scenarios.html
- Official scenario repository: https://github.com/DLR-TS/sumo-scenarios

The Bologna scenarios were prepared from real-world network, traffic-light and demand information so researchers can evaluate traffic-management methods without first constructing a real scenario from scratch.

## Max-Pressure reference

**Pravin Varaiya (2013), “Max pressure control of a network of signalized intersections,” Transportation Research Part C 36, 177–195.**

- DOI: `10.1016/j.trc.2013.08.014`

Lab 01 implements the core movement-pressure idea only in a simple two-stage unit-validation intersection. Network-scale and RL pressure methods are intentionally deferred to later labs.
