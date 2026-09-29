# Resources: packages, APIs, repositories, datasets, models, and what they cost

Recorded 2026-09-30 against the plan in `PHASES.md`. Budget on that date: AWS credits about $331 estimated remaining, applicable
across AWS services (two Amazon Devices hackathon credits of $150 each, valid to 2028-08-31; a $20 EC2 credit and a $2.69 Lambda credit
to 2027-06-17; about $9 of a Vercel-series credit that expires 2026-12-31); 2 TB Google Drive; Google Colab for GPU notebooks. Prices below are list prices to check
before use; every paid call is logged so the bill is traceable.

## Packages (pip / npm), by phase

| Phase | Packages | Licence | Cost |
|---|---|---|---|
| P0 foundation | pydantic, fastapi, sqlalchemy, alembic, pytest | MIT/BSD/Apache | free |
| P1 compiler | spacy (+ `en_core_web_sm`), dateparser, python-dateutil, rapidfuzz; Bedrock through boto3 | MIT/BSD/Apache | Bedrock: Claude Haiku 4.5 about $1 per million input tokens, $5 per million output; one goal costs well under a cent |
| P2 Life Twin | networkx, sqlalchemy | BSD | free |
| P3 optimiser | ortools (CP-SAT) | Apache-2.0 | free |
| P4 routing | pyvalhalla (wheels), OpenTripPlanner as a Java service, r5py later, gtfs-kit | MIT / LGPL / MIT+GPL | free; self-hosted on the EC2 credit or locally |
| P5 weather | open-meteo client | MIT; API free for non-commercial | free |
| P6 baselines | numpy, pandas, scikit-learn, xgboost | BSD/Apache | free |
| P7 deep learning | torch, torch-geometric, BasicTS harness | BSD/MIT/Apache | GPU time: Colab first; EC2 g5.xlarge about $1.0/h on demand, less on spot |
| P8 cross-city | UniST, OpenCity (released weights) | no licence / MIT | GPU time as above |
| P9 uncertainty | mapie | BSD-3 | free |
| P10 AccessTwin | numpy, scipy, networkx | BSD | free |
| P11–P12 personal ML, risk | xgboost, lightgbm, scikit-learn | Apache/MIT/BSD | free |
| P13–P14 agent | our orchestrator on Bedrock; OpenAI Agents SDK and OpenMuse as patterns | MIT (patterns) | Bedrock as P1 |
| P15 connectors | Composio (MIT) or Google APIs directly | MIT | free tiers; Google OAuth needs a Google Cloud project (consent screen only, no compute) |
| P17–P20 systems | redis, celery or rq, opentelemetry-api/sdk; ray and bentoml later | BSD/Apache | free locally; a small EC2 for Redis |
| P21–P23 simulation, networking | eclipse-sumo, traci, sumolib, sumo-rl; MATSim (Java); ns-3, Eclipse MOSAIC | EPL/MIT/GPL | CPU time only |
| P24 edge | onnxruntime, executorch | MIT/BSD | free |
| P25 federated | flwr | Apache-2.0 | CPU/GPU time |
| P26 opportunity | r5py on Conveyal R5 (pinned) | MIT+GPL | free |
| P28 web | react, typescript, tailwindcss, @tanstack/react-query, react-hook-form, zod, maplibre-gl, recharts, date-fns | MIT | free |

## APIs and data services

| Need | Service | Cost | Note |
|---|---|---|---|
| Roads and live traffic where covered | Amazon Location Service, Routes (HERE data) | about $0.50 per 1 000 route calculations; free tier for the first months of an account | already in; the only paid mobility API; cached per request, never trained on |
| Self-hosted road routing, map matching, isochrones | Valhalla on OSM extracts (Geofabrik) | free | replaces the provider where it has no coverage, and for probes |
| Transit routing | OpenTripPlanner on OSM + GTFS | free | GTFS from the Mobility Database or Transitland Atlas; Dhaka has no official GTFS, so OSM stops and the published metro timetable remain until a feed exists |
| Places and geocoding | OpenStreetMap Nominatim (1 request/s, cached), Overpass; Photon or Pelias self-hosted at scale | free | never hammer the public Nominatim in production |
| Weather | Open-Meteo forecast and historical | free, no key | 16-day forecast, hourly |
| The language model | Amazon Bedrock, Claude Haiku 4.5 (Nova Lite fallback) | pay per token, see above | the only model that plans; its output validates through Pydantic |
| Reminders and alerts | Amazon SNS | about $0.50 per 1 000 SMS in many regions; e-mail and app push near free | already in |
| Voice | Alexa+ through our MCP server | free | the hackathon path |
| Accounts | Amazon Cognito | free to 10 000 monthly users | block D/F |
| Hosting | EC2 (the $20 credit) or a small ECS service; static web on S3 + CloudFront | cents per day | the $150 hackathon credit is kept for the demo month |

## Repositories (studied in their phase, pinned in `upstream/UPSTREAM_PINS.yaml` and `docs/life_os_pins.json`)

Agents: openai/openai-agents-python, langchain-ai/langgraph, tahodev/openmuse, CopilotKit/openmuse. Optimisation: google/or-tools,
TimefoldAI/timefold-solver. Routing: opentripplanner/OpenTripPlanner, valhalla/valhalla, conveyal/r5. Traffic and deep learning:
LibCity/Bigscity-LibCity, GestaltCogTeam/BasicTS, liyaguang/DCRNN, nnzhan/Graph-WaveNet, GestaltCogTeam/STID, XDZhelheim/STAEformer,
HKUDS/OpenCity, tsinghua-fib-lab/UniST, harsharajkumar-273/namma-commute-. Networking: nsnam/ns-3-dev-git, eclipse-mosaic/mosaic.
Federated: flwrlabs/flower. Simulation: eclipse-sumo/sumo, matsim-org/matsim-libs, LucasAlegre/sumo-rl. Systems: ray-project/ray,
BentoML/BentoML, open-telemetry/opentelemetry-python.

## Datasets

| Dataset | Use | Where it lives | Size |
|---|---|---|---|
| METR-LA (207 sensors, Los Angeles) and PEMS-BAY (325, Bay Area) | P6–P7 baselines and deep models, the sensor-rich ground truth | DCRNN release; Google Drive `DhakaFlow-Nexus-Data` | about 1 GB |
| PEMS03/04/07/08 | P7 second benchmark set | STSGCN release | about 2 GB |
| LargeST (San Diego first, then Greater Bay and California) | P7 scale test | LargeST release | up to 20 GB |
| UTD19 (40 cities, loop detectors) | Lab 00 foundation, city-wide density | ETH Research Collection, on Drive | 7 GB |
| Our recorded Dhaka corridor states (5-minute bins, 6 days) | departure bands until probes exist; never a training target for the provider's sake | `results/artifacts/live_dhaka` | small |
| Consented phone probes (P8 of the earlier plan, P4 onward here) | the only city history a model may learn from | our store | grows with users |
| OpenStreetMap extracts (Geofabrik) | networks for Valhalla, OTP, SUMO | downloaded per city | 50 MB to 1 GB per city |
| GTFS feeds (Mobility Database, 6 000+ feeds, 99 countries) | transit routing per city | downloaded per city | small |
| Open-Meteo historical | weather features for P5 and P11 | API | small |
| Commitment sentences (ours, about 300 labelled examples, English and Bangla) | P1 compiler evaluation | `data/lifeos/commitments.jsonl` (to create) | tiny |
| Our outcomes (planned vs actual departures and arrivals) | P11 personal models, the thesis metrics | our store | grows with use |

## Models we train or run

| Model | Role | Trained where | Data |
|---|---|---|---|
| Persistence, historical average | baselines every table reports | CPU | all benchmarks |
| XGBoost on lagged speeds | the strong classical baseline | CPU | all benchmarks |
| Graph WaveNet, then DCRNN, STID, STAEformer | the deep forecasters, one at a time, with the P7 record | Colab first, EC2 g5 spot when Colab times out | METR-LA, PEMS-BAY, then PEMS, LargeST-SD |
| Chronos-Bolt, OpenCity, UniST | zero-shot and few-shot for a city with no history | run only, released weights | Dhaka corridors, held-out cities |
| MAPIE conformal wrappers | intervals over every forecaster and over the route time | CPU | calibration days |
| XGBoost or logistic risk model | READY / AT RISK / BLOCKED | CPU | our outcomes and constraints |
| Personal lateness and duration models | P11 | CPU, later federated with Flower | our outcomes |
| Claude Haiku 4.5 on Bedrock | the compiler's model path and the agent | not trained | prompts validated by Pydantic |

## How the credits are spent (about $331)

| Envelope | Amount | For |
|---|---|---|
| Training campaign, block B | up to $120 | EC2 g5.xlarge spot for GWNet, DCRNN, STID, STAEformer on METR-LA and PEMS-BAY, then PEMS and LargeST-SD; about 30 to 60 GPU hours; Colab remains the first try for every run |
| Model and agent calls | up to $40 | Bedrock (Claude Haiku 4.5) for the compiler and the agent across development, evaluation and the demo; Amazon Location routes |
| Hosting the demo month | up to $60 | one small EC2 or ECS service for the API, Redis, Valhalla and OTP self-hosted; S3 and CloudFront for the web app; SNS; Cognito is free at our size |
| Reserve | the rest, about $110 | a failed training run, the hackathon week, anything the judges ask to see live |

Order of spending: the Vercel-series credit first (expires 2026-12-31), then the Lambda and EC2 credits, then the two
hackathon credits. Every paid call is logged so the bill is traceable; a budget alarm at 80 % of each envelope.
