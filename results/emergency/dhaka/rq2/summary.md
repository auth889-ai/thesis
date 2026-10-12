# RQ2 ambulance alert — summary

- With every vehicle equipped, the alert's median saving is -0.5 s (-0.3 %) at demand x0.5; 0.5 s (0.2 %) at demand x1; 2.5 s (1.1 %) at demand x2; 3.5 s (1.2 %) at demand x3; -2.0 s (-0.5 %) at demand x4.
- No equipped share reaches a median saving of 10 % at any density.
- Time saved falls with the free width ahead of the ambulance in the siren-only run (Spearman rho -0.16, 95 % CI -0.248 to -0.062, 400 paired runs) and rises with the queue at the route's signals (rho 0.179, CI 0.081 to 0.272). It is not clearly related to the share of alerted vehicles that actually moved aside (rho -0.003, CI -0.098 to 0.093). It is not clearly related to how long the siren-only ambulance stood blocked (rho 0.005, CI -0.093 to 0.104). The free width ahead hardly changes with density (7.71-8.42 m over all levels): on this route there is room to move aside at every level, so room is not what limits the alert. Smarter signals do more: the Q-learning signals' median saving beats the alert to every vehicle at 5 of 5 densities, which suggests the ambulance's delay on this route sits at the junctions more than behind vehicles that could move aside.
- In 70 of 400 alert runs the ambulance was more than 5 s slower than with the siren alone (worst 552 s slower, at demand x4); these runs are kept in every mean, not dropped.
- Q-learning signals without the alert: median saving 11.0 s at x0.5, 32.5 s at x1, 36.0 s at x2, 39.0 s at x3, 92.5 s at x4 against SUMO's own signal programmes (3 signals near the route controlled).
- On the whole network, Dhaka's recorded density at the INT camera (57.7 vehicles/km, 07:00-08:00) is not reached before the simulation gridlocks: the densest run gives 4.54 vehicles/km on that section.
- At the density the corridor reaches (54.37 vehicles/km on the INT section against the recorded 57.7), the alert to every vehicle saves a median 26.0 s (time saved, 25-75 %: -17.0 to 39.8 s) over 10 paired seeds, 4 of them slower than the siren alone; with signal preemption it saves a median 3.0 s (time saved, 25-75 %: -21.0 to 32.5 s); with Q-learning signals and no alert it costs a median 49.5 s (time saved, 25-75 %: -243.8 to 140.0 s). Only 653 vehicles an hour pass the section there, against 1184 recorded: the density matches, the flow does not.
- At the Dhaka-density level, time saved is not clearly related to the free width ahead (rho -0.123, CI -0.367 to 0.129, 80 paired runs), is not clearly related to the queue at the route's signals (rho -0.063, CI -0.291 to 0.169) and rises with how long the siren-only ambulance stood blocked (rho 0.294, CI 0.052 to 0.498; median 86.0 s blocked). Free width ahead averages 7.11 m there (whole network: 7.71-8.42 m).
- Moving aside (make-way v2): alerted vehicles keep their own route lane changes, and only those within 100 m ahead of the ambulance move aside. No published distance at which drivers act on an electronic alert was found, so 50 m and 100 m were piloted at the Dhaka-density level and chosen by a rule fixed before the pilot (the longer, unless it still produced a circular wait). The rule as fixed rejected both, only on waits that also occur identically in the siren-only runs of the same seeds; the owner amended it after the pilot (a flagged wait counts only if the siren-only run of the same seed does not show it), which gives 100 m. Time saved was not used in the choice.
- On the 5 seeds where the Q-learning signals made the ambulance slower at Dhaka density, it stood 2065 s in all (siren-only on the same seeds: 699 s). 0 of those seconds were within 100 m of a traffic light; the next light on its route was green for it in 1962 s, red in 0 s, and there was no light left ahead in 103 s. The queues it stood in were short (median 2 vehicles to the head) and their heads were not at a light; many ended at a vehicle waiting to change lane. So the lights did not hold the ambulance directly. The Q-learning controllers change when traffic is released around the route, which may load the junctions where it stood, but these logs do not show that path; the cause of the slowdown is not established.
- Why the simulation stays far below Dhaka's recorded density at the INT camera (57.7 vehicles/km, 07:00-08:00): (1) not the definition: both count every vehicle class on the whole road over about 90 m (89.2 m camera zone, 91.8 m simulated section); (2) not the space per vehicle: SUMO's lengths and gaps for this mix allow about 443.3 vehicles/km on those 3 lanes, and other roads in the same run reach 359.1 vehicles/km at gridlock; (3) partly lane discipline: with smaller lateral gaps for two-wheelers, rickshaws and CNGs the section's mean density rises from 4.8 to 24.82 vehicles/km, still below the recorded value; (4) mainly supply: only 260 vehicles an hour enter the section in the simulation, against 1184 recorded, because the generated trips do not load this road and the network gridlocks elsewhere first. So the whole-network ambulance results come from a simulation that does not reach Dhaka's recorded density on the road it measures. (5) Supply tested: a corridor 300 m around the route, loaded with the recorded counts at INT and BM and the smaller lateral gaps, overshoots at the full counts (200.3 vehicles/km on INT) and reaches 54.37 vehicles/km at x0.78 of the counts, inside the recorded range (36.5-126.6); but only 653 vehicles an hour pass, against 1184 recorded. The density is reached; the recorded flow at that density is not.

## Time saved (s): median [25 %, 75 %]; mean ± sd; runs more than 5 s slower than the siren alone

| Arm | Share | x0.5 | x1 | x2 | x3 | x4 | Dhaka density |
|---|---|---|---|---|---|---|---|
| Alert to vehicles | 25 % | 0.0 [0.0, 0.0]; 0.0 ± 0.0; 0 slower | 0.0 [0.0, 0.0]; 0.0 ± 0.0; 0 slower | 0.5 [-0.8, 2.8]; 0.6 ± 4.7; 1 slower | 0.0 [-2.5, 8.5]; 2.2 ± 8.5; 1 slower | 0.0 [-1.8, 0.0]; -2.6 ± 6.5; 1 slower | 6.0 [-18.8, 40.0]; 15.8 ± 72.9; 4 slower |
| Alert to vehicles | 50 % | 0.0 [-2.8, 1.0]; -2.1 ± 6.6; 1 slower | 0.0 [-3.0, 0.8]; -1.0 ± 3.3; 1 slower | 0.0 [-3.0, 1.0]; -0.4 ± 4.3; 1 slower | 1.5 [-0.8, 4.5]; 4.8 ± 12.0; 1 slower | 2.5 [-1.5, 5.0]; 56.5 ± 167.7; 1 slower | 7.5 [-23.8, 124.0]; 47.8 ± 138.7; 4 slower |
| Alert to vehicles | 75 % | 0.0 [-1.8, 1.8]; -1.7 ± 6.4; 1 slower | 0.0 [-2.5, 3.2]; -0.2 ± 5.5; 2 slower | 0.5 [0.0, 3.0]; 0.9 ± 2.8; 0 slower | 3.0 [-1.0, 9.0]; 1.7 ± 20.6; 1 slower | 0.5 [-9.5, 5.2]; 2.6 ± 275.4; 3 slower | 24.0 [1.0, 72.5]; 70.3 ± 118.7; 2 slower |
| Alert to vehicles | 100 % | -0.5 [-2.8, 2.5]; 2.3 ± 8.9; 0 slower | 0.5 [-0.8, 2.8]; 0.0 ± 4.3; 1 slower | 2.5 [-0.5, 4.0]; 2.6 ± 6.9; 1 slower | 3.5 [-3.8, 12.0]; -0.9 ± 24.6; 2 slower | -2.0 [-13.5, 6.0]; -37.8 ± 91.0; 5 slower | 26.0 [-17.0, 39.8]; 60.4 ± 124.2; 4 slower |
| Alert + signal preemption | 25 % | -0.5 [-1.8, 1.8]; 2.4 ± 11.7; 1 slower | 4.5 [-7.5, 16.0]; 4.6 ± 14.2; 4 slower | 0.0 [-6.5, 5.2]; -1.1 ± 8.0; 3 slower | 1.5 [-7.0, 15.5]; 2.9 ± 17.2; 3 slower | -1.0 [-2.0, -0.2]; 0.5 ± 11.2; 1 slower | 4.0 [-110.2, 63.0]; -31.0 ± 159.0; 5 slower |
| Alert + signal preemption | 50 % | 0.5 [-5.0, 2.5]; 1.8 ± 12.5; 3 slower | 8.0 [-5.2, 11.5]; 5.2 ± 12.8; 3 slower | 2.0 [-7.8, 3.8]; -1.5 ± 8.7; 3 slower | 6.0 [-4.2, 18.2]; 8.1 ± 13.8; 3 slower | 0.5 [-1.8, 8.0]; 57.2 ± 176.2; 1 slower | 62.5 [-27.5, 130.5]; 32.5 ± 175.1; 3 slower |
| Alert + signal preemption | 75 % | -1.5 [-7.8, 6.2]; 0.7 ± 13.9; 3 slower | 4.0 [-2.8, 15.5]; 5.9 ± 11.9; 2 slower | -0.5 [-1.8, 5.8]; -0.5 ± 10.6; 1 slower | -2.0 [-7.5, 14.2]; -1.6 ± 20.5; 4 slower | 0.0 [-10.5, 5.8]; -59.3 ± 173.8; 3 slower | 15.5 [-81.2, 36.5]; -62.1 ± 264.1; 4 slower |
| Alert + signal preemption | 100 % | 1.0 [-1.5, 3.8]; 2.0 ± 9.7; 1 slower | 12.0 [7.0, 18.5]; 12.0 ± 7.7; 0 slower | 2.5 [0.0, 7.5]; 3.6 ± 5.2; 0 slower | -3.0 [-10.2, 9.5]; -3.8 ± 21.1; 5 slower | 6.0 [-2.5, 8.8]; -2.7 ± 251.7; 2 slower | 3.0 [-21.0, 32.5]; 18.3 ± 110.3; 4 slower |
| Q-learning signals (sumo-rl), no alert | 0 % | 11.0 [9.2, 12.8]; 12.1 ± 10.3; 0 slower | 32.5 [27.2, 39.2]; 31.1 ± 10.2; 0 slower | 36.0 [31.8, 42.0]; -2.2 ± 186.1; 2 slower | 39.0 [-158.8, 82.8]; 10.7 ± 291.5; 4 slower | 92.5 [-168.8, 290.5]; 124.5 ± 402.5; 4 slower | -49.5 [-243.8, 140.0]; -54.8 ± 264.4; 5 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | 11.5 [9.2, 14.0]; 14.6 ± 11.6; 0 slower | 33.0 [32.2, 39.0]; 32.5 ± 9.2; 0 slower | 36.0 [25.8, 39.8]; -62.6 ± 297.2; 2 slower | -25.0 [-190.0, 80.0]; -15.9 ± 308.1; 5 slower | -15.5 [-292.5, 302.8]; 74.3 ± 439.3; 5 slower | 33.5 [-135.0, 150.8]; 0.9 ± 255.4; 4 slower |

## Density ladder (siren only)

| Demand | Vehicles | Section density (veh/km) | Ambulance (s) | Not arrived | Teleports | Gridlock |
|---|---|---|---|---|---|---|
| x0.5 | 451 | 1.17 | 190.4 | 0/5 | 0.0% | no |
| x1 | 900 | 1.97 | 207.8 | 0/5 | 0.0% | no |
| x2 | 1800 | 3.88 | 279.2 | 0/5 | 0.6% | no |
| x3 | 2700 | 4.54 | 357.8 | 0/5 | 2.7% | no |
| x4 | 3599 | 4.53 | 600.8 | 0/5 | 6.3% | yes |
| Dhaka density (corridor x0.78) | – | 54.37 (INT, median of 5 seeds; recorded 57.7) | – | – | – | – |

## Old (make-way v1, artefact) against new (v2): median saved [25 %, 75 %]; slower runs

| Arm | Share | Level | v1 | v2 |
|---|---|---|---|---|
| Alert to vehicles | 25 % | x0.5 | 0.0 [0.0, 0.0]; 0 of 10 slower | 0.0 [0.0, 0.0]; 0 of 10 slower |
| Alert to vehicles | 25 % | x1 | 0.0 [0.0, 0.0]; 0 of 10 slower | 0.0 [0.0, 0.0]; 0 of 10 slower |
| Alert to vehicles | 25 % | x2 | 3.0 [-1.8, 5.5]; 2 of 10 slower | 0.5 [-0.8, 2.8]; 1 of 10 slower |
| Alert to vehicles | 25 % | x3 | -4.5 [-9.5, -1.2]; 5 of 10 slower | 0.0 [-2.5, 8.5]; 1 of 10 slower |
| Alert to vehicles | 25 % | x4 | -3.0 [-27.0, 1.5]; 4 of 10 slower | 0.0 [-1.8, 0.0]; 1 of 10 slower |
| Alert to vehicles | 25 % | Dhaka density | 28.5 [-20.5, 146.0]; 3 of 10 slower | 6.0 [-18.8, 40.0]; 4 of 10 slower |
| Alert to vehicles | 50 % | x0.5 | -1.0 [-2.8, 5.0]; 1 of 10 slower | 0.0 [-2.8, 1.0]; 1 of 10 slower |
| Alert to vehicles | 50 % | x1 | -0.5 [-4.8, 6.2]; 3 of 10 slower | 0.0 [-3.0, 0.8]; 1 of 10 slower |
| Alert to vehicles | 50 % | x2 | -2.0 [-15.5, 1.0]; 4 of 10 slower | 0.0 [-3.0, 1.0]; 1 of 10 slower |
| Alert to vehicles | 50 % | x3 | 4.5 [-1.0, 12.0]; 1 of 10 slower | 1.5 [-0.8, 4.5]; 1 of 10 slower |
| Alert to vehicles | 50 % | x4 | -17.5 [-37.8, 4.5]; 6 of 10 slower | 2.5 [-1.5, 5.0]; 1 of 10 slower |
| Alert to vehicles | 50 % | Dhaka density | 57.5 [16.8, 140.0]; 2 of 10 slower | 7.5 [-23.8, 124.0]; 4 of 10 slower |
| Alert to vehicles | 75 % | x0.5 | -1.5 [-2.8, 1.5]; 2 of 10 slower | 0.0 [-1.8, 1.8]; 1 of 10 slower |
| Alert to vehicles | 75 % | x1 | 12.5 [3.5, 22.5]; 2 of 10 slower | 0.0 [-2.5, 3.2]; 2 of 10 slower |
| Alert to vehicles | 75 % | x2 | -3.5 [-11.2, 1.8]; 5 of 10 slower | 0.5 [0.0, 3.0]; 0 of 10 slower |
| Alert to vehicles | 75 % | x3 | 10.5 [4.0, 21.0]; 0 of 10 slower | 3.0 [-1.0, 9.0]; 1 of 10 slower |
| Alert to vehicles | 75 % | x4 | 8.5 [-10.2, 76.5]; 3 of 10 slower | 0.5 [-9.5, 5.2]; 3 of 10 slower |
| Alert to vehicles | 75 % | Dhaka density | -8.5 [-302.0, 37.8]; 5 of 10 slower | 24.0 [1.0, 72.5]; 2 of 10 slower |
| Alert to vehicles | 100 % | x0.5 | -0.5 [-5.0, 2.8]; 3 of 10 slower | -0.5 [-2.8, 2.5]; 0 of 10 slower |
| Alert to vehicles | 100 % | x1 | 23.0 [18.8, 28.5]; 1 of 10 slower | 0.5 [-0.8, 2.8]; 1 of 10 slower |
| Alert to vehicles | 100 % | x2 | 7.0 [-27.2, 14.2]; 3 of 10 slower | 2.5 [-0.5, 4.0]; 1 of 10 slower |
| Alert to vehicles | 100 % | x3 | 10.5 [-19.8, 21.2]; 4 of 10 slower | 3.5 [-3.8, 12.0]; 2 of 10 slower |
| Alert to vehicles | 100 % | x4 | 53.5 [-125.0, 173.5]; 3 of 10 slower | -2.0 [-13.5, 6.0]; 5 of 10 slower |
| Alert to vehicles | 100 % | Dhaka density | -230.0 [-291.8, -20.8]; 7 of 10 slower | 26.0 [-17.0, 39.8]; 4 of 10 slower |
| Alert + signal preemption | 25 % | x0.5 | -0.5 [-1.8, 1.8]; 1 of 10 slower | -0.5 [-1.8, 1.8]; 1 of 10 slower |
| Alert + signal preemption | 25 % | x1 | 10.0 [-4.5, 16.2]; 3 of 10 slower | 4.5 [-7.5, 16.0]; 4 of 10 slower |
| Alert + signal preemption | 25 % | x2 | 3.5 [-3.2, 12.0]; 2 of 10 slower | 0.0 [-6.5, 5.2]; 3 of 10 slower |
| Alert + signal preemption | 25 % | x3 | 3.0 [-6.2, 22.0]; 3 of 10 slower | 1.5 [-7.0, 15.5]; 3 of 10 slower |
| Alert + signal preemption | 25 % | x4 | 0.0 [-21.2, 3.8]; 4 of 10 slower | -1.0 [-2.0, -0.2]; 1 of 10 slower |
| Alert + signal preemption | 25 % | Dhaka density | 33.5 [-13.0, 142.2]; 4 of 10 slower | 4.0 [-110.2, 63.0]; 5 of 10 slower |
| Alert + signal preemption | 50 % | x0.5 | 1.0 [-10.5, 3.8]; 4 of 10 slower | 0.5 [-5.0, 2.5]; 3 of 10 slower |
| Alert + signal preemption | 50 % | x1 | 8.5 [2.0, 22.8]; 1 of 10 slower | 8.0 [-5.2, 11.5]; 3 of 10 slower |
| Alert + signal preemption | 50 % | x2 | -1.0 [-11.2, 7.0]; 4 of 10 slower | 2.0 [-7.8, 3.8]; 3 of 10 slower |
| Alert + signal preemption | 50 % | x3 | 8.0 [4.0, 16.8]; 0 of 10 slower | 6.0 [-4.2, 18.2]; 3 of 10 slower |
| Alert + signal preemption | 50 % | x4 | -13.5 [-185.2, 1.8]; 5 of 10 slower | 0.5 [-1.8, 8.0]; 1 of 10 slower |
| Alert + signal preemption | 50 % | Dhaka density | 34.0 [23.2, 57.2]; 1 of 10 slower | 62.5 [-27.5, 130.5]; 3 of 10 slower |
| Alert + signal preemption | 75 % | x0.5 | 1.0 [-10.5, 3.0]; 4 of 10 slower | -1.5 [-7.8, 6.2]; 3 of 10 slower |
| Alert + signal preemption | 75 % | x1 | 10.5 [4.5, 23.0]; 1 of 10 slower | 4.0 [-2.8, 15.5]; 2 of 10 slower |
| Alert + signal preemption | 75 % | x2 | 3.0 [-12.0, 10.2]; 3 of 10 slower | -0.5 [-1.8, 5.8]; 1 of 10 slower |
| Alert + signal preemption | 75 % | x3 | 13.0 [10.2, 22.8]; 0 of 10 slower | -2.0 [-7.5, 14.2]; 4 of 10 slower |
| Alert + signal preemption | 75 % | x4 | 10.5 [-3.5, 86.8]; 2 of 10 slower | 0.0 [-10.5, 5.8]; 3 of 10 slower |
| Alert + signal preemption | 75 % | Dhaka density | 23.0 [-158.5, 41.5]; 3 of 10 slower | 15.5 [-81.2, 36.5]; 4 of 10 slower |
| Alert + signal preemption | 100 % | x0.5 | 1.0 [-3.0, 7.2]; 2 of 10 slower | 1.0 [-1.5, 3.8]; 1 of 10 slower |
| Alert + signal preemption | 100 % | x1 | 24.0 [12.5, 29.5]; 0 of 10 slower | 12.0 [7.0, 18.5]; 0 of 10 slower |
| Alert + signal preemption | 100 % | x2 | 14.5 [-9.8, 20.0]; 3 of 10 slower | 2.5 [0.0, 7.5]; 0 of 10 slower |
| Alert + signal preemption | 100 % | x3 | 18.5 [8.8, 174.2]; 0 of 10 slower | -3.0 [-10.2, 9.5]; 5 of 10 slower |
| Alert + signal preemption | 100 % | x4 | 24.5 [-129.5, 151.5]; 3 of 10 slower | 6.0 [-2.5, 8.8]; 2 of 10 slower |
| Alert + signal preemption | 100 % | Dhaka density | 47.5 [-164.0, 82.0]; 3 of 10 slower | 3.0 [-21.0, 32.5]; 4 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | x0.5 | 8.5 [3.5, 14.5]; 0 of 10 slower | 11.5 [9.2, 14.0]; 0 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | x1 | 29.5 [25.0, 37.5]; 0 of 12 slower | 33.0 [32.2, 39.0]; 0 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | x2 | 38.0 [29.0, 47.5]; 1 of 10 slower | 36.0 [25.8, 39.8]; 2 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | x3 | 41.0 [-96.0, 101.0]; 4 of 13 slower | -25.0 [-190.0, 80.0]; 5 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | x4 | 119.0 [-493.5, 284.5]; 4 of 11 slower | -15.5 [-292.5, 302.8]; 5 of 10 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | Dhaka density | 24.0 [-103.5, 179.0]; 5 of 11 slower | 33.5 [-135.0, 150.8]; 4 of 10 slower |

## Figures

- `results/emergency/dhaka/rq2/figures/rq2_density.png`
- `results/emergency/dhaka/rq2/figures/rq2_share.png`
- `results/emergency/dhaka/rq2/figures/rq2_why.png`
