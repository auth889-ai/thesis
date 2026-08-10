# PAPER_SUMMARY — Lab 00

## Core idea

Urban congestion is a **network state**, not merely a single-road condition. The paper uses the Macroscopic Fundamental Diagram (MFD) to relate network accumulation `n` to travel production `P(n)`. The fitted MFD has a maximum `P*` at critical accumulation `n*`. Below `n*`, adding vehicles can increase production; beyond `n*`, additional vehicles reduce production and the network is macroscopically congested.

Key relationship:

`v = P / n`, so critical speed is `v* = P* / n*`.

## Paper scale

The 2019 analysis reports 41 cities and 107 regional networks. Current UTD19 public release advertises 40 cities. This project records that mismatch rather than hiding it.

## Method path

1. Stationary detector flow + occupancy/speed.
2. Error/outlier/noise handling.
3. Regional network aggregation.
4. Re-sampling to reduce heterogeneity bias.
5. Upper-bound extraction from high flow quantiles at density bins.
6. Nonlinear MFD fit.
7. Critical point = fitted function maximum.
8. Network topology regression is a later/full reproduction extension, not necessary to understand MFD mechanics.

## Relevance to DhakaFlow Nexus

Forecasting later predicts whether the live network is moving toward `n*`/spillback. SUMO provides the controllable digital twin. RL/MARL later chooses signal/routing actions intended to keep the network away from damaging congested states.
