"""The frozen Dhaka R1 network, expanded on demand.

The network is 16 MB of XML, too large to track, so the repository carries a 2 MB `.gz` and this
module expands it the first time anything needs it. Three modules used to carry their own copy of
this logic and one of them (the NLP event feed) did not, which showed up as every incident mapping
to zero edges instead of an error. One place now, imported by all of them.
"""
from __future__ import annotations

import gzip
import shutil
from pathlib import Path

from traffictwin.paths import REPO
DHAKA_R1 = REPO / "paper_labs/02_dhaka_osm/outputs/lab02_v2/network/dhaka_r1.net.xml"


def ensure_net(net: Path = DHAKA_R1) -> Path:
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
