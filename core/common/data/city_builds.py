"""Adding a city: write its config from a search result, then build it with the city pipeline, one at a time.

The config has the same strict schema as a hand-written one and names a source for every value. What the search did
not find is written as `null` with the reason; nothing is guessed. A city without a known driving side is refused,
because a network built for the wrong side of the road would be wrong without showing it.

Limits, all checked before anything is requested: the area (MAX_SIDE_DEG), one build at a time, a city already built
is returned as it is, and a daily count of new builds, because each build sends one road request to the public
Overpass server, whose guidance for an app in regular use is "less than 100 queries fetching less 10 MB of data per
day", with an identifying User-Agent and "No parallel running of multiple scripts" (read 2026-10-05).
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from core.common.data import city_config
from core.common.paths import REPO

MAX_SIDE_DEG = 0.06                 # about 6.5 km on a side
DAILY_BUILDS = 8                    # new cities per day; each is one Overpass road request of the order of 1-2 MB
LEDGER = REPO / "data/cities/_builds.jsonl"
DEMAND = {"seed": 11, "period_s": 2.0, "horizon_s": 1800}       # the same generated demand as every city
_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_running: list[str] = []


class Refused(ValueError):
    """The request cannot be carried out, and the message says why."""


def check_box(box: list[float]) -> tuple[float, float, float, float]:
    s, w, n, e = (float(x) for x in box)
    if not (-90 <= s < n <= 90 and -180 <= w < e <= 180):
        raise Refused("the area must be [south, west, north, east] with south < north and west < east")
    if n - s > MAX_SIDE_DEG + 1e-9 or e - w > MAX_SIDE_DEG + 1e-9:
        raise Refused(f"the area is too large: at most {MAX_SIDE_DEG} degrees (about 6.5 km) on a side")
    return s, w, n, e


def built_today(ledger: Path = LEDGER) -> int:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    return sum(1 for line in ledger.read_text().splitlines() if json.loads(line)["utc"].startswith(today)) if ledger.exists() else 0


def is_built(city_id: str, config_dir: Path = city_config.CONFIG_DIR, city_dir: Path | None = None) -> bool:
    city_dir = city_dir or REPO / "data/cities"
    return (Path(config_dir) / f"{city_id}.yaml").exists() and (Path(city_dir) / city_id / "sumo" / "MANIFEST.json").exists()


def config_text(c: dict, box: tuple[float, float, float, float], adjusted: bool) -> str:
    """The YAML of a generated city: every value with its source, every unknown as null with the reason."""
    s, w, n, e = box
    names = "\n".join(f"  {lang}: {json.dumps(name, ensure_ascii=False)}" for lang, name in c["display_name"].items())
    missing = "not held by Overture's divisions theme and not looked up anywhere else when this city was added"
    return f"""# {c['name']}: added through "Add your city" on {time.strftime('%Y-%m-%d', time.gmtime())}. Generated, not hand-written.
# Source of every value below unless it says otherwise: {c['source']}
# (ODbL; © OpenStreetMap contributors, Overture Maps Foundation).
city_id: {city_config.slug(c['name'])}
display_name:
{names}
country: {json.dumps(c['country'])}          # ISO country code, from Overture
bounding_box:
  south: {s}
  west: {w}
  north: {n}
  east: {e}
  source: "{'adjusted by the person who added the city from ' if adjusted else ''}a {round(n - s, 4)} x {round(e - w, 4)} degree box proposed around the Overture point {c['lon']}, {c['lat']} of division {c['division_id']}"
time_zone: null             # {missing}
default_languages: null     # {missing}
emergency_numbers: null     # {missing}
units: null                 # {missing}
drive_side: {c['drive_side']}            # the driving side recorded for the country ({c['country']}) in Overture's divisions theme
vehicle_classes: null       # no fleet mix has been sourced for this city
plugins: []
datasets: []                # no traffic data for this city: it gets simulated vehicles only
sumo:
  prebuilt: null
  build:                    # generated demand, uncalibrated: never a measurement of this city's traffic
    seed: {DEMAND['seed']}
    period_s: {DEMAND['period_s']}
    horizon_s: {DEMAND['horizon_s']}
"""


def prepare(candidate: dict, box: list[float] | None, config_dir: Path = city_config.CONFIG_DIR) -> tuple[str, bool]:
    """Check the request and write the city's config. Returns (city id, whether the city was already built)."""
    from core.common.data.city_search import proposed_box
    checked = check_box(box or candidate["proposed_box"])
    if candidate.get("drive_side") not in ("left", "right"):
        raise Refused(f"the side of the road {candidate.get('country') or 'this country'} drives on is not recorded in Overture, and a network cannot be built without it")
    cid = city_config.slug(candidate["name"])
    if not cid:
        raise Refused("the city's name gives no usable id")
    path = Path(config_dir) / f"{cid}.yaml"
    if path.exists():
        if candidate["division_id"] not in path.read_text():
            raise Refused(f"a different city already uses the id {cid!r}; it is not overwritten")
        return cid, True
    adjusted = [round(x, 5) for x in checked] != proposed_box(candidate["lon"], candidate["lat"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config_text(candidate, checked, adjusted))
    city_config.load(cid, config_dir)                      # the generated file must pass the same strict schema
    return cid, False


def start(candidate: dict, box: list[float] | None = None) -> dict:
    """Begin building a city in the background. Refuses instead of queueing when another build is running."""
    from core.simulation.twin import city_pipeline
    with _lock:
        if _running:
            raise Refused(f"another city ({_running[0]}) is being built; one at a time")
        cid, existed = prepare(candidate, box)
        if existed and is_built(cid):
            return {"job": None, "city_id": cid, "status": "done", "stage": "already built: nothing was requested from anyone", "cached": True}
        if built_today() >= DAILY_BUILDS:
            raise Refused(f"{DAILY_BUILDS} cities have been built today; the limit protects the public OpenStreetMap server")
        job = "city_" + uuid.uuid4().hex[:8]
        _jobs[job] = {"job": job, "city_id": cid, "status": "running", "stage": "fetching roads from OpenStreetMap, building the network, generating demand", "cached": False}
        _running.append(cid)

    def work() -> None:
        try:
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            with open(LEDGER, "a") as fh:
                fh.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "city_id": cid, "division_id": candidate["division_id"]}) + "\n")
            record = city_pipeline.run(cid)
            _jobs[job].update(status="done", stage="done", network=record.get("network"), demand={k: record["demand"][k] for k in ("vehicles", "label")}, evidence=f"evidence/cities/{cid}/build.json")
        except BaseException as exc:                       # noqa: BLE001 - the person is told why
            _jobs[job].update(status="failed", stage="failed", reason=f"{type(exc).__name__}: {str(exc)[:300]}")
        finally:
            _running.clear()

    threading.Thread(target=work, name=f"build-{cid}", daemon=True).start()
    return dict(_jobs[job])


def status(job: str) -> dict | None:
    return dict(_jobs[job]) if job in _jobs else None
