"""Settings of the live twin: output paths, defaults, the routing arms, and the sumo-gui colours."""
from __future__ import annotations

from app import evidence_paths as config

OUT_ROOT = config.REPO / "results/live/sim"
HISTORY = config.REPO / "results/live/sim_history.json"
MAX_VEHICLES_SHOWN = 2000
ARMS = ("baseline", "reactive", "prediction_aware")
DEFAULTS = {"scale": None, "duration_s": 900, "seed": 11, "compliance": 0.3, "arm": "reactive",
            "levels": "observed", "step_delay_ms": 100, "v2x": "ideal", "horizon_min": 15,
            "continuous": False, "network": "dhaka_r1", "gui": False}
# vehicle colours in sumo-gui (RGBA): what a viewer sees moving on the OSM network
COLOUR = {"normal": (255, 200, 0, 255),        # background vehicle (SUMO passenger)
          "reactive": (40, 120, 255, 255),     # rerouted by rerouteTraveltime on current travel times
          "advised": (40, 190, 60, 255),       # pre-departure route from the production optimizer (prediction-aware / oracle debug)
          "stopped": (220, 40, 40, 255),       # standing > 20 s (queue)
          "probe": (255, 0, 255, 255),         # the USER PROBE: the analysed trip
          "heavy": (150, 150, 150, 255)}       # bus / truck, where the demand has them
VISUAL_LEGEND = {"NORMAL BACKGROUND VEHICLE": "amber", "REACTIVE-REROUTED VEHICLE": "blue", "PREDICTION-AWARE-REROUTED VEHICLE": "green",
                 "USER PROBE VEHICLE": "magenta, 8 m long", "STOPPED / QUEUED VEHICLE (> 20 s)": "red", "BUS / TRUCK": "grey"}
TELEPORT_REASON = "SUMO teleports a vehicle that waited longer than --time-to-teleport (300 s) at a blocked position (jam / junction blocker); TraCI exposes the event, not the reason text"
DHAKA_CENTER = (90.395, 23.755)
LIVE_REFRESH_S = 300          # the provider's own cadence; the recorder samples at the same rate
DEMAND_PERIOD_S = 3600        # the calibrated demand file covers one hour; it is replayed hourly
