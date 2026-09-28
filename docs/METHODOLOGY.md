# Methodology

## Scientific Core

The frozen stress case is selected on development seeds using stability, congestion, arrival, speed, and teleport thresholds. Every comparison starts from the same saved SUMO state, with identical demand, lane caps, signals, and random state.

1. Run BASELINE, REACTIVE, and ORACLE.
2. Gate future-information value from ORACLE versus REACTIVE using paired vehicle-hours and a 95% confidence interval.
3. Run persistence and Graph WaveNet only when the oracle gate passes for forecastable congestion.
4. Treat unexpected incidents separately: they test V2X detection and online correction, not forecast skill.

The primary metric is total vehicle-hours including never-inserted vehicles. Teleports, arrivals, queues, waiting, and route changes remain reported rather than filtered.

## Forecast Contract

The canonical model is Graph WaveNet on 207-node METR-LA. Every inference records model, checkpoint hash, parameters, input/output shapes, graph size, horizons, runtime, MAE/RMSE, skill versus persistence, and validation status. Persistence and historical average remain baselines.

## Networking Contract

The Python channel is explicitly a **SIMULATED V2X EMULATOR**. Each applied recommendation follows: vehicle status, uplink result, server receipt, fresh inference, optimization, recommendation, downlink result, and TraCI route change.

## Method References

- Wu et al., *Graph WaveNet for Deep Spatial-Temporal Graph Modeling*, IJCAI 2019. The canonical model uses its spatial-temporal graph formulation; the repository reports its own held-out METR-LA result rather than presenting the paper's result as a local deployment result. https://arxiv.org/abs/1906.00121
- Eclipse SUMO, TraCI vehicle state API. The closed loop applies a received recommendation with `traci.vehicle.setRoute`, whose route must begin at the vehicle's current edge. https://sumo.dlr.de/docs/TraCI/Change_Vehicle_State.html
