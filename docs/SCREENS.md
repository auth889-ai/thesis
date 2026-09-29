# The fourteen screens and the phase that makes each real

Reference: the LIFE OS screen set of 2026-09-30 (kept in the coffee palette). A screen is built only when its data is real.

| # | Screen | What it needs | Phase |
|---|---|---|---|
| 1 | Onboarding / sign up (Google, Microsoft, e-mail) | accounts: Cognito with federated sign-in | block D (P17–P20), moved earlier if asked |
| 2 | Profile setup (name, zone, home, mobility profile, target) | the Person contract | P0 done; mobility profile shown in P10 |
| 3 | Integrations (calendar, mail, maps, tasks, weather) | connectors with consent | P15 (Google), P5 (Open-Meteo), P4 (maps) |
| 4 | Home / Today: "Can today work? YES", commitments, at risk, free time, travel, timeline, live traffic | the day optimiser and AccessTwin | P3 first answer; P10 real probabilities |
| 5 | Plan: day timeline with travel, route and travel details, alternatives | real travel edges | P4 |
| 6 | Agent chat: "Make tomorrow work", plan summary with steps | the agent over the compiler and the optimiser | P1 now (commitment line), P13 |
| 7 | Explore: reachable within N minutes, jobs, hospitals, schools, what-if | R5 opportunity reachability | P26, P27 |
| 8 | Activity / monitor: traffic delay, plan updated, weather, calendar change | the event bus | P16–P17 |
| 9 | Research lab: experiments, datasets, models, model performance, simulation preview | the run records | P6–P7, P21 |
| 10 | Network and edge lab: latency, loss, bandwidth sweeps; twin freshness, MAE, plan success | ns-3 / MOSAIC and edge runs | P23–P24 |
| 11 | City / population simulation: agents, scenario, results | MATSim | P22 |
| 12 | Settings: profile, preferences, privacy, integrations, data | P0 + P15 | partly done |
| 13 | Help and documentation | the docs | P28 |
| 14 | Mobile | the same API | P28 |
