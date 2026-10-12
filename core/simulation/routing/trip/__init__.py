"""ANALYZE TRAFFIC, one module per responsibility:

    geometry   route-to-corridor geometry and the congestion-band multiplier
    places     city and place resolution (known Dhaka places, OpenStreetMap's geocoder)
    corridors  corridor states from speeds, corridor polylines, observatory fill-in, backtest accuracy
    routes     the candidate routes: the live provider, or the local router on the frozen network
    pricing    pricing every route from the forecast and choosing one, with the reason
    analysis   the stages in order, with provenance
    jobs       the background job table: start / status
    models     which forecast models can serve a city

`core.simulation.routing.trip_analysis` remains the import surface for the routers, the agent tools and the tests.
"""
