"""The V2X penetration-rate sweep on the registered Dhaka R1 Eclipse MOSAIC scenario, one module per step:

    scenario   build one (P, seed) scenario from the frozen inputs and run mosaic.sh on it
    parsers    stream the MOSAIC log directory and SUMO's outputs into facts
    metrics    the point record: vehicles, V2X delivery and latency, routing, travel time, time-to-hazard
    report     penetration.csv and penetration.md from every point JSON
    cli        the command line: one point, the full grid, parse-only, aggregate, refresh

`core.networking.mosaic.penetration_sweep` remains the import surface and the module to run.
"""
