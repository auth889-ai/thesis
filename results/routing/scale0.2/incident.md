# NLP incident scenario — Dhaka R1, 3 paired seeds

Event: "Bus and CNG collision at Karwan Bazar signal, road blocked" → label `incident` (p=0.9975), place Karwan Bazar, 8 edges, factor ×10.0. Incident at t=900s for 1800s, speed limit 1.5 m/s; report delay 120s; compliance 0.3; demand scale 0.2; horizon 5400s.

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| uninformed | 893.1 ± 9.6 | 825.6 ± 14.4 | 1943.0 ± 106.0 | 1264.1 ± 34.2 | 3199.0 ± 42.6 | 695.7 ± 21.6 | 89.7 ± 12.4 |
| reactive | 897.7 ± 18.8 | 872.2 ± 12.8 | 1917.3 ± 22.5 | 1198.2 ± 38.8 | 3095.7 ± 104.1 | 611.3 ± 31.0 | 30.0 ± 13.6 |
| nlp_informed | 954.2 ± 39.6 | 939.0 ± 34.1 | 2340.7 ± 180.7 | 1415.1 ± 114.1 | 2951.3 ± 56.0 | 706.3 ± 78.8 | 81.3 ± 22.9 |
| reactive_plus_nlp | 939.2 ± 15.9 | 904.3 ± 26.1 | 2118.3 ± 119.7 | 1265.4 ± 27.7 | 3018.3 ± 79.2 | 722.0 ± 48.4 | 86.7 ± 32.8 |
| reactive_predeparture | 880.8 ± 25.7 | 849.3 ± 23.3 | 1802.3 ± 83.2 | 1203.0 ± 48.8 | 3110.7 ± 73.1 | 623.3 ± 31.5 | 15.0 ± 7.1 |
| nlp_predeparture | 903.4 ± 14.2 | 848.6 ± 15.0 | 1858.0 ± 51.2 | 1222.6 ± 26.8 | 3203.7 ± 28.4 | 629.0 ± 18.2 | 69.7 ± 7.3 |

## Paired % change vs uninformed (mean over seeds [bootstrap 95 % CI]; sign count = seeds improved)

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| reactive | +0.5 % [-0.9, +1.9] 1/3 | +5.7 % [+1.1, +8.8] 0/3 | -1.0 % [-9.8, +4.7] 1/3 | -5.2 % [-8.5, -2.1] 3/3 | -3.2 % [-7.5, +3.2] 1/3 | -12.1 % [-18.6, -8.1] 3/3 | -65.5 % [-83.0, -43.7] 3/3 |
| nlp_informed | +6.8 % [+2.0, +10.1] 0/3 | +13.7 % [+9.5, +16.7] 0/3 | +20.4 % [+14.7, +23.5] 0/3 | +11.8 % [+3.0, +17.4] 0/3 | -7.7 % [-8.2, -6.8] 0/3 | +1.3 % [-6.8, +13.1] 2/3 | -5.8 % [-49.1, +26.4] 1/3 |
| reactive_plus_nlp | +5.2 % [+4.2, +5.9] 0/3 | +9.5 % [+6.9, +11.1] 0/3 | +9.3 % [+0.3, +20.8] 0/3 | +0.1 % [-0.9, +1.0] 1/3 | -5.7 % [-7.4, -4.5] 0/3 | +3.8 % [-5.0, +9.6] 1/3 | -4.8 % [-44.7, +37.9] 2/3 |
| reactive_predeparture | -1.4 % [-3.6, +3.0] 2/3 | +2.9 % [+0.2, +6.0] 0/3 | -7.0 % [-13.4, +0.8] 2/3 | -4.8 % [-8.4, +0.7] 2/3 | -2.8 % [-4.2, -1.9] 0/3 | -10.4 % [-13.4, -5.8] 3/3 | -84.0 % [-88.2, -76.4] 3/3 |
| nlp_predeparture | +1.2 % [-2.0, +3.7] 1/3 | +2.8 % [-1.3, +6.6] 1/3 | -4.0 % [-14.5, +1.4] 1/3 | -3.2 % [-8.4, +0.3] 2/3 | +0.2 % [-1.7, +2.5] 1/3 | -9.5 % [-14.8, -6.6] 3/3 | -20.7 % [-39.6, -8.0] 3/3 |

`affected_*` = vehicles whose initial route ran through an incident edge. `arrived`: higher is better; all other columns: lower is better.
Regenerate: `python pipeline/routing/incident_scenario.py --seeds 11,12,13`.
