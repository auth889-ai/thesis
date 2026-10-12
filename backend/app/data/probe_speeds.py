"""Live road speeds from the web app's own store of opt-in phone cells (probes): read(), sources(). The matching rules and the
recorded datasets are research code, in core/common/data/real_speeds.py; this is the web app's half, because it reads the app's
database."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.common import tag
from core.common.data.real_speeds import BIN_MIN, CURRENT_MIN, MIN_PHONES, SERIES_MIN, match_cell  # noqa: F401


def _in_box(bbox):
    from app.probes.db import ProbeCellRow
    s, w, n, e = bbox
    return (ProbeCellRow.lat >= s, ProbeCellRow.lat <= n, ProbeCellRow.lng >= w, ProbeCellRow.lng <= e)


def from_probes(city_id: str, net, edges, bbox, now: datetime | None = None, db_url: str | None = None) -> dict:
    from sqlalchemy import select
    from app.lifeos.db import session
    from app.probes.db import ProbeCellRow
    now = now or datetime.now(timezone.utc)
    with session(db_url) as s:
        rows = s.execute(select(ProbeCellRow).where(*_in_box(bbox), ProbeCellRow.bin_start >= now - timedelta(minutes=SERIES_MIN),
                                                    ProbeCellRow.bin_start <= now)).scalars().all()
    from core.common.data import researcher
    show_own = bool(researcher.devices())               # only on the machine that lists the researcher's device
    bins: dict[str, dict[datetime, list]] = {}
    own_bins: dict[str, dict[datetime, list]] = {}
    for r in rows:
        octant, own = r.cell.split(":")[1], researcher.own_cell(r.cell)
        if octant == "x" or r.mean_speed_kmh is None or (own and not show_own) or (not own and r.n_devices < MIN_PHONES):
            continue                                    # no heading, no speed, or too few phones: not a reading
        e = match_cell(net, edges, r.lat, r.lng, octant)
        if e is not None:
            (own_bins if own else bins).setdefault(e.getID(), {}).setdefault(r.bin_start, []).append(r)
    mine = set()
    for sid, by_bin in own_bins.items():                # the researcher's own trips fill only sections nobody else measured
        if sid not in bins:
            bins[sid] = by_bin; mine.add(sid)
    out = {}
    for sid, by_bin in bins.items():
        series = []
        for start in sorted(by_bin):
            cells = by_bin[start]
            points = sum(c.n_points for c in cells)
            series.append({"bin_start": start.isoformat(), "kmh": round(sum(c.mean_speed_kmh * c.n_points for c in cells) / points, 1),
                           "phones_at_least": max(c.n_devices for c in cells), "cells": len(cells)})
        last = series[-1]
        if datetime.fromisoformat(last["bin_start"]) < now - timedelta(minutes=CURRENT_MIN):
            continue                                    # history only: nothing current to show for this section
        out[sid] = {"kmh": last["kmh"], "series": series,
                    "tag": tag.real(researcher.SOURCE if sid in mine else "phones that opted in, on this road section", last["bin_start"], f"{city_id} probe cells",
                                    phones_at_least=last["phones_at_least"], bin_minutes=BIN_MIN, researcher=sid in mine)}
    return out


def read(city_id: str, net, edges, bbox, now: datetime | None = None, db_url: str | None = None) -> dict:
    """Real readings for these sections from every source that has any. Today that is the probes source alone."""
    return from_probes(city_id, net, edges, bbox, now, db_url)


def sources(city_id: str, bbox, db_url: str | None = None) -> list[dict]:
    """What each real source holds for this city right now, for the page to say in words. No value is implied."""
    from sqlalchemy import func, select
    from core.common.data import city_config
    from app.lifeos.db import session
    from app.probes.db import ProbeCellRow
    with session(db_url) as s:
        stored = s.execute(select(func.count()).select_from(ProbeCellRow).where(*_in_box(bbox))).scalar_one()
    out = [{"kind": "probes", "state": "collecting" if stored else "empty", "rule": f"a reading needs at least {MIN_PHONES} distinct phones",
            "cells_stored": tag.tagged(stored, "cells", tag.real("this app's own store of opt-in phone cells, inside this city's built area", datetime.now(timezone.utc).isoformat(), f"{city_id} probe cells"))}]
    from core.common.data import researcher
    if researcher.devices():
        out.append({"kind": "researcher", "state": "active", "note": researcher.SOURCE})
    try:
        live = city_config.load(city_id).live
    except KeyError:
        live = None
    for src in (live.real_sources if live and live.real_sources else []):
        out.append({"kind": src.kind, "state": src.status, "note": src.note})
    return out


