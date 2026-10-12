# Forecast routing (RQ2): every borrowed piece, in one table (2026-10-12)

Drawn from `third_party/SOURCES.md` (the row numbers there are given so the full record can be read); nothing here is new. "Reuse"
says what we took: code run or imported unchanged, data read, a tool called, or only a paper's design. The loop itself
(`core/simulation/closed_loop`, `core/simulation/twin/runner.py`, `core/simulation/routing/*`, `core/networking/v2x/channel.py`,
`core/networking/v2x/state_correction.py`) is our code.

| Piece | Kind | Link | Version / pin | Licence | Reuse in forecast routing | SOURCES row |
|---|---|---|---|---|---|---|
| Eclipse SUMO + TraCI + sumolib | code, run unchanged | https://github.com/eclipse-sumo/sumo | tag `v1_27_1`, commit `7717f237…` (pip `eclipse-sumo==1.27.1`) | EPL-2.0 | the simulator; `netconvert` built the LA twin network from OSM; `--load-state` for the fork at 1 200 s; `setRoute` applies an advised route; `tripinfo`, `summary`, `edgeData` outputs | 9, 92, 204 |
| SUMO `tools/randomTrips.py` | tool, run unchanged | same repository, `tools/randomTrips.py` | `v1_27_1` | EPL-2.0 | the SYNTHETIC demand: one draw per seed on the real network, 8x "peak" profile, arterial OD rule (`closed_loop.demand_for_seed`) | 9, 177 |
| SUMO `duarouter` | tool, run unchanged | same repository, `bin/duarouter` | `v1_27_1` | EPL-2.0 | the K = 5 alternative routes per connected car on the forecast weight file (`route_optimizer.duarouter_routes`); we do no path search ourselves | 9 |
| SUMO `tools/visualization/plot_net_dump.py`, `plotXMLAttributes.py` | tool, run unchanged | same repository | `v1_27_1` | EPL-2.0 | addition B: the edge-speed map and the time plots of a finished run (`scripts/routing/plot_run.py`) | 274 |
| OpenStreetMap (Overpass API) | data | https://overpass-api.de | `osm_base` date in `evidence/cities/la_c4_central_wide/build.json` | ODbL 1.0, © OpenStreetMap contributors | the road network of central Los Angeles, box 34.08–34.16 N, 118.342–118.222 W (`data/cities/la_c4_central_wide/sumo/la_c4_central_wide.net.xml`) | 10 |
| METR-LA (207 loop detectors, 5-minute speeds, 2012-03-01 to 2012-06-27) | data | released with DCRNN, https://github.com/liyaguang/DCRNN (data), through the BasicTS pre-processing | `data/forecasting/cities/metr_la.npz`, dataset hash `857a98d0ec47b353` | released with DCRNN's code (MIT repository); the data file's own terms as released by the authors | the forecast's input (12 bins before `as_of`), the "real future" replayed as lane speed caps on the mapped edges in every arm, the reference for the forecast error shown in the demo | 11, 148 |
| DCRNN `graph_sensor_locations.csv` | data | https://github.com/liyaguang/DCRNN | commit `602afd9d…` | MIT | the detector coordinates that place the LA box and map each sensor to a twin edge (`results/routing/coverage_rescue/la_c4_central_wide/sensor_to_edge_207.json`, 83 GOOD of 207) | 11 |
| Graph WaveNet (Wu, Pan, Long, Jiang, Zhang, IJCAI 2019) as implemented in BasicTS | code (model definition and training harness), imported unchanged | https://github.com/GestaltCogTeam/BasicTS (legacy fair-comparison branch) | commit `4c3e2d37…` (`~/.dhakaflow/upstream/BasicTS_legacy`) | Apache-2.0 | the forecaster: trained by us with BasicTS's own config on METR-LA (held-out MAE 2.71 mph at +15 min, `results/forecasting/verify_GWNet_METR-LA_207.json`); checkpoint `548e399bd53c…` loaded by `core/ml/forecasting/service.py` and run fresh every 300 s; BasicTS's masked metrics for RQ1 | 148, 217 |
| 5GAA P-190033, "V2X Functional and Performance Test Report" | paper / report (values cited) | https://5gaa.org/content/uploads/2018/11/5GAA_P-190033_V2X-Functional-and-Performance-Test-Report_final-1.pdf | PDF sha256 `d4f79c7e…` | industry report; figures cited, nothing copied | the `its-g5` and `c-v2x` link profiles registered for the routing loop: latency 16.2 / 14 ms, delivery 0.90 (range does not apply to the server ↔ car channel) | 166 |
| ETSI EN 302 637-2 (CAM), EN 302 637-3 (DENM) | standard (values cited) | etsi.org/deliver | V1.4.1 / V1.3.1 (2019-04) | ETSI standards | message lifetime 600 s in the registered profiles | 167 |
| Eckermann, Gorczak, Wietfeld, "tinyLTE", IEEE VTC-Spring 2018 | paper (value cited) | arXiv:1802.09262 | — | arXiv | the `4g` profile's latency: 37.5 ms one way, two legs = 75 ms | 168 |
| Xu, Li, Zhao, Zhang, Wang, "DSRC versus 4G-LTE for Connected Vehicle Applications", J. Adv. Transportation 2017 | paper (value cited) | doi:10.1155/2017/2750452 | Wiley PDF sha256 `652acd52…` | CC BY | the `4g` profile's delivery ratio 0.96 (loss 4 %) | 169 |
| BPR volume-delay function (Bureau of Public Roads, 1964) | published formula | Traffic Assignment Manual, U.S. Dept. of Commerce, 1964 | — | public domain (U.S. government work) | the optimizer's load penalty, α = 0.15, β = 4 (`routing_config.json`), the marginal-cost form in `network_assignment.py` | 254 |
| Santamaria, Fazio, Raimondo, Tropea, De Rango, IEEE TVT 68(5) 2019 ("PRE-VE") | paper design, comparison only | doi:10.1109/TVT.2019.2905753 | — | — (no code released) | design lineage: predictive, congestion-aware rerouting over a vehicular link in Veins/SUMO; ours differs in forecaster, decision rules and link; nothing copied | 260 |
| Chan, Kuncheria, Macfarlane, arXiv:2207.12580 (2022) | paper design | https://arxiv.org/abs/2207.12580 | — | — (their simulator Mobiliti) | addition A: the penetration-rate sweep 0-100 % → our 10/30/50/70/100 % on one seed (`scripts/routing/penetration_sweep.py`) | 273 |
| Eclipse MOSAIC (visualiser convention) | display convention only | https://github.com/eclipse-mosaic/mosaic | documentation read 2026-10-12 | EPL-2.0 | the two-window demo's message lines (red sent / green received) and the recoloured rerouted car; no code read or run for this | 266 |
| Veins (Qtenv message animation) | display convention only; the simulator itself is run elsewhere as the thesis's second view | https://github.com/sommer/veins | `veins-5.3.1` | GPL-2.0-or-later | the same convention; never copied | 195, 267 |
| Kinchen, Bai, Malikopoulos, "Predictive Rerouting of Connected and Automated Vehicles Using Traffic and Charging Demand Forecasts", arXiv:2610.10532 (2026) | paper, read 2026-10-12 for comparison | https://arxiv.org/abs/2610.10532 | v1, 7 Oct 2026 | — (no code, data or licence published) | nothing reused; see the comparison note below | — (not in SOURCES: nothing borrowed) |

Not used by the routing runs reported: the channel's `mosaic` latency profile (latencies sampled from a reproduced MOSAIC run) exists in
`core/networking/v2x/channel.py` but every routing run here uses `ideal`, `its-g5`, `c-v2x` or `4g`.

## Comparison note: arXiv 2610.10532 (read-only, 2026-10-12)

Kinchen, Bai and Malikopoulos forecast edge-level conditions with a DCRNN over a graph built from SUMO's own connections (history 5 steps
of 60 s, a 120 s nominal horizon; inputs: travel-time index, CO2, speed, EV charging state), on a "NYC-6" SUMO map (638 edges, 254
junctions, under 600 trips per scenario, demand source not stated), with CAV penetration 5-45 %. Routing: up to K = 3 loop-free
alternatives; edge cost 0.95·TTI' + 3.1·CO2' + 0.90·length' + 2.5·charging risk; a change is accepted only if the destination stays
reachable, the cost falls, and cooldown (4 s), a three-changes limit and duplicate checks pass. No communication path is modelled: TraCI
hands observations to the forecaster and applies the decision directly (V2X appears only as a benchmark with a 180 s warning). Results
(Table II, summed over scenarios): DCRNN 41 reroutes, average TTI 3.520 against 3.570 (K-shortest), 3.591 (predictive density), 3.582
(V2X); about 1.8 % lower TTI than no rerouting, with the no-reroute reference lower in total CO2 and distance. **No code, dataset or
licence is published**, so there is nothing we could reuse unchanged; the paper is a design comparison only. Differences from ours: a
120 s horizon from simulation-derived features versus our 15-minute horizon from 207 real detectors; no link model versus our
latency/loss/lifetime channel with per-message delivery; a weighted multi-objective cost versus our travel-time saving with a 60 s / 5 %
threshold, cooldown, share and BPR capacity gates; a few hundred vehicles versus 12 480 per seed.
