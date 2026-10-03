"""Watch a road; raise an alert when the served model predicts its onset at two consecutive moments (hysteresis),
at most once per cooldown; publish it through the person's notifications (in-app, SNS when configured)."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import select

from app.alerts.db import RoadAlertRow, RoadWatchRow
from app.lifeos.db import session

COOLDOWN_TICKS = 6                       # 30 minutes of 5-minute ticks: one alert per episode, not one per tick
CONFIRM_TICKS = 2                        # onset must be predicted at this tick and the previous one


def _id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def watch(person_id: str, dataset: str, node: str, label: str | None = None, db_url: str | None = None) -> dict:
    wid = _id("watch", person_id, dataset, node)
    with session(db_url) as s:
        row = s.get(RoadWatchRow, wid) or RoadWatchRow(id=wid, person_id=person_id, dataset=dataset, node=node, label=label, created_at=datetime.now(timezone.utc))
        row.label = label or row.label
        s.add(row); s.commit()
        return _watch(row)


def unwatch(person_id: str, watch_id: str, db_url: str | None = None) -> bool:
    with session(db_url) as s:
        row = s.get(RoadWatchRow, watch_id)
        if not row or row.person_id != person_id:
            return False
        s.delete(row); s.commit(); return True


def watches(person_id: str, db_url: str | None = None) -> list[dict]:
    with session(db_url) as s:
        return [_watch(r) for r in s.execute(select(RoadWatchRow).where(RoadWatchRow.person_id == person_id)).scalars()]


def _watch(r: RoadWatchRow) -> dict:
    return {"id": r.id, "person_id": r.person_id, "dataset": r.dataset, "node": r.node, "label": r.label, "created_at": r.created_at.isoformat()}


def evaluate(dataset: str, as_of: int, model: str | None = None, onsets=None, db_url: str | None = None, publish=None) -> dict:
    """Evaluate every watch on `dataset` at `as_of`. `onsets(dataset, as_of, model)` and `publish(person, kind, text, detail)`
    are injectable so the rule is testable without a model or a phone."""
    from app.forecasting.operations import onset_now
    from app.plan import notifications
    onsets = onsets or onset_now.onsets
    publish = publish or notifications.publish
    now_run = onsets(dataset, as_of, model)
    prev_run = onsets(dataset, as_of - 1, model) if as_of - 1 >= 12 else {"roads": []}
    now_by = {r["node"]: r for r in now_run["roads"]}
    prev_by = {r["node"]: r for r in prev_run["roads"]}
    raised, checked = [], 0
    with session(db_url) as s:
        for w in s.execute(select(RoadWatchRow).where(RoadWatchRow.dataset == dataset)).scalars():
            checked += 1
            cur, prev = now_by.get(w.node), prev_by.get(w.node)
            if not cur or not cur["onset_in_min"] or not prev or not prev["onset_in_min"]:
                continue                                                   # not predicted at both ticks
            recent = s.execute(select(RoadAlertRow).where(RoadAlertRow.watch_id == w.id, RoadAlertRow.as_of > as_of - COOLDOWN_TICKS)).first()
            if recent:
                continue                                                   # one alert per episode
            h = cur["onset_in_min"]
            a = RoadAlertRow(id=_id("alert", w.id, str(as_of)), watch_id=w.id, as_of=as_of, model=now_run["model"], horizon_min=h,
                             now_speed=cur["now"], predicted_speed=cur["predicted"][str(h)], threshold=cur["threshold"], created_at=datetime.now(timezone.utc))
            s.add(a)
            text = f"{w.label or w.node}: congestion forming in about {h} min ({cur['now']} now, {cur['predicted'][str(h)]} forecast, threshold {cur['threshold']}; {now_run['model']})"
            publish(w.person_id, "onset", text, f'{{"watch_id": "{w.id}", "as_of": {as_of}, "horizon_min": {h}}}')
            raised.append({"watch_id": w.id, "person_id": w.person_id, "node": w.node, "horizon_min": h, "text": text})
        s.commit()
    return {"dataset": dataset, "as_of": as_of, "model": now_run["model"], "watches_checked": checked, "alerts": raised,
            "rule": f"onset predicted at {CONFIRM_TICKS} consecutive moments; one alert per {COOLDOWN_TICKS} ticks"}


def alerts(person_id: str, db_url: str | None = None) -> list[dict]:
    with session(db_url) as s:
        rows = s.execute(select(RoadAlertRow, RoadWatchRow).join(RoadWatchRow).where(RoadWatchRow.person_id == person_id).order_by(RoadAlertRow.as_of.desc())).all()
        return [{"id": a.id, "watch_id": a.watch_id, "node": w.node, "label": w.label, "dataset": w.dataset, "as_of": a.as_of, "model": a.model,
                 "horizon_min": a.horizon_min, "now_speed": a.now_speed, "predicted_speed": a.predicted_speed, "threshold": a.threshold,
                 "created_at": a.created_at.isoformat()} for a, w in rows]
