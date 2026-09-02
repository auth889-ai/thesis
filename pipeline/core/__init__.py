"""DhakaFlow Nexus — permanent platform.

Real-time camera-grounded, forecast-aware and safety-constrained digital twin
for network-wide traffic-signal and routing optimization under heterogeneous
Bangladeshi urban traffic.

Layout
------
common/        shared types, units, provenance, component registry
simulation/    simulator backends + signal actuation      (graduated: Lab 01)
perception/    detection, tracking, camera->traffic sensor (Labs 04-06)
forecasting/   uniform forecaster contract                 (Labs 07-12)
digital_twin/  calibrated twin + what-if                   (Lab 13)
control/       signal controllers and actions              (graduated: Lab 01; Labs 14-20)
routing/       routing strategies                          (Lab 22)
safety/        constraints, shield, action masking         (graduated: Lab 01; Lab 21)
priority/      emergency / transit / pedestrian priority   (Lab 23)
pipeline/nlp/           incident extraction                         (Lab 24)
genai/         grounded operator copilot                   (Lab 25)
evaluation/    metrics, traffic science, fair benchmarks   (graduated: Labs 00-01)
visualization/ figure contract

Only interfaces and shared types live here. Algorithms live in paper labs and
reach the platform through adapters registered in `common.registry`.
"""
__version__ = "0.1.0"
