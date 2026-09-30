    
   IFE OS / Agent / Approval / Audit
- OpenMuse (tahodev): github.com/tahodev/openmuse GitHub
- CopilotKit OpenMuse: github.com/CopilotKit/openmuse
- OpenAI Agents Python: github.com/openai/openai-agents-python
- Human-in-the-loop docs: openai-agents-python human-in-the-loop
Traffic Forecasting
- DCRNN: github.com/liyaguang/DCRNN
- Graph WaveNet: github.com/nnzhan/Graph-WaveNet
- STID: github.com/GestaltCogTeam/STID GitHub
- STAEformer: github.com/XDZhelheim/STAEformer
Foundation / Cross-city Models
- OpenCity: github.com/HKUDS/OpenCity GitHub
- UniST: github.com/tsinghua-fib-lab/UniST GitHub
- RAST: github.com/RWLinno/RAST GitHub
Large-scale Benchmark / Dataset
- LargeST: github.com/liuxu77/LargeST
Uncertainty / Conformal Prediction
- MAPIE: github.com/scikit-learn-contrib/MAPIE GitHub
Multimodal Routing
- OpenTripPlanner: github.com/opentripplanner/OpenTripPlanner GitHub
- Valhalla: github.com/valhalla/valhalla
- Valhalla Docker: github.com/nilsnolde/docker-valhalla
Map Matching / Phone Probe Data
- Map Matching: github.com/MapMatching-research/Map-Matching GitHub
SUMO / Digital Twin
- Eclipse SUMO: github.com/eclipse-sumo/sumo GitHub
Traffic Signal Control / RL
- SUMO-RL: github.com/gusongen/sumo-rl
- LibSignal: github.com/sal0-h/LibSignal
- RL Signals / CityFlow: github.com/yizhihongli/RL_signals_CityFlow
- smart-traffic-rl: github.com/taha-elbadaoui/smart-traffic-rl
V2X / Connected Mobility
- Eclipse MOSAIC: github.com/eclipse-mosaic/mosaic
- SUMO V2X research example: github.com/sraddon/SUMO-V2X-Communication-Research-Platooning-and-CIM 
    
    
    
    1. Personal agent / LIFE OS architecture
Start with these first, because they show how a serious agent should work beyond a chatbot.
- tahodev/OpenMuse — exact-action approvals, verifiable hash-chained audit, isolated secrets, durable tasks, safe tool execution. This is probably the single most useful repo for your existing permission + audit architecture. GitHub
  OpenMuse — tahodev
- CopilotKit/OpenMuse — especially useful for the consumer product side: persistent browser, Gmail/Calendar, delegated tasks, visible progress, pause/resume/cancel/retry, approvals, goals, personal context and rich activity UI. GitHub
  OpenMuse — CopilotKit
- OpenAI Agents Python — Human in the Loop examples — study how tool execution pauses for approval, persists state, and resumes safely. Even if you continue using Bedrock, the architecture pattern is useful. GitHub
  Human-in-the-loop agent examples






  2. Traffic forecasting — the research foundation
These are the models you should study and reproduce carefully.
- DCRNN — one of the canonical graph-based traffic forecasting repos. It provides METR-LA/PEMS-BAY preprocessing, train/val/test setup, baselines and reproducible experiments. GitHub
  DCRNN repository
- Graph WaveNet — original PyTorch implementation; very important for adaptive adjacency and temporal convolutions. GitHub
  Graph WaveNet repository
- STID — extremely useful because it is simple but competitive, and it uses BasicTS. It is a good sanity baseline against more complicated GNN/Transformer models. GitHub
  STID repository
- STAEformer — official Transformer traffic-forecasting implementation with METR-LA, PEMS-BAY and several PEMS datasets. GitHub
  STAEformer repository



  3. Foundation / cross-city traffic models
These are especially important for your “new city / Dhaka with little data” story.
- OpenCity — open spatiotemporal foundation model for traffic prediction; includes code, data and model weights and targets zero-shot transfer across urban environments. GitHub
  OpenCity repository
- UniST — supports short-term, long-term, few-shot and zero-shot spatiotemporal prediction. Very relevant to your new-city adaptation idea. GitHub
  UniST repository
- RAST — retrieval-augmented universal spatiotemporal framework for traffic prediction; useful if you later want to explore retrieving similar traffic patterns instead of relying only on one trained model. GitHub
  RAST repository



 4. Large-scale datasets and benchmarking
Use this when you want to prove the project is not a toy.
- LargeST — official NeurIPS 2023 large-scale traffic forecasting benchmark. GitHub
  LargeST repository
This is useful after you have a stable pipeline on METR-LA / PEMS-BAY. Do not begin with the largest dataset; use it after reproducibility is working.
5. Uncertainty and reliable arrival probability
This is one of the strongest additions for your thesis.
- MAPIE — conformal prediction / prediction intervals / risk-control library. It supports time-series uncertainty workflows and is useful for turning “52 min prediction” into something like “45–64 min interval.” GitHub
  MAPIE repository


   7. Map matching and phone probe data
This matters for your “own data” idea.
- MapMatching-research/Map-Matching — implements research-oriented map matching including HMM-based approaches on OpenStreetMap trajectories. GitHub
  Map Matching repository
Study:
phone GPS points
↓
candidate road segments
↓
map matching
↓
road-segment speed
↓
TrafficTwin input

This is how you move away from depending completely on a third-party traffic provider.
8. SUMO digital twin
This remains essential for your thesis because it lets you test whether a decision actually improves traffic outcomes.
Use Eclipse SUMO itself as the core simulator. SUMO documentation explicitly notes that TraCI can control the simulation and that external communication simulators are needed for detailed V2X/network effects. GitHub
Your loop:
forecast
↓
route/signal decision
↓
SUMO
↓
travel time
waiting time
queue
stops
spillback
emissions

This is much better than only drawing moving cars.
9. Traffic signal control and RL
For city control, study these.
- sumo-rl — creates Gymnasium/PettingZoo RL environments around SUMO traffic signals and uses TraCI for state/action control. GitHub
  SUMO-RL repository
- LibSignal — useful benchmark-style library covering fixed-time, max-pressure, PressLight, FRAP, CoLight, PPO and other controllers. GitHub
  LibSignal repository
- RL Signals / CityFlow collection — useful overview of major traffic-signal-control methods including CoLight, PressLight, FRAP, MetaLight, MPLight and CityFlow. GitHub
  Traffic signal control repository
- smart-traffic-rl — especially valuable because it shows a good research attitude: real Cologne network, real demand, fixed-time versus max-pressure versus learned methods, with negative RL results honestly retained. GitHub
  smart-traffic-rl repository
This last one is worth studying carefully because your thesis should also preserve failures rather than forcing a “deep learning always wins” conclusion.
10. V2X / networking
For the networking side, the most important one is:
- Eclipse MOSAIC — multi-domain connected-mobility simulator coupling SUMO with communication simulation including OMNeT++, ns-3 and cellular/network components. GitHub
  Eclipse MOSAIC repository
This is the correct reference architecture when your research question is:
vehicle observation
↓
V2X communication
↓
latency / packet loss
↓
traffic state estimate
↓
routing / control decision
↓
traffic outcome

- SUMO V2X dissertation example — smaller and easier to read; uses SUMO + TraCI for platooning and centralized intersection management. GitHub
  SUMO V2X example repository
Use this one for learning code flow; use MOSAIC for research-grade experiments.
Resources:
- Pixy Devpost: Pixy — “Literally the Smallest 0.5B Param Functional LLM ever built”
- Pixy GitHub: bitanath/pixy
- Project BlackBox Devpost: Project BlackBox — Autonomous data incident repair
- Project BlackBox GitHub: alejandro-publius/blackbox-datahub