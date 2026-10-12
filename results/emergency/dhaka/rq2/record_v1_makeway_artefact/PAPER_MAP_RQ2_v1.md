## RQ2 — Ambulance alert: how far it helps, and why

**Question.** How much time does the ambulance alert save, at which traffic densities and equipped shares, against which baselines, and why?

**Data.**
- **Network:** the Dhaka twin's OpenStreetMap network.
- **Demand:** the generated demand (randomTrips, SYNTHETIC_WHAT_IF, not calibrated), scaled by SUMO `--scale`.
- **Trip:** the ambulance's 3.4 km route crosses 2 signals and the DhaTraX INT camera section.

**Arms (baselines).**
- Siren only (SUMO's bluelight behaviour, no message).
- The alert to equipped vehicles, over ITS-G5.
- The alert plus signal preemption (adaptive-traffic-signal-rl, MIT, reproduced earlier).
- **sumo-rl** Q-learning signals (MIT, commit 86f0fc4), with and without the alert. It controls the 3 signals within 500 m of the route, with 30 training episodes per density level on separate seeds, then frozen.

**Reproduced first.** sumo-rl's own `ql_single-intersection.py` against its fixed timing. Q-learning's mean total waiting time over the last 20 % of steps is 31.2 s against fixed timing's 3418365.7 s: pass. The repository publishes no number, so this checks the direction of its README figure. **The fixed-timing comparison is lopsided:** with 42 s greens on this example's routes, the queue under fixed timing grows throughout the run, so the comparison passes trivially. The real evidence is the learning curve: in each of three runs, Q-learning's waiting time falls from 78.9, 73.3, 86.8 s in the first tenth to 28.9, 31.0, 33.6 s in the last fifth.

**Protocol.**
- **Density ladder:** demand ×0.5, ×1, ×2, ×3, ×4, until gridlock (no-alert ambulance not arrived on >= 3 of 5 seeds, or teleports > 5% of vehicles).
- **Equipped shares:** 25, 50, 75 and 100 %.
- **Seeds:** 5 siren-only seeds per level for the gridlock verdict; 10 finished (arm, siren-only) pairs per table cell. A seed is replaced when SUMO's bluelight device crashes.
- **Time saved:** each run against the siren-only run of the same seed and density.
- **Measures, per run:** free width ahead of the ambulance, the share of alerted vehicles that moved aside, seconds blocked, and queues at the route's signals.

**Dhaka-density row (RQ2b).**
- **Corridor:** the edges within 300 m of the ambulance route (1198 of 6527), cut with SUMO's `netconvert --keep-edges.input-file`, so gridlock on unrelated roads cannot starve the corridor. The route's signal programmes are unchanged by the cut.
- **Demand:** SUMO's `routeSampler.py` matched to DhaTraX's recorded 5-minute counts at INT and BM, 07:00-08:00 (3451 sampled trips plus 937 uncalibrated background trips), the Dhaka class mix, and the smaller lateral gaps for two-wheelers, rickshaws and CNGs (sublane model, 0.8 m).
- **Density reached (INT, no ambulance):** at the full counts, 200.3 vehicles/km (overshoot). Scales tried (median over 5 seeds): x0.4: 9.08; x0.5: 11.23; x0.6: 12.82; x0.7: 15.14; x0.72: 20.3; x0.75: 68.38; x0.78: 54.37; x0.8: 103.08. Chosen x0.78: **54.37 vehicles/km** (seeds' 25-75 %: 42.7-83.7) against the recorded **57.7** (07:00-08:00, 25-75 %: 36.5-126.6); label "Dhaka density".
- **Flow at that density:** 653 vehicles/h through INT against 1184 recorded.
- **Arms:** siren only, alert and alert plus preemption at 25-100 % equipped, Q-learning signals trained 30 episodes on the corridor, with and without the alert; 10 paired seeds each.

### Results

#### Time saved (s): median [25 %, 75 %]; mean ± sd; runs more than 5 s slower than the siren alone

| Arm | Share | x0.5 | x1 | x2 | x3 | x4 | Dhaka density |
|---|---|---|---|---|---|---|---|
| Alert to vehicles | 25 % | 0.0 [0.0, 0.0]; 0.0 ± 0.0; 0 slower | 0.0 [0.0, 0.0]; -0.1 ± 0.3; 0 slower | 3.0 [-1.8, 5.5]; 1.3 ± 6.0; 2 slower | -4.5 [-9.5, -1.2]; -5.4 ± 9.2; 5 slower | -3.0 [-27.0, 1.5]; -37.5 ± 94.6; 4 slower | 28.5 [-20.5, 146.0]; 94.3 ± 156.2; 3 slower |
| Alert to vehicles | 50 % | -1.0 [-2.8, 5.0]; 2.5 ± 13.5; 1 slower | -0.5 [-4.8, 6.2]; 1.7 ± 9.7; 3 slower | -2.0 [-15.5, 1.0]; -52.3 ± 104.1; 4 slower | 4.5 [-1.0, 12.0]; 7.2 ± 13.3; 1 slower | -17.5 [-37.8, 4.5]; -18.3 ± 167.7; 6 slower | 57.5 [16.8, 140.0]; 63.2 ± 143.8; 2 slower |
| Alert to vehicles | 75 % | -1.5 [-2.8, 1.5]; -1.4 ± 13.6; 2 slower | 12.5 [3.5, 22.5]; 9.8 ± 15.2; 2 slower | -3.5 [-11.2, 1.8]; -49.0 ± 105.4; 5 slower | 10.5 [4.0, 21.0]; 37.2 ± 80.8; 0 slower | 8.5 [-10.2, 76.5]; 11.4 ± 305.3; 3 slower | -8.5 [-302.0, 37.8]; -96.6 ± 230.8; 5 slower |
| Alert to vehicles | 100 % | -0.5 [-5.0, 2.8]; -27.1 ± 85.8; 3 slower | 23.0 [18.8, 28.5]; 20.4 ± 14.9; 1 slower | 7.0 [-27.2, 14.2]; -32.6 ± 133.9; 3 slower | 10.5 [-19.8, 21.2]; -0.2 ± 188.9; 4 slower | 53.5 [-125.0, 173.5]; 17.4 ± 368.9; 3 slower | -230.0 [-291.8, -20.8]; -131.1 ± 236.5; 7 slower |
| Alert + signal preemption | 25 % | -0.5 [-1.8, 1.8]; 2.4 ± 11.7; 1 slower | 10.0 [-4.5, 16.2]; 7.5 ± 12.8; 3 slower | 3.5 [-3.2, 12.0]; 1.3 ± 15.6; 2 slower | 3.0 [-6.2, 22.0]; 7.2 ± 16.7; 3 slower | 0.0 [-21.2, 3.8]; -32.2 ± 87.8; 4 slower | 33.5 [-13.0, 142.2]; 71.2 ± 188.5; 4 slower |
| Alert + signal preemption | 50 % | 1.0 [-10.5, 3.8]; -0.4 ± 16.1; 4 slower | 8.5 [2.0, 22.8]; 10.6 ± 12.7; 1 slower | -1.0 [-11.2, 7.0]; -49.3 ± 108.5; 4 slower | 8.0 [4.0, 16.8]; 12.8 ± 13.4; 0 slower | -13.5 [-185.2, 1.8]; -68.7 ± 247.7; 5 slower | 34.0 [23.2, 57.2]; 68.5 ± 169.5; 1 slower |
| Alert + signal preemption | 75 % | 1.0 [-10.5, 3.0]; -0.7 ± 15.8; 4 slower | 10.5 [4.5, 23.0]; 12.3 ± 11.4; 1 slower | 3.0 [-12.0, 10.2]; -46.1 ± 108.1; 3 slower | 13.0 [10.2, 22.8]; 67.2 ± 115.6; 0 slower | 10.5 [-3.5, 86.8]; 92.0 ± 198.6; 2 slower | 23.0 [-158.5, 41.5]; -82.1 ± 349.4; 3 slower |
| Alert + signal preemption | 100 % | 1.0 [-3.0, 7.2]; -23.1 ± 87.0; 2 slower | 24.0 [12.5, 29.5]; 21.1 ± 11.8; 0 slower | 14.5 [-9.8, 20.0]; -27.4 ± 134.6; 3 slower | 18.5 [8.8, 174.2]; 87.7 ± 122.6; 0 slower | 24.5 [-129.5, 151.5]; -45.8 ± 408.2; 3 slower | 47.5 [-164.0, 82.0]; 9.7 ± 218.0; 3 slower |
| Q-learning signals (sumo-rl), no alert | 0 % | 11.0 [9.2, 12.8]; 12.1 ± 10.3; 0 slower | 32.5 [27.2, 39.2]; 31.1 ± 10.2; 0 slower | 36.0 [31.8, 42.0]; -2.2 ± 186.1; 2 slower | 39.0 [-158.8, 82.8]; 10.7 ± 291.5; 4 slower | 92.5 [-168.8, 290.5]; 124.5 ± 402.5; 4 slower | -49.5 [-243.8, 140.0]; -54.8 ± 264.4; 5 slower |
| Q-learning signals (sumo-rl) + alert | 100 % | 8.5 [3.5, 14.5]; 12.5 ± 12.6; 0 slower | 29.5 [25.0, 37.5]; 28.9 ± 10.5; 0 slower | 38.0 [29.0, 47.5]; 44.1 ± 108.5; 1 slower | 41.0 [-96.0, 101.0]; 9.2 ± 281.4; 4 slower | 119.0 [-493.5, 284.5]; -28.4 ± 506.2; 4 slower | 24.0 [-103.5, 179.0]; 32.5 ± 223.5; 5 slower |

#### Density ladder (siren only)

| Demand | Vehicles | Section density (veh/km) | Ambulance (s) | Not arrived | Teleports | Gridlock |
|---|---|---|---|---|---|---|
| x0.5 | 451 | 1.17 | 190.4 | 0/5 | 0.0% | no |
| x1 | 900 | 1.97 | 207.8 | 0/5 | 0.0% | no |
| x2 | 1800 | 3.88 | 279.2 | 0/5 | 0.6% | no |
| x3 | 2700 | 4.54 | 357.8 | 0/5 | 2.7% | no |
| x4 | 3599 | 4.53 | 600.8 | 0/5 | 6.3% | yes |
| Dhaka density (corridor x0.78) | – | 54.37 (INT, median of 5 seeds; recorded 57.7) | – | – | – | – |


### The finding

- With every vehicle equipped, the alert's median saving is -0.5 s (-0.3 %) at demand x0.5; 23.0 s (11.0 %) at demand x1; 7.0 s (2.8 %) at demand x2; 10.5 s (4.4 %) at demand x3; 53.5 s (16.9 %) at demand x4.
- A median saving of 10 % or more is reached only at demand x1 (from 100 % equipped), demand x4 (from 100 % equipped); at demand x0.5, demand x2, demand x3 no equipped share reaches it.
- In 97 of 400 alert runs the ambulance was more than 5 s slower than with the siren alone (worst 822 s slower, at demand x4); these runs are kept in every mean, not dropped.
- Q-learning signals without the alert: median saving 11.0 s at x0.5, 32.5 s at x1, 36.0 s at x2, 39.0 s at x3, 92.5 s at x4 against SUMO's own signal programmes (3 signals near the route controlled).
- On the whole network, Dhaka's recorded density at the INT camera (57.7 vehicles/km, 07:00-08:00) is not reached before the simulation gridlocks: the densest run gives 4.54 vehicles/km on that section.
- At the density the corridor reaches (54.37 vehicles/km on the INT section against the recorded 57.7), the alert to every vehicle costs a median 230.0 s (time saved, 25-75 %: -291.8 to -20.8 s) over 10 paired seeds, 7 of them slower than the siren alone; with signal preemption it saves a median 47.5 s (time saved, 25-75 %: -164.0 to 82.0 s); with Q-learning signals and no alert it costs a median 49.5 s (time saved, 25-75 %: -243.8 to 140.0 s). Only 653 vehicles an hour pass the section there, against 1184 recorded: the density matches, the flow does not.

### Why

Time saved falls with the free width ahead of the ambulance in the siren-only run (Spearman rho -0.172, 95 % CI -0.265 to -0.079, 400 paired runs) and is not clearly related to the queue at the route's signals (rho 0.041, CI -0.059 to 0.141). It is not clearly related to the share of alerted vehicles that actually moved aside (rho 0.08, CI -0.017 to 0.176). It rises with how long the siren-only ambulance stood blocked (rho 0.238, CI 0.138 to 0.332). The free width ahead hardly changes with density (7.67-8.42 m over all levels): on this route there is room to move aside at every level, so room is not what limits the alert. Smarter signals do more: the Q-learning signals' median saving beats the alert to every vehicle at 5 of 5 densities, which suggests the ambulance's delay on this route sits at the junctions more than behind vehicles that could move aside.

At the Dhaka-density level, time saved falls with the free width ahead (rho -0.416, CI -0.592 to -0.211, 80 paired runs), is not clearly related to the queue at the route's signals (rho -0.238, CI -0.481 to 0.007) and rises with how long the siren-only ambulance stood blocked (rho 0.565, CI 0.357 to 0.738; median 84.0 s blocked). Free width ahead averages 7.17 m there (whole network: 7.67-8.42 m).

**Why the alert slows the ambulance at Dhaka density (inspected).** In the 7 of 10 Dhaka-density runs where the alert to every vehicle made the ambulance slower, it stood 2870 s in all; 63 % of that time it was held by a chain of vehicles ending at an alerted vehicle that waited at the end of a lane it needed to leave. The make-way settings forbid that vehicle's own lane changes until the ambulance has passed it, and the ambulance cannot pass, so both wait until SUMO removes the vehicle after its 300 s teleport limit. A driver would not be expected to wait minutes at a lane end for an ambulance stuck behind them, and the wait ends only through the simulator's teleport, so this part is read as a simulation artefact of how moving aside is applied (our make-way rule, which copies SUMO's bluelight settings and holds them until the ambulance passes). Letting those vehicles keep their own lane changes turns the median into a saving of 37.0 s (25-75 %: -2.5 to 108.5 s, 8 runs, 2 slower, 2 crashed in SUMO); alerting only vehicles within 50 m ahead gives 65.5 s (-15.8 to 270.2 s, 3 of 10 slower); keeping junctions free of make-way changes nothing (median -230.0 s, the same runs). The other 37 % of the time the ambulance stood behind alerted vehicles with no such lane end among the four ahead, or with nothing alerted ahead; whether that is vehicles moving aside blocking each other, or the same wait further ahead, was not resolved. Ten seeds at one density: most of the slowdown at Dhaka density is a simulation artefact, and whether the alert helps there is not known. Details: `evidence/ambulance_rq2/inspect/dhaka/SLOWDOWN.md`.

Why the simulation stays far below Dhaka's recorded density at the INT camera (57.7 vehicles/km, 07:00-08:00): (1) not the definition: both count every vehicle class on the whole road over about 90 m (89.2 m camera zone, 91.8 m simulated section); (2) not the space per vehicle: SUMO's lengths and gaps for this mix allow about 443.3 vehicles/km on those 3 lanes, and other roads in the same run reach 359.1 vehicles/km at gridlock; (3) partly lane discipline: with smaller lateral gaps for two-wheelers, rickshaws and CNGs the section's mean density rises from 4.8 to 24.82 vehicles/km, still below the recorded value; (4) mainly supply: only 260 vehicles an hour enter the section in the simulation, against 1184 recorded, because the generated trips do not load this road and the network gridlocks elsewhere first. So the whole-network ambulance results come from a simulation that does not reach Dhaka's recorded density on the road it measures. (5) Supply tested: a corridor 300 m around the route, loaded with the recorded counts at INT and BM and the smaller lateral gaps, overshoots at the full counts (200.3 vehicles/km on INT) and reaches 54.37 vehicles/km at x0.78 of the counts, inside the recorded range (36.5-126.6); but only 653 vehicles an hour pass, against 1184 recorded. The density is reached; the recorded flow at that density is not.

### Figures

- `results/emergency/dhaka/rq2/figures/rq2_density.png`
- `results/emergency/dhaka/rq2/figures/rq2_share.png`
- `results/emergency/dhaka/rq2/figures/rq2_why.png`

### Threats to validity

- all traffic is simulated (SUMO); the demand is generated, not calibrated to Dhaka counts
- the ambulance's 3.4 km route crosses 2 signals; the Q-learning baseline controls the 3 signals within 500 m of it
- ITS-G5 only in the sweep; C-V2X and 4G at one density are in the earlier table
- SUMO 1.27.1's bluelight device crashes on some seeds; a crashed seed is replaced by the next one
- the simulation does not reach Dhaka's recorded density on the INT section (see density_gap): every ambulance number here is from traffic lighter on that road than Dhaka's recorded morning, and is not a statement about Dhaka at its recorded density
- Dhaka-density row: a corridor cut 300 m around the route (1198 of 6527 roads), with no traffic from the rest of the city
- Dhaka-density row: one recorded day per camera (INT 2026-04-19, BM 2026-04-20), two different days merged into one 07:00-08:00 window
- Dhaka-density row: the density matches (54.37 vs 57.7 vehicles/km) but the flow does not (653 vs 1184 vehicles/h): at the same density, traffic on the simulated section moves slower than the recorded traffic
- Dhaka-density row: at the full recorded counts the corridor overshoots (200.3 vehicles/km on INT, 597 vehicles/h through); the counts are scaled to x0.78 to match the density, and the density reached does not rise smoothly with the scale (see tried scales)
- Dhaka-density row: 63 % of the time the ambulance stood in the slower alert runs is a circular wait created by the make-way rule (an alerted vehicle may not make its own lane change until the ambulance passes, and the ambulance cannot pass); the alert's slowdown there is therefore mostly a simulation artefact (evidence/ambulance_rq2/inspect/dhaka/SLOWDOWN.md)
- Dhaka-density row: the route's signal programmes are unchanged by the cut

### Evidence

```
9f51b2ada1a136a99afcd530ec50fa11dedd9196c5c6d96b7f4441d55bddfd87  evidence/ambulance_rq2/density_gap.json
df4447502470a618163239f332e29e0d14ed6edd353506f36f84753328b5ecbe  evidence/ambulance_rq2/dhaka_density/calibration.json
9a0cc5e7571f7eb7f5d7acbd8f885c92c3ff2b5321889192bfda9eb329a4481c  evidence/ambulance_rq2/dhaka_density/density.json
926ad019d73a1efeb8143210d95bbcfca4d30d3388198521f78487fdab2e2f89  evidence/ambulance_rq2/dhaka_density/density_x0.4.json
0bec27da31eba464089462e7cfb3ae464f090761b2292bf63255af0e0e6d768e  evidence/ambulance_rq2/dhaka_density/density_x0.5.json
393363d2ed9df2d1f1b2480ba7bc264e5e1afdfe1662cb8aceff8b5b8252d7d0  evidence/ambulance_rq2/dhaka_density/density_x0.6.json
a3777320db079f13e9f7fc473a240ae90821271a1d33e2ff6321ac5d9da70b75  evidence/ambulance_rq2/dhaka_density/density_x0.7.json
cb8e357785f1235586ce9e267325a264aee071795736d2d0576b14f17b86cce4  evidence/ambulance_rq2/dhaka_density/density_x0.72.json
a7f12cf7572023a613da0815fb58aff6805ae5c3360bb9a8210958e81976c16c  evidence/ambulance_rq2/dhaka_density/density_x0.75.json
1d68bf73ecccf4258a36ea9aad17616ad669817ad8d62025d77fb6f70825ee17  evidence/ambulance_rq2/dhaka_density/density_x0.78.json
d4552a08fc78f7d129b5f27b1caca8ff69656df7f2b2a93f954fb61084ec8068  evidence/ambulance_rq2/dhaka_density/density_x0.8.json
f1e874a57dfc9c1111ca6ac0bf00a8f0b9a3c539b6feac32fb2f4e08d30db29d  evidence/ambulance_rq2/dhaka_density/match.json
63ba977887c034c556f181e588e4643934795f750bbe1d41272b33d0df92646c  evidence/ambulance_rq2/inspect/dhaka/SLOWDOWN.md
43bddeb297fb901ba85a052be925a877af683a1e2478f0911205c8db20c3541a  evidence/ambulance_rq2/inspect/dhaka/slowdown.json
22af876f5b714aa3ecf7ff90b910b5aa34c0e7fc84be0c1bba710f1c55dc3a46  evidence/ambulance_rq2/inspect/slow_alert_run.md
22803d04e03f09dc0393d2de9f375cc12d40a10499cce9272192a56d68928797  results/emergency/dhaka/rq2/figures/rq2_density.png
7c26d43d0ccce459262e89e95bf1ba5492b85c6cebcc41b4ae6fb2a38286b894  results/emergency/dhaka/rq2/figures/rq2_share.png
47a0babf11b4bbc0315f79355270e95a323e7b3644a7bf112f99fc12d410f5ad  results/emergency/dhaka/rq2/figures/rq2_why.png
5f3f9b4c84ea331ce265785406bb677c81ee2d14b153294ebb5043ce17cbaf61  results/emergency/dhaka/rq2/ladder.json
921174ec73d9ad75ff8e969e017344711e7854e5e80c1d3cd7d794e5264f57bf  results/emergency/dhaka/rq2/rl/train_dhaka_density_x0.78.json
061f1a0c68a4cab60b2f26c7bef2cde20b810ddc7612ca00b42b884574074a67  results/emergency/dhaka/rq2/rl/train_x0.5.json
840628644ce8e5e832e56259a0c3ff1f964426bcde37d8a5857c91761d7eb355  results/emergency/dhaka/rq2/rl/train_x1.json
1391e9349983245b61b2835c0ac0cc330a9b1f8db989566835fe97e22617834a  results/emergency/dhaka/rq2/rl/train_x2.json
aa46fc918c2e0a31f91cc925cfc0e78440c63f5cbc5bb9c030e91363ee122fbc  results/emergency/dhaka/rq2/rl/train_x3.json
6054cd18cdfcfdfdcf5d3b5f3aceef60fff7bcb2dea61a129298db141fecd4c6  results/emergency/dhaka/rq2/rl/train_x4.json
ebab3a776f752a708102cfe3db7d7ad47fb1a7fa65f36a3e04060bc6ea1bf5d5  results/emergency/dhaka/rq2/summary.json
f2feb266b096e9ddf55c08dec54c33c95743ddd80d52bcef9d635296fbd3144c  results/emergency/dhaka/rq2/summary.md
```
