"""A small iCalendar reader: enough of RFC 5545 for events with a time and a place. No dependency."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

LOCAL_UTC_OFFSET_H = 6                                 # floating (no-zone) times are read as the person's local time


def _unfold(text: str) -> list[str]:
    """Continuation lines (a leading space or tab) belong to the previous line."""
    out: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _unescape(v: str) -> str:
    return v.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\").strip()


def parse_dt(value: str, params: str, tz=None) -> tuple[str, bool]:
    """('ISO instant in UTC', all_day). Forms: 20260930T090000Z · 20260930T090000 (+TZID) · 20260930 (date only).
    Floating times (no zone) are read in `tz`, the person's zone."""
    tz = tz or timezone(timedelta(hours=LOCAL_UTC_OFFSET_H))
    v = value.strip()
    if re.fullmatch(r"\d{8}", v):
        d = datetime.strptime(v, "%Y%m%d").replace(tzinfo=tz)
        return d.astimezone(timezone.utc).isoformat(), True
    if v.endswith("Z"):
        return datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat(), False
    d = datetime.strptime(v[:15], "%Y%m%dT%H%M%S")
    m = re.search(r"TZID=([^;:]+)", params or "")
    if m:
        try:
            from zoneinfo import ZoneInfo
            return d.replace(tzinfo=ZoneInfo(m.group(1))).astimezone(timezone.utc).isoformat(), False
        except Exception:                               # noqa: BLE001 - an unknown zone name: read as local time
            pass
    return d.replace(tzinfo=tz).astimezone(timezone.utc).isoformat(), False


def parse(text: str, tz=None) -> list[dict]:
    """Every VEVENT as {uid, title, start_utc, end_utc, location, all_day, description}."""
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            if cur.get("start_utc"):
                cur.setdefault("uid", f"{cur.get('title', '')}@{cur['start_utc']}")
                cur.setdefault("end_utc", cur["start_utc"]); cur.setdefault("location", ""); cur.setdefault("title", "(untitled)"); cur.setdefault("all_day", False); cur.setdefault("description", "")
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, _, value = line.partition(":")
            name, _, params = head.partition(";")
            name = name.upper()
            if name == "DTSTART":
                cur["start_utc"], cur["all_day"] = parse_dt(value, params, tz)
            elif name == "DTEND":
                cur["end_utc"], _ = parse_dt(value, params, tz)
            elif name == "SUMMARY":
                cur["title"] = _unescape(value)
            elif name == "LOCATION":
                cur["location"] = _unescape(value)
            elif name == "DESCRIPTION":
                cur["description"] = _unescape(value)[:500]
            elif name == "UID":
                cur["uid"] = value.strip()
    return events


def fetch(url: str, timeout_s: int = 20) -> str:
    """Read a calendar subscription URL (webcal:// is https://)."""
    import urllib.request
    u = re.sub(r"^webcal://", "https://", url.strip())
    req = urllib.request.Request(u, headers={"User-Agent": "traffictwin/1.0 (calendar import)"})
    with urllib.request.urlopen(req, timeout=timeout_s) as r:
        return r.read().decode("utf-8", errors="replace")
