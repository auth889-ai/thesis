# Third-party licences

Our repository: MIT (LICENSE, © 2026 Jannatul Ferdouse). Licences below were read from each repository's LICENSE
file on 2026-09-29 (`curl` of the raw file; "headline" is its first non-empty line). A repository with **no licence
file** grants no right to copy: read for the method, compare as a benchmark, never copy code.

| Component | Use in this repository | Licence | Compatible with MIT copying? | Attribution |
|---|---|---|---|---|
| tahodev/openmuse | concepts only (approvals, audit checkpoints); no code copied | MIT | yes (not needed: no code) | `REFERENCE_IMPLEMENTATIONS.md`, `references.json` |
| CopilotKit/openmuse | concepts only (task lease, action review) | MIT | yes (no code) | same |
| openai/openai-agents-python | concepts only (needs_approval, rejection message) | MIT | yes (no code) | same |
| GestaltCogTeam/BasicTS | training harness, run unmodified from the external workspace | Apache-2.0 | yes, with NOTICE preserved | `UPSTREAM_PINS.yaml` |
| liyaguang/DCRNN | official model, via BasicTS | MIT | yes | pins |
| nnzhan/Graph-WaveNet | official model, via BasicTS | MIT-style text (headline: copyright Zonghan Wu 2019) | yes | pins |
| GestaltCogTeam/STID | official model, via BasicTS | Apache-2.0 | yes | pins |
| XDZhelheim/STAEformer | reading only; the BasicTS implementation is used | **no licence file** | no | pins |
| HKUDS/OpenCity | zero-shot weights as released | MIT | yes | pins |
| tsinghua-fib-lab/UniST | Phase 5, reading / benchmark only unless a licence appears | **no licence file** | no | pins |
| RWLinno/RAST | Phase 5 | MIT | yes | pins |
| liuxu77/LargeST | Phase 6 datasets and loaders | MIT | yes | pins |
| scikit-learn-contrib/MAPIE | Phase 7 dependency | BSD-3-Clause (headline is the copyright line) | yes | pins |
| MapMatching-research/Map-Matching | Phase 8 reading only | **no licence file** | no | pins |
| valhalla/valhalla | Phase 8/10 infrastructure (routing, Meili) | MIT (COPYING) | yes | pins |
| nilsnolde/docker-valhalla | Phase 10 container | MIT | yes | pins |
| opentripplanner/OpenTripPlanner | Phase 10 infrastructure, run as a service | LGPL-3.0 (GNU licence text) | run as a separate service; do not vendor | pins |
| eclipse-sumo/sumo | simulator, pip dependency, never patched | EPL-2.0 | as a dependency, yes | `MASTER_RESOURCE_INDEX.md` |
| eclipse-mosaic/mosaic | V2X reference runs, dependency | EPL-2.0 | as a dependency, yes | pins |
| LucasAlegre/sumo-rl | Phase 13 dependency | MIT | yes | pins |
| DaRL-LibSignal/LibSignal | Phase 13 reading / benchmark only | **no licence file** at HEAD (earlier pin note: GPL-3.0) | no | pins |
| yizhihongli/RL_signals_CityFlow, taha-elbadaoui/smart-traffic-rl | Phase 13 reading only | **no licence file** | no | pins |
| sraddon/SUMO-V2X-Communication-Research-Platooning-and-CIM | Phase 15 reading | MIT | yes | pins |
| amazon-science/chronos-forecasting | zero-shot corridor forecaster (pip) | Apache-2.0 | yes | `references.json` |
| Unsplash photographs | app imagery | Unsplash License | yes, credited | `frontend/public/photos/ATTRIBUTION.md` |

Datasets (METR-LA, PEMS-BAY, PEMS03/04/07/08, LargeST, UTD19) carry their own terms; each dataset card (Phase 6)
records the source, the licence or terms, and the download date.
