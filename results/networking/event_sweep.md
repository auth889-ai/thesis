# V2X advisory from OUR event (NLP report / forecast) — Eclipse MOSAIC 25.2, Dhaka R1

Hazard rectangle = bounding box of the event edges; the event is physically real in SUMO (variableSpeedSign). Same official WeatherWarningApp/NavigationModule chain as the penetration sweep; only WHERE/WHEN the hazard is comes from us.

| source | p | seed | wall_s | registered | equipped | senders | receivers | delivery_ratio_veh | route_switches | switch_fraction_of_equipped | finished.n | finished.duration_mean_s | finished.duration_p95_s | finished.timeLoss_mean_s | finished_equipped.duration_mean_s | finished_unequipped.duration_mean_s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nlp_event | 0.25 | 11 | 60 | 2564 | 628 | 111 | 628 | 1 | 170 | 0.271 | 1045 | 391 | 664 | 161 | 391 | 390 |
| nlp_event | 0 | 11 | 25 | 2555 | 0 | 0 | 0 |  | 0 |  | 1022 | 387 | 644 | 158 |  | 387 |
| nlp_event | 1 | 11 | 953 | 2651 | 2651 | 427 | 2648 | 0.999 | 818 | 0.309 | 1027 | 384 | 621 | 156 | 384 |  |
| predicted | 0.25 | 11 | 368 | 2619 | 642 | 504 | 642 | 1 | 546 | 0.85 | 903 | 416 | 658 | 206 | 400 | 421 |

* NLP: "Bus and CNG collision at Karwan Bazar signal, road blocked" -> incident @ Karwan Bazar
* predicted: top-8 traveltime/free-flow edges of results/routing/static_s11_h7200/edgedata.xml at t=200s

Regenerate: `python pipeline/networking/event_sweep.py --source nlp_event --p <P> --seed <S>`; `--aggregate` rebuilds this table.
