# Q-learning signals at Dhaka density: where the ambulance stood (RQ2c)

On the 5 seeds where the Q-learning signals made the ambulance slower at Dhaka density, it stood 2065 s in all (siren-only on the same seeds: 699 s). 0 of those seconds were within 100 m of a traffic light; the next light on its route was green for it in 1962 s, red in 0 s, and there was no light left ahead in 103 s. The queues it stood in were short (median 2 vehicles to the head) and their heads were not at a light; many ended at a vehicle waiting to change lane. So the lights did not hold the ambulance directly. The Q-learning controllers change when traffic is released around the route, which may load the junctions where it stood, but these logs do not show that path; the cause of the slowdown is not established.

| Run | Travel (s) | Stood (s) | By the light ahead | Where (most seconds) |
|---|---|---|---|---|
| no_alert_s14 | 299.0 | 28 | {'no light within 100 m ahead': 28} | [('240107302#5', 11), (':264894192_0', 6)] |
| rl_signals_s14 | 758.0 | 545 | {'no light within 100 m ahead': 545} | [('240107302#5', 545)] |
| no_alert_s18 | 608.0 | 384 | {'no light within 100 m ahead': 384} | [('240107302#5', 201), ('691209729#14', 183)] |
| rl_signals_s18 | 972.0 | 746 | {'no light within 100 m ahead': 746} | [('240107302#5', 431), (':8779042937_0', 315)] |
| no_alert_s19 | 241.0 | 27 | {'in the queue at a red (a Q-learning light)': 24, 'light ahead green (a Q-learning light), still held': 1, 'no light within 100 m ahead': 2} | [('155271803#3', 25), (':2320154999_2', 2)] |
| rl_signals_s19 | 520.0 | 305 | {'no light within 100 m ahead': 305} | [(':8779042937_0', 269), ('565194019#7', 24)] |
| no_alert_s21 | 288.0 | 73 | {'no light within 100 m ahead': 51, 'in the queue at a red (a Q-learning light)': 21, 'light ahead green (a Q-learning light), still held': 1} | [('240107302#5', 51), ('691209729#6', 22)] |
| rl_signals_s21 | 426.0 | 150 | {'no light within 100 m ahead': 150} | [('691209729#14', 91), ('240107302#5', 40)] |
| no_alert_s23 | 401.0 | 187 | {'no light within 100 m ahead': 172, 'in the queue at a red (a Q-learning light)': 14, 'light ahead green (a Q-learning light), still held': 1} | [('240107302#5', 171), ('155271803#3', 15)] |
| rl_signals_s23 | 531.0 | 319 | {'no light within 100 m ahead': 319} | [(':8779042937_0', 275), (':318321939_3', 44)] |

Queue heads under Q-learning (seeds 14, 18, 19, 23): {"queue head at no light": 1245, "queue head at no light, waiting to change lane": 644, "no stopped vehicle ahead": 26}

The logged re-runs give the same travel times as the original runs; the logs are in this folder (`*_rq2c.json`, `*_rq2c_deep.json`).
