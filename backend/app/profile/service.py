"""The person's context for every other module: their clock, their city, their home, the reliability they asked for.
Nothing here is a fixed place. When a person has no profile yet, the deployment's defaults apply (config.DEFAULT_CITY,
config.DEFAULT_TZ), and every answer says so through `source`."""
from __future__ import annotations

from datetime import datetime, timezone, tzinfo
from zoneinfo import ZoneInfo

from app import config
from app.profile import store

DEFAULT_TARGET = 0.8


def profile(user_id: str) -> dict | None:
    return store.get(user_id)


def tz_for(user_id: str | None) -> tzinfo:
    p = store.get(user_id) if user_id else None
    return zone(p["timezone"] if p and p.get("timezone") else config.DEFAULT_TZ)


def zone(name: str | None) -> tzinfo:
    try:
        return ZoneInfo(name or config.DEFAULT_TZ)
    except Exception:                                   # noqa: BLE001 - an unknown zone name falls back to the deployment default
        return ZoneInfo(config.DEFAULT_TZ)


def city_for(user_id: str | None) -> str:
    p = store.get(user_id) if user_id else None
    return p["city"] if p and p.get("city") else config.DEFAULT_CITY


def home_for(user_id: str | None) -> str | None:
    p = store.get(user_id) if user_id else None
    return (p or {}).get("home") or None


def target_for(user_id: str | None) -> float:
    p = store.get(user_id) if user_id else None
    return float(p["on_time_target"]) if p and p.get("on_time_target") else DEFAULT_TARGET


def local_clock(user_id: str | None, at: datetime | None = None) -> datetime:
    return (at or datetime.now(timezone.utc)).astimezone(tz_for(user_id))


def context(user_id: str) -> dict:
    """What the app shows and what the tools read: with `source` saying whether it came from the person or the deployment."""
    p = store.get(user_id)
    return {"user_id": user_id, "exists": p is not None, "name": (p or {}).get("name"), "timezone": (p or {}).get("timezone") or config.DEFAULT_TZ,
            "city": city_for(user_id), "lat": (p or {}).get("lat"), "lng": (p or {}).get("lng"), "home": home_for(user_id), "work": (p or {}).get("work"),
            "on_time_target": target_for(user_id), "source": "person" if p else "deployment default", "local_time": local_clock(user_id).isoformat()}


def locate(lat: float, lng: float) -> dict:
    """The city at a point, from OpenStreetMap's reverse geocoder; the person confirms it."""
    from core.simulation.routing.trip.places import reverse_geocode
    hit = reverse_geocode(lat, lng)
    a = hit.get("address", {})
    city = a.get("city") or a.get("town") or a.get("municipality") or a.get("county") or a.get("state") or hit.get("display_name", "").split(",")[0]
    return {"lat": lat, "lng": lng, "city": city, "country": a.get("country"), "display_name": hit.get("display_name"), "source": "openstreetmap nominatim reverse"}
