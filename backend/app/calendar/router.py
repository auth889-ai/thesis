"""Calendar routes: import an .ics file or URL; list events in a window."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.calendar import ics, store

router = APIRouter()


@router.post("/api/calendar/import", tags=["calendar"])
async def calendar_import(user_id: str = Form("demo"), url: str | None = Form(None), name: str | None = Form(None), file: UploadFile | None = File(None)):
    """Import events from an uploaded .ics file or a subscription URL. Re-importing updates events by their UID."""
    if file is not None:
        text = (await file.read()).decode("utf-8", errors="replace"); source = "ics:" + (file.filename or "upload")
    elif url:
        try:
            text = ics.fetch(url)
        except Exception as exc:                        # noqa: BLE001
            raise HTTPException(422, f"could not read the calendar URL: {type(exc).__name__}")
        source = "ics:" + url[:80]
    else:
        raise HTTPException(422, "give a .ics file or a url")
    events = ics.parse(text)
    if not events:
        raise HTTPException(422, "no events found in that calendar")
    rows = store.import_events(user_id, events, source)
    if url:
        store.remember_calendar(user_id, url, name or "imported calendar", len(rows))
    return {"imported": len(rows), "source": source, "events": rows[:20]}


@router.get("/api/calendar/events", tags=["calendar"])
def calendar_events(user_id: str = "demo", hours: float = 36.0):
    return {"events": store.upcoming(user_id, hours), "calendars": store.list_calendars(user_id)}
