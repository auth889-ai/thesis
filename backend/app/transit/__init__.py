"""Public transport for the commute: the rail and metro lines of any city, read from OpenStreetMap at
request time, and a door-to-door estimate beside the road routes.

    osm        the Overpass query: route relations with their ordered, located stops, within the trip's box
    schedule   operator facts OSM does not carry (headway, hours, commercial speed), each with its source
    service    the plan: walk to the nearest stop, wait, ride, walk; totals and provenance
    router     GET /api/transit/lines, POST /api/transit/plan

Nothing here is a timetable lookup: OSM gives the geometry and the operator's published headway
gives the wait; the ride time is estimated from station spacing and the line's commercial speed,
and every response says which of its numbers are estimates.
"""
