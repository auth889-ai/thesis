"""Real road speeds for a city, behind one interface: who measured them and when, or nothing. The live probe readings (the web
app's own database of opt-in phone cells) are read by backend/app/data/probe_speeds.py; this module holds the matching rules and
the recorded datasets, which the research code uses.

    read(city_id, net, edges)  ->  {section id: {"kmh", "tag", "series"}}   only for sections that have a real reading

Sources, each optional per city and never substituted for one another:

    probes        positions shared by people who opted in (`app/probes`): 5-minute cells of about 70 m with a heading.
                  A cell belongs to a city by where it lies (inside the city's built box), not by the city name the
                  phone sent with it, which is whatever the person's profile says. A cell is matched to the route
                  section it lies on and points along. A reading is used only when at least MIN_PHONES distinct
                  phones are behind it (owner's decision, 2026-10-05).
    pems          Caltrans PeMS station speeds. Declared in a city's config under `live.real_sources`. NOT READ YET:
                  it needs an approved account, and the terms shown after login and the freshness of the downloadable
                  data have not been read. Until then the source reports "pending" and gives no value.
    researcher    the researcher's own consented trips (`app/probes/researcher.py`): one device, exempt from the
                  several-phones rule, kept in cells of its own and shown only on the machine that lists the device.
    field_counts  the owner's own roadside counts. No data exists yet; the source gives no value.

    recorded      a published dataset of past measurements, declared in the city's config and read by a module in
                  `app/data/recorded/`. A recorded reading keeps its own date and source and is returned only by
                  `recorded()`: it is never mixed into `read()`, so it can never be shown as the present or reach a
                  travel time or a departure.

A section without a reading is absent from the answer. Nothing is filled in, smoothed across a gap, or borrowed from
another section or another city.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from core.common import tag

MIN_PHONES = 3
MATCH_M = 66.0                # a cell is a hexagon with 66 m sides, so a road through it passes within 66 m of its centre;
                              # the nearest section pointing the cell's way is taken, which cannot tell two parallel roads that close apart
CURRENT_MIN = 15              # a reading older than this is not called current
SERIES_MIN = 120              # the recent history handed to a forecast
BIN_MIN = 5


def _octant(heading_deg: float) -> str:
    return str(int(((heading_deg % 360) + 22.5) // 45) % 8)


def _local_heading(shape, x: float, y: float) -> tuple[float, float]:
    """(distance in metres from the point to the shape, heading in degrees of the segment nearest to it)."""
    best = (math.inf, 0.0)
    for (x0, y0), (x1, y1) in zip([p[:2] for p in shape], [p[:2] for p in shape[1:]]):
        dx, dy = x1 - x0, y1 - y0
        t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)))
        d = math.hypot(x - (x0 + t * dx), y - (y0 + t * dy))
        if d < best[0]:
            best = (d, math.degrees(math.atan2(dx, dy)) % 360)
    return best


def match_cell(net, edges, lat: float, lon: float, octant: str):
    """The section a probe cell belongs to: the nearest one within MATCH_M whose direction there is the cell's octant."""
    x, y = net.convertLonLat2XY(lon, lat)
    near = [(d, e.getID(), e) for e in edges for d, h in [_local_heading(e.getShape(), x, y)] if d <= MATCH_M and _octant(h) == octant]
    return min(near)[2] if near else None


RECORDED_MATCH_M = 30.0       # a camera site must lie this close to the section it measures
RECORDED_HEADING_DEG = 45.0   # and the section must run the way the site's vehicles travel


def _readers() -> dict:
    from core.common.data.recorded import dhatrax
    return {"dhatrax": dhatrax}


def _turn(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def recorded_sources(city_id: str, net=None, bbox=None) -> list[dict]:
    """The recorded datasets a city's config declares, each with its sites inside the city's box and, when the
    network is given, the section each site measures. A site with no stated place is listed without one."""
    from core.common.data import city_config
    from core.common.data import researcher
    try:
        live = city_config.load(city_id).live
    except KeyError:
        return []
    out = []
    if researcher.devices():
        out.append({"kind": "researcher", "state": "active", "note": researcher.SOURCE})
    for src in (live.real_sources if live and live.real_sources else []):
        reader = _readers().get(src.dataset or "") if src.kind == "recorded" else None
        if reader is None:
            continue
        sites = []
        for st in reader.sites():
            site = {**st, "section": None}
            inside = st["located"] and (bbox is None or (bbox[0] <= st["lat"] <= bbox[2] and bbox[1] <= st["lon"] <= bbox[3]))
            if inside and net is not None:
                x, y = net.convertLonLat2XY(st["lon"], st["lat"])
                near = sorted((d, e.getID()) for e, _ in net.getNeighboringEdges(x, y, r=RECORDED_MATCH_M) if not e.isSpecial()
                              for d, h in [_local_heading(e.getShape(), x, y)] if d <= RECORDED_MATCH_M and _turn(h, st["bearing_deg"]) <= RECORDED_HEADING_DEG)
                site["section"] = near[0][1] if near else None
                site["section_distance_m"] = round(near[0][0], 1) if near else None
            if st["located"] and not inside:
                continue                                # a site in another place is not this city's
            sites.append(site)
        out.append({"dataset": reader.NAME, "version": reader.VERSION, "citation": src.citation or reader.CITATION, "licence": src.licence or reader.LICENCE,
                    "caveat": reader.CAVEAT, "fetched": reader.available(), "sites": sites})
    return out


def recorded(city_id: str, net, edges, bbox, at: str) -> dict:
    """{section id: tagged recorded speed} for the sections of a route that a recorded site measures, at a clock time
    of the site's own recording day. Only the interval that contains that time is used; a missing one stays missing."""
    on_route = {e.getID() for e in edges}
    out = {}
    for src in recorded_sources(city_id, net, bbox):
        reader = next(r for r in _readers().values() if r.NAME == src["dataset"])
        for st in src["sites"]:
            got = reader.reading_at(st["site"], at) if st["section"] in on_route else None
            if got:
                label = f"Recorded, {src['dataset']}, {st['day']}"
                t = tag.real(f"{src['dataset']} fixed camera, site {st['site']}: {src['caveat']}", f"{got['start']} (camera clock)", f"{src['dataset']} v{src['version']}, {src['licence']}",
                             recorded=True, label=label, citation=src["citation"], vehicles=got["vehicles"], stretch_m=got["stretch_m"], statistic="median over a 5-minute interval")
                out[st["section"]] = tag.tagged(got["median_kmh"], "km/h", t)
    return out

