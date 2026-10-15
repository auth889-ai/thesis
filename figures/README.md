# Figures for the forecast-routing talk and report

All figures are PNG, white background, at most 1600 px wide, one font family (DejaVu Sans; DejaVu Sans Mono for the
terminal text). Every number drawn is read from the file named below. The script stops if a number differs from the value
the owner listed.

Regenerate the data figures:

```
python figures/make_figures.py                 # all scripted figures
python figures/make_figures.py fig05           # one figure
```

| Figure | Source | How it was made |
|---|---|---|
| `fig01_sensors_map.png` | Sensor positions: `~/.dhakaflow/upstream/DCRNN/data/sensor_graph/graph_sensor_locations.csv` (DCRNN repo, commit `602afd9d`, file sha256 `eb8ea96e0735…`). Mapped sensors: `results/routing/coverage_rescue/la_c4_central_wide/sensor_to_edge_207.json` (quality `GOOD`, 83 of 207; dashed box = its `bbox`). | `make_figures.py fig01`. Background: OpenStreetMap standard tiles, zoom 12, fetched at run time (© OpenStreetMap contributors). |
| `fig02_gwnet_architecture.png` | `fig/model.png` from the authors' repository github.com/nnzhan/Graph-WaveNet, commit `6b162e80`, MIT licence (file sha256 `2026f040673a7ac5…`). | `make_figures.py fig02`: the figure unchanged, with its source line added below. Not my work; credit Wu et al., IJCAI 2019. |
| `fig03_data_split.png` | Replaces the training curve (see "Missing"). Length of METR-LA from `ForecastService.metr_la_gwnet().values` (34 272 steps, checked), split by `core.ml.forecasting.training.train_eval.splits` (70/10/20 in time order): train 0–23 989, val 23 990–27 416, test 27 417–34 271. | `make_figures.py fig03`. Dates = 1 Mar 2012 + 5 min × index. |
| `fig04_mae_bar.png` | `results/forecasting/verify_GWNet_METR-LA_207.json`: `held_out.{+15,+30,+60}.MAE` and `.persistence_MAE`, `published_GWNet_METR-LA` (checkpoint sha256 `548e399bd53cc54a`). | `make_figures.py fig04`. Checked against 2.71/3.10/3.56, 4.02/5.10/6.80, 2.69/3.07/3.53: all match. |
| `fig05_forecast_vs_real.png` | Checkpoint `results/forecasting/checkpoints/GraphWaveNet/METR-LA_50_12_12/d1ffd3d52d3caacf60ebf59214673f7c/GraphWaveNet_best_val_MAE.pt`, loaded by `core.ml.forecasting.ForecastService.metr_la_gwnet()`; one fresh forward pass. | `make_figures.py fig05`. Moment chosen by a rule, not by outcome: the first weekday 17:30 in the held-out split (`moment_for("peak", 0, …)`, METR-LA index 27570, Mon 4 Jun 2012). Sensors 717458, 717468, 717461 (the same three as the report's Figure 6.1). Zero readings (missing in METR-LA) are not drawn. |
| `fig06_sumo_window.png` | Run `evidence/veins_forecast_routing/20261014T113750Z/` (seed 6593). Raw capture `figure_capture/sumo_t222_car_enters.png` (sha256 `9ed46fe0cc2d1289…`), sumo-gui at 222 s. | macOS `screencapture -l <window id>` of the sumo-gui window during the run; `make_figures.py fig06` only scales it to 1600 px. The red ring marks an RSU's position, not its radio range. |
| `fig07_omnet_window.png` | Same run as fig06. Raw capture `figure_capture/qtenv_t236_after_rsu7_decode.png`, the OMNeT++/Qtenv window paused at 235.79 s, just before RSU 7 decodes status #2 at 236 s. | Window capture, scaled by `make_figures.py fig07`. Its event log shows 802.11p PHY/MAC events at cars and at `rsu[16]`; **the rsu[7] lines are not visible in it**, so caption it as "the packet-level network simulator during the run", not "frame arriving at rsu[7]". |
| `fig08_car_reroute.png` | Same run. Raw capture `figure_capture/sumo_t242_route_changed.png` (sha256 `48ec71d193955719…`), sumo-gui at 242 s, right after `ROUTE CHANGED` for veh0_444. | Window capture, scaled by `make_figures.py fig08`. Shows the new route (thick blue), veh0_444 (blue) and the RSU 7 ring. The demo code draws the old route ORANGE (car A's colour), not red; it is outside this close view. |
| `fig09_explain_terminal.png` | Same run. Terminal text `figure_capture/terminal.log` (or `terminal_partial.log` if the run was still going), events [1]–[11]. | `make_figures.py fig09` renders the lines; text is not edited, only wrapped. |
| `fig11_funnel.png` | `evidence/veins_forecast_routing/20261012T142239Z/summary.json` (20 RSUs) and `…/20261012T143208Z/summary.json` (60 RSUs): `arms.predictive_corrected_v2x.network.downlink.{advice_decided, handed_to_rsu, received_by_car, applied}`. | `make_figures.py fig11`. Checked against 123/14/7/6 and 183/23/19/15: all match. |
| `fig12_vehh.png` | Same two runs: `s201/{baseline,predictive_corrected_v2x}/tripinfo.xml`, parsed by `core.simulation.twin.runtime.parse_metrics` with horizon 2 100 s (1 200 s warm-up + 15 min). | `make_figures.py fig12`. The value from tripinfo must equal `summary.json` `total_vehicle_hours`, or the script stops. 20 RSUs: 1055.5 vs 1055.7; 60 RSUs: 1055.5 vs 1055.9. |

The demo run for fig06, fig08 and fig09:

```
make veins-forecast-routing SEED=6593 ARGS="--minutes 8 --arms predictive_corrected_v2x --demo-early --explain veh0_444 --step-through"
```

`--step-through` only pauses the run at each event so the windows could be captured; it does not change the simulation.

## Missing

- **fig03 (training curve).** Replaced by `fig03_data_split.png`. The checkpoint used everywhere (`…/d1ffd3d52d3caacf60ebf59214673f7c/`) has no training log
  saved with it, in the repo or in the Drive copy. `results/forecasting/aws_logs/GWNet_METR-LA.log` is a different
  training run (folder `333285b1…`): its best model scores 2.7190 mph at 15 min, while this checkpoint's `test_metrics.json`
  says 2.7115. Plotting it as "my model's" curve would be wrong.
- **fig07 (Qtenv, frame at rsu[7]).** The capture used shows the run at 235.79 s but not an rsu[7] line; a frame at
  rsu[7] on screen would need a manual capture.
