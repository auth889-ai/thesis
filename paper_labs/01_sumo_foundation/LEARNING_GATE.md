# Lab 01 Learning Gate

You should be able to explain these in your own words before Lab 01 is marked PASS.

## Dependency order

### 1. Road network
A traffic network is represented by junctions connected by directed road segments. In SUMO, roads are built from **nodes/junctions**, **edges**, and **lanes**.

**Tiny example:** `North -> Center -> South` means a vehicle traverses two directed edges through the center junction.

**DhakaFlow connection:** later Dhaka OSM is converted into exactly this simulation representation.

### 2. Junction / node
A point where road segments meet. A signalized intersection is a junction controlled by a traffic-light system.

### 3. Edge
A directed road segment between junctions. Two-way streets are normally represented by two opposite directed edges.

### 4. Lane
A lane belongs to an edge and carries vehicles with attributes such as speed and permissions.

### 5. Route
The ordered sequence of edges a vehicle follows.

### 6. Traffic-light phase
A phase is the signal state active for a period of time. In SUMO, characters such as `G`, `g`, `y`, and `r` describe the state of controlled movements.

### 7. Cycle
The ordered repetition of traffic-light phases.

### 8. Green / yellow / all-red
Green serves movements, yellow gives transition/clearance, and all-red can provide additional clearance. Safety transitions are not optional details.

### 9. SUMO
SUMO is a microscopic traffic simulator: individual vehicles move through a network according to traffic-demand, route, vehicle, junction and signal models.

### 10. TraCI
TraCI is the online Traffic Control Interface. Python can read simulation state (queues, vehicles, signals) and change control decisions while SUMO is running.

### 11. Queue
Vehicles that are effectively stopped/halting on an approach. In this lab, SUMO lane halting counts are used as a queue proxy.

### 12. Waiting time
Time a vehicle spends below SUMO's waiting threshold. It is different from total trip duration.

### 13. Travel time
Time from vehicle departure to arrival.

### 14. Throughput
Number of vehicles completing the measured network/trip during the experiment.

### 15. Stops
Repeated waiting episodes are used as a simple stop proxy from `tripinfo` when available.

### 16. Fixed-Time control
The signal follows a predeclared timing plan regardless of current traffic.

### 17. Actuated control
Signal timing reacts to traffic. This lab's queue-actuated controller decides whether to extend or terminate a green within safe min/max limits.

### 18. Pressure
For a movement from incoming lane `i` to outgoing lane `j`, a simple movement pressure is:

`pressure(i->j) = queue(i) - queue(j)`

High positive pressure means traffic is building upstream relative to downstream storage.

### 19. Max-Pressure
At a decision point, score feasible green stages from movement pressures and favor the stage with highest pressure while respecting safe transition logic.

## What does NOT need mastery yet

- PPO / MAPPO
- PressLight / FRAP / CoLight
- Dhaka calibration
- OSM import details
- GNN forecasting
- full multi-intersection pressure theory

Those have later learning gates.

## 5-question self-check

1. What is the difference between an edge and a lane?
2. Why is TraCI necessary if SUMO already runs a simulation?
3. Why can a queue-actuated controller outperform fixed timing when demand changes?
4. In `q_in - q_out`, why does downstream queue matter?
5. Why must we compare controllers on the same demand, seeds and safety rules?

**Learning PASS:** answer all five correctly in your own words and explain how Lab 01 becomes the environment for later DhakaFlow RL.
