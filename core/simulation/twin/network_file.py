"""The default city's SUMO network, demand and demand scale, read from its config, and expanded on demand.

Which city, which network file, which routes and which calibrated scale are stated in config/cities/<city_id>.yaml
(`sumo.prebuilt`, or the files the city pipeline builds); nothing here names a city. `DHAKA_R1` remains as the name
older callers import for the default network.

A network can be 16 MB of XML, too large to track, so the repository carries a `.gz` and this module expands it the
first time anything needs it. Three modules used to carry their own copy of this logic and one of them (the NLP
event feed) did not, which showed up as every incident mapping to zero edges instead of an error. One place now.
"""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path

from core.common.data import city_config
from core.common.paths import REPO

_CITY = city_config.default()
_PRE = _CITY.sumo.prebuilt
_BUILT = REPO / "data/cities" / _CITY.city_id / "sumo"          # where the city pipeline writes a built network
DEFAULT_NET = REPO / _PRE.network if _PRE else _BUILT / f"{_CITY.city_id}.net.xml"
DEFAULT_ROUTES = REPO / _PRE.routes if _PRE else _BUILT / f"{_CITY.city_id}.rou.xml"
DEFAULT_SCALE = _PRE.demand_scale if _PRE else 1.0
DHAKA_R1 = DEFAULT_NET


def ensure_net(net: Path = DEFAULT_NET) -> Path:
    """Return a usable .net.xml path, expanding the tracked .gz if necessary."""
    net = Path(net)
    if net.exists():
        return net
    gz = net.with_suffix(net.suffix + ".gz")
    if not gz.exists():
        raise SystemExit(f"network missing: neither {net} nor {gz} is present")
    net.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(gz, "rb") as fi, open(net, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    return net
