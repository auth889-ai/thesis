#!/usr/bin/env python3
"""V2X penetration-rate sweep on the registered Dhaka R1 Eclipse MOSAIC scenario.

For every (P, seed) point:
  1. copy results/artifacts/mosaic_dhaka/dhaka_r1 -> results/networking/generated_scenarios/dhaka_r1_p{P}_s{SEED}/
     (big, immutable inputs -- net/route/db/osm -- are symlinked, configs copied);
  2. rewrite mapping/mapping_config.json so that a fraction P of the SUMO-spawned vehicles is
     equipped with the official V2X app stack [WeatherWarningApp (sense hazard -> DENM ->
     NavigationModule reroute), SlowDownApp] and the remaining 1-P carry only SlowDownApp;
  3. set randomSeed / duration in scenario_config.json (+ SUMO --seed, tripinfo/summary outputs);
  4. run `mosaic.sh -c <scenario_config.json> -l logback_sweep.xml -w 0`;
  5. parse the MOSAIC log directory: visualizer.csv (registrations, V2X tx/rx, per-message latency,
     positions), Navigation.log (route switches), Mapping.log (equipment cross-check), MOSAIC.log
     (wall clock), SUMO tripinfo.xml + summary.xml;
  6. write results/networking/penetration_p{P}_s{SEED}.json and re-aggregate penetration.csv + .md.

Definitions (also written into every JSON): see sweep/metrics.py.

Usage
  python -m core.networking.mosaic.penetration_sweep --p 0.25 --seed 11 --duration 600      # one point
  python -m core.networking.mosaic.penetration_sweep --all --seeds 11 22 33 --duration 600   # full sweep, sequential
  python -m core.networking.mosaic.penetration_sweep --parse-only <mosaic log dir> --p 0.25 --seed 11
  python -m core.networking.mosaic.penetration_sweep --aggregate                              # rebuild csv/md only

The work lives in core.networking.mosaic.sweep (scenario, parsers, metrics, report, cli); this module
is the import surface and the entry point.
"""
from __future__ import annotations

from core.networking.mosaic.sweep.cli import main as _main, run_point  # noqa: F401
from core.networking.mosaic.sweep.metrics import HAZARD, dist_to_hazard_m, keep_small_logs, parse_point, refresh_tripinfo, time_to_hazard  # noqa: F401
from core.networking.mosaic.sweep.parsers import (equipped_from_mapping_log, hist_percentile, parse_id_map, parse_mapping,  # noqa: F401
                                                 parse_mosaic_log, parse_navigation, parse_summary, parse_tripinfo, parse_visualizer, pct)
from core.networking.mosaic.sweep.report import aggregate  # noqa: F401
from core.networking.mosaic.sweep.scenario import (FALLBACK_NET, LOGBACK, MOSAIC_HOME, NET_DIR, NS, OUTPUT_CONFIG, P_GRID, RESULTS, SCEN_ROOT,  # noqa: F401
                                                  SDA, SRC_SCENARIO, SYMLINK_SUFFIXES, WWA, build_scenario, ensure_net_file,
                                                  mapping_config, point_name, ptag, run_mosaic)


def main():
    return _main(__doc__)


if __name__ == "__main__":
    main()
