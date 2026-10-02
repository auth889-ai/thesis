# Signature features: what makes the app more than a forecast

Written 2026-10-03 from a search of what Google Maps, Waze, TomTom, city digital twins and the 2025–2026 traffic-LLM
papers ship, filtered to what is software-only, real-data, and buildable on the stack already here (SUMO twin, Amazon
Location, Bedrock, BasicTS models, MapLibre). Ranked by surprise × feasibility. Each names its precedent and the
open-source piece that does the heavy lifting.

| # | Feature | What the person sees | Precedent | Built from | Phase |
|---|---|---|---|---|---|
| S1 | **Your phone is the sensor** | A city with zero sensors gets a live speed map from its own users: the browser shares location, the trace is map-matched to roads, segment speeds appear within a minute, with how many probes each road has | CitySpeed (crowdsensing platform), TomTom's index built from anonymised GPS | Geolocation API → Fast Map Matching (Apache-2.0) or Valhalla Meili → Redis Streams → the live layer | Q6 |
| S2 | **The living twin** | The forecast becomes thousands of vehicles moving on a 3D map; scrub forward and watch the jam form on the roads the model flagged | DIDYMOS-XR SUMO-in-browser twin; MapLibre + Three.js at 100 k vehicles; Amsterdam/St Louis CesiumJS twins | SUMO FCD output → deck.gl TripsLayer on MapLibre (MIT) | P12 |
| S3 | **"Why will it be slow?"** | Tap a road's forecast and get a sentence: "Mirpur Road slows at 17:40 because Farmgate upstream is already congested and that pattern reached here in 20 minutes on 14 of the last 20 days", with the influential roads highlighted | Verbal Explanations of STGNNs (open source), STExplainer, Information Sciences 2023 on GNN explainability for traffic | the subgraph explainer on the trained GWNet/STAEformer; Bedrock turns the subgraph into text | P2+ |
| S4 | **Ask the city** | Natural-language questions over the data, answered with a chart and a reason: "Which roads got worse this month?", "When does the airport road clear on Fridays?" | TrafficGPT, Google's Ask Maps (2026), UrbanGPT | Bedrock agent with typed tools over the datasets, forecasts and outcomes; Vega-Lite charts; already the MCP tool pattern | exists, re-pointed |
| S5 | **What-if city planner** | Close a road, add a flyover, change a signal plan, add rain: the twin re-runs and shows delay, queue and CO2 before and after | DiTAT (SUMO 2025), Geneva twin, Snap4City | SUMO paired same-state runs (exists) + HBEFA emission output + the forecaster as demand | P12 |
| S6 | **CO2 and fuel meter** | Every route and every signal plan shows grams of CO2 and litres of fuel; eco-route option; "this plan saves 1.2 t/year" | SUMO HBEFA models; emission-aware bus routing (Osnabrück 2026); eco-driving at signals | SUMO `--emission-output`, HBEFA v3/v4 classes, per-route aggregation | Q4 |
| S7 | **Herding guard** | The app knows it is not the only one giving advice: when many users would be sent the same way it spreads them, and shows the jam it avoided creating | Nature Communications 2026, "traffic concentration effects of urban navigation services"; popularity-based alternative routing | the twin with 20 % compliance (exists) + MATSim population run; alternative-route ranking by load | Q9 |
| S8 | **World congestion pulse** | Thirty cities live on a hex grid: congestion level, speed, travel time per km, ranked, with history, like the TomTom index but open and reproducible | TomTom Traffic Index 2026 methodology (hex grid, 20 % / 80 % trip clusters) | Amazon Location Routes sampled on an H3 grid per city; nightly index; MapLibre choropleth | P9+ |
| S9 | **Open regime leaderboard** | Anyone uploads predictions for a benchmark and gets scored on Protocol A and Protocol B; the public table lists every model with its onset lead and coverage | Papers-with-Code leaderboards (aggregate only); LargeST benchmark | the evaluation module (exists) behind an upload endpoint; signed result cards | P2 |
| S10 | **Time machine** | Scrub any past day: forecast vs what happened, per road, with the regime bands shaded; find the day the model was most wrong and why | Google Maps "typical traffic" slider; our forecast-map slider (exists) | the outcomes table + checkpoint inference per step (exists) | P8 |
| S11 | **Event-aware forecasts** | Rain, public holidays, Eid, a cricket final: the forecast takes them as inputs and says which one is moving the number | Google's event-based signals (2026); Chronos-2 covariates | Chronos-2 with covariates (Open-Meteo, Nager.Date holidays, a city events file); attribution per covariate | P9 |
| S12 | **Reliability index per route** | "Typical 24 min; add 11 min to be on time 95 % of days": the planning-time index every transport agency reports, per route, from our own intervals | FHWA travel-time reliability measures; Namma Commute | conformal p95 (P8) → buffer index and planning-time index | P8 |
| S13 | **Incident radar** | Anomaly score per road from sensors and public cameras; "unreported incident likely at 08:12, severity moderate"; measured detection delay | IncidentNet (Apache-2.0); early anomaly detection 2025 | IncidentNet on the twin and on 511 camera feeds; RT-DETR counts (exists) | Q3 |
| S14 | **Signal lab with reasons** | Pick a junction set, compare fixed-time, max-pressure, MAPPO, Advanced-MP; LLMLight explains each cycle's decision in a sentence | LLMLight (KDD 2025), LibSignal | existing control arms + Advanced-XLight (GPL, separate process) + Bedrock as the LLM agent | Q4, Q5 |
| S15 | **Model health** | Per city, per regime: coverage this week, drift since training, when the model was last retrained, whether persistence is currently better | production MLOps (Michelangelo-style monitoring) | the outcomes table, weekly job, Evidently (Apache-2.0) report | P12 |
| S16 | **Equity map** | Which neighbourhoods lose the most minutes to congestion, and whether the advice helps them or only the centre | Access Across America, TransitCenter equity tools | H3 aggregation of forecast delay × population (WorldPop, open) | later |

## What this does to the project's story

The forecaster is the engine. The features above are what the engine makes possible: a city sensed by its own users,
a twin you can watch and poke, explanations instead of numbers, advice that knows it is not alone, a world index
anyone can reproduce, and a public benchmark nobody else offers. Every one of them reads real data or a real run.

## Sources

TomTom index methodology: https://www.tomtom.com/traffic-index/about/ · Waze 2026 features: https://techcrunch.com/2026/07/13/waze-adds-new-ai-powered-features-and-customization-updates/ ·
Google Maps 2026 predictive and Ask Maps: https://techcrunch.com/2026/03/12/google-maps-is-getting-an-ai-ask-maps-feature-and-upgraded-immersive-navigation/ ·
DIDYMOS-XR web twin: https://didymos-xr.eu/bringing-traffic-to-life-a-web-based-traffic-simulation-for-smart-city-digital-twin/ ·
100 k vehicles in MapLibre: https://github.com/webtrackerxy/3d-city-million-cars · St Louis twin: https://github.com/ihelfrich/stl-digital-twin ·
Verbal explanations of STGNNs: https://github.com/RiccardoSpolaor/Verbal-Explanations-of-Spatio-Temporal-Graph-Neural-Networks-for-Traffic-Forecasting ·
GNN explainability for traffic: https://www.sciencedirect.com/science/article/pii/S0020025523009052 · TrafficGPT: https://github.com/lijlansg/TrafficGPT ·
SUMO emissions: https://sumo.dlr.de/docs/Topics/Environmental_Issues.html · navigation herding (Nature Comms 2026): https://www.nature.com/articles/s41467-026-75254-8 ·
popularity-based alternative routing: https://arxiv.org/abs/2406.05388 · IncidentNet: https://github.com/MPSLab-ASU/IncidentNet · LLMLight: https://github.com/usail-hkust/LLMTSCS ·
crowdsensed speeds (CitySpeed): https://www.researchgate.net/publication/330816752 · Access Across America: https://access.umn.edu/ao-research/aaa
