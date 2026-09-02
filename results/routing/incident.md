# NLP incident scenario — Dhaka R1, 3 paired seeds

Event: "Bus and CNG collision at Karwan Bazar signal, road blocked" → label `incident` (p=0.9975), place Karwan Bazar, 8 edges, factor ×10.0. Incident at t=900s for 1800s, speed limit 1.5 m/s; report delay 120s; compliance 0.3; demand scale 0.25; horizon 5400s.

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| uninformed | 898.9 ± 43.9 | 539.9 ± 27.1 | 1253.7 ± 112.2 | 988.6 ± 50.5 | 5644.3 ± 107.1 | 350.0 ± 100.0 | 80.0 ± 40.2 |
| reactive | 1069.5 ± 86.9 | 670.1 ± 64.3 | 1510.3 ± 288.3 | 877.6 ± 102.1 | 5032.3 ± 268.8 | 722.7 ± 154.2 | 252.7 ± 67.1 |
| nlp_informed | 1042.3 ± 102.8 | 650.5 ± 75.1 | 1296.7 ± 212.0 | 876.1 ± 50.8 | 4995.0 ± 264.3 | 784.0 ± 171.1 | 226.3 ± 49.3 |
| reactive_plus_nlp | 996.0 ± 71.4 | 611.3 ± 52.3 | 1474.0 ± 179.7 | 922.8 ± 27.0 | 5279.3 ± 223.9 | 592.7 ± 139.2 | 199.7 ± 62.6 |

## Paired % change vs uninformed (mean over seeds [bootstrap 95 % CI]; sign count = seeds improved)

| arm | total_vehicle_hours | mean_travel_time_all | p95_travel_time_s | affected_mean_travel_time_s | arrived | unfinished | teleports |
|---|---|---|---|---|---|---|---|
| reactive | +18.9 % [+11.5, +25.6] 0/3 | +24.0 % [+13.7, +34.9] 0/3 | +20.1 % [-3.5, +35.5] 1/3 | -11.4 % [-22.6, -5.7] 3/3 | -10.9 % [-16.4, -6.8] 0/3 | +112.9 % [+68.1, +148.7] 0/3 | +264.6 % [+131.8, +364.7] 0/3 |
| nlp_informed | +15.7 % [+10.5, +24.1] 0/3 | +20.1 % [+14.2, +31.4] 0/3 | +3.2 % [-13.8, +13.1] 1/3 | -11.3 % [-16.5, -4.9] 3/3 | -11.6 % [-16.0, -9.1] 0/3 | +130.9 % [+100.9, +176.0] 0/3 | +246.9 % [+124.2, +452.9] 0/3 |
| reactive_plus_nlp | +11.4 % [-1.1, +29.1] 1/3 | +13.9 % [-1.0, +34.4] 1/3 | +19.2 % [+1.9, +51.6] 0/3 | -6.4 % [-11.9, +0.9] 2/3 | -6.4 % [-13.0, +1.1] 1/3 | +97.1 % [-13.9, +224.9] 1/3 | +289.5 % [-10.6, +694.1] 1/3 |

`affected_*` = vehicles whose initial route ran through an incident edge. `arrived`: higher is better; all other columns: lower is better.
Regenerate: `python pipeline/routing/incident_scenario.py --seeds 11,12,13`.
