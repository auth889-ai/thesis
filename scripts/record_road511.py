#!/usr/bin/env python3
"""24/7 road511 recorder — incident timeline + camera snapshots.

Runs until artifacts/road511_recordings/STOP exists (touch it to stop) or the
process is killed. Designed to accrue wall-clock data for the sprint:

* every minute: one events sweep per jurisdiction (CO, WA) — the raw payload
  goes to the ObservationStore; a DEDUPED delta timeline goes to
  incidents_timeline.jsonl (append only when an event is new or its
  last_updated changed), so congestion labels are a clean event stream.
* every minute: SNAPSHOTS_PER_CYCLE snapshot images from usable cameras,
  round-robin, saved under snapshots/<camera_id>/<utc>.jpg. Snapshot hosts
  (state DOT, e.g. cocam.carsprogram.org) are outside the road511 API rate
  limit; we stay polite anyway.
* every 30 minutes: refresh the camera roster.

API budget: 2 events + (roster refresh amortised) ≈ 3 calls/min against the
provider's 30/min limit, and the provider's own _RateGate caps bursts at 20.

Classification (locked, from road511_provider): PROVIDER_INTEGRATION_VALIDATION
/ DOMAIN_SHIFT_MEASUREMENT — never a Dhaka validation source.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dhakaflow.live.providers import ObservationStore            # noqa: E402
from dhakaflow.live.road511_provider import Road511Provider      # noqa: E402

ROOT = REPO / "artifacts" / "road511_recordings"
STOP_FILE = ROOT / "STOP"
SNAP_DIR = ROOT / "snapshots"
TIMELINE = ROOT / "incidents_timeline.jsonl"
STATE = ROOT / "recorder_state.json"
LOG = ROOT / "recorder.log"

JURISDICTIONS = ["CO", "WA"]
# Denver metro bbox — the densest verified camera cluster.
CAMERA_BBOX = (39.4, 40.1, -105.5, -104.6)
CAMERA_JURISDICTION = "CO"
SNAPSHOTS_PER_CYCLE = 6
ROSTER_REFRESH_S = 30 * 60
CYCLE_S = 60

UA = {"User-Agent": "dhakaflow-research/0.1 (+thesis; contact via key owner)"}


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {"seen": {}, "snap_cursor": 0}


def save_state(state: dict) -> None:
    STATE.write_text(json.dumps(state))


def sweep_events(provider: Road511Provider, state: dict) -> int:
    """Append new/changed events to the timeline. Returns count appended."""
    appended = 0
    for jur in JURISDICTIONS:
        try:
            events = provider.list_events(jur, limit=100)
        except Exception as exc:                      # noqa: BLE001 — keep running
            log(f"events {jur} FAILED: {exc!r}")
            continue
        for ev in events:
            key = ev["id"]
            marker = ev["last_updated"] or ev["start_time"]
            if state["seen"].get(key) == marker:
                continue
            state["seen"][key] = marker
            with open(TIMELINE, "a") as fh:
                fh.write(json.dumps(ev) + "\n")
            appended += 1
    # Bound the dedup map: keep newest ~5000 entries.
    if len(state["seen"]) > 6000:
        for k in list(state["seen"])[: len(state["seen"]) - 5000]:
            del state["seen"][k]
    return appended


def refresh_roster(provider: Road511Provider) -> list[dict]:
    cams = provider.list_cameras(CAMERA_BBOX, jurisdiction=CAMERA_JURISDICTION,
                                 limit=100)
    roster = []
    for c in cams:
        img = c.provenance.metadata.get("image_url", "")
        if c.has_stream and img:
            roster.append({"id": c.camera_id, "image_url": img,
                           "name": c.provenance.metadata.get("name", "")})
    (ROOT / "camera_roster.json").write_text(json.dumps(roster, indent=1))
    return roster


def grab_snapshots(roster: list[dict], state: dict) -> int:
    if not roster:
        return 0
    got = 0
    n = len(roster)
    start = state.get("snap_cursor", 0) % n
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for i in range(SNAPSHOTS_PER_CYCLE):
        cam = roster[(start + i) % n]
        out_dir = SNAP_DIR / cam["id"]
        out_dir.mkdir(parents=True, exist_ok=True)
        try:
            req = urllib.request.Request(cam["image_url"], headers=UA)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            if len(data) > 1000:                      # skip error stubs
                (out_dir / f"{stamp}.jpg").write_bytes(data)
                got += 1
        except Exception as exc:                      # noqa: BLE001
            log(f"snapshot {cam['id']} FAILED: {exc!r}")
        time.sleep(1.0)                               # politeness to DOT host
    state["snap_cursor"] = (start + SNAPSHOTS_PER_CYCLE) % n
    return got


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    store = ObservationStore(ROOT)
    provider = Road511Provider(store=store)
    if not provider.enabled:
        sys.exit("no ROAD511_API_KEY — recorder refuses to start")

    state = load_state()
    roster: list[dict] = []
    roster_age = 1e12
    log(f"recorder START pid-file={ROOT/'recorder.pid'} "
        f"jurisdictions={JURISDICTIONS} snaps/cycle={SNAPSHOTS_PER_CYCLE}")
    (ROOT / "recorder.pid").write_text(str(__import__('os').getpid()))

    cycles = 0
    while not STOP_FILE.exists():
        t0 = time.monotonic()
        if roster_age > ROSTER_REFRESH_S:
            try:
                roster = refresh_roster(provider)
                roster_age = 0
                log(f"roster refreshed: {len(roster)} usable cameras")
            except Exception as exc:                  # noqa: BLE001
                log(f"roster refresh FAILED: {exc!r}")
        new_ev = sweep_events(provider, state)
        snaps = grab_snapshots(roster, state)
        save_state(state)
        cycles += 1
        if new_ev or cycles % 30 == 0:
            log(f"cycle {cycles}: +{new_ev} timeline events, {snaps} snapshots, "
                f"timeline={sum(1 for _ in open(TIMELINE)) if TIMELINE.exists() else 0}")
        elapsed = time.monotonic() - t0
        roster_age += max(CYCLE_S, elapsed)
        time.sleep(max(0.0, CYCLE_S - elapsed))
    log("STOP file found — recorder exiting cleanly")


if __name__ == "__main__":
    main()
