"""Crash SOS, TEST mode only: the detection rule, the labelled synthetic traces for the thesis, the alert path step by
step, and the in-memory TEST alerts. Nothing here sends, dials or notifies anyone.

The rule is WreckWatch's (White, Thompson, Turner, Dougherty, Schmidt, Mobile Networks and Applications 16(3), 2011;
third_party/SOURCES.md "Crash SOS"): a crash-like jolt is an acceleration of at least 4 g, chosen there to "filter out a
drop or sudden stop", and only while the GPS speed exceeds 15 mph (24 km/h); when no speed is known the speed check is
reported as not made. The synthetic traces are ours, labelled SYNTHETIC with their parameters and seed; they are not
recordings of anything and claim nothing about real crashes.

    python -m core.safety.sos build     # research/sos/traces/*.json + SHA256SUMS, evidence/sos/results.json (+ .sha256)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path

from core.simulation.ambulance import service

G = 9.80665
THRESHOLD_G = 4.0                    # WreckWatch 2011: "ignores any acceleration events below 4G's"
MIN_SPEED_KMH = 24.1                 # WreckWatch 2011: an alarm only above 15 mph
COUNTDOWN_S = 15                     # the person's time to cancel
SOURCE = "White et al. 2011, WreckWatch, Mobile Networks and Applications 16(3): 4 g and a GPS speed over 15 mph"
RATE_HZ, SECONDS, SEED = 50, 30, 7
TRACES = service.REPO / "research/sos/traces"
EVIDENCE = service.REPO / "evidence/sos"
LABEL = "SYNTHETIC"
KINDS = {"normal_ride": "a normal ride: gravity plus road noise", "hard_brake": "a hard brake: a 1.5 s pulse to 1.8 g", "crash_jolt": "a crash-like jolt: a 120 ms spike to 6.5 g"}
# R1 (2026-10-11): a trace built from SUMO's own record of a collision in `make run-sos-collide` (scripts/live/run_sos_v2v.py --collide):
# the closing speed at the contact becomes a half-sine pulse of PULSE_S along x (its integral equals the closing speed), the collider's
# speed is the GPS speed, so the rule's speed floor applies. The pulse length is ASSUMED (the synthetic trace's 120 ms); SUMO models
# stopping, not the impact, so the pulse shape is ours. Written by the live run, read back by the same trace API as the synthetic kinds.
COLLISION_KIND = "sumo_collision"
COLLISION_LABEL = "SIMULATION"
COLLISION_TRACE = service.REPO / "evidence/live_runs/sos_v2v/collision_trace.json"
PULSE_S = 0.12
AT_S = 12.0
_TEST_ALERTS: list[dict] = []        # TEST SOS alerts raised on this machine; in memory only, gone on restart
MAX_TEST_ALERTS = 20


def magnitude_g(ax: float, ay: float, az: float) -> float:
    """|a| in g from the three axes of accelerationIncludingGravity (m/s²)."""
    return math.sqrt(ax * ax + ay * ay + az * az) / G


def detect(samples: list[dict], threshold_g: float = THRESHOLD_G, min_speed_kmh: float = MIN_SPEED_KMH) -> dict:
    """The first sample at or above the threshold (and, where a speed is known, above the speed floor). Each sample:
    {t, ax, ay, az, speed_kmh?}. Returns {detected, at_s, at_g, peak_g, speed_checked, speed_kmh}: `peak_g` is the trace's largest
    magnitude, `at_g` the magnitude of the sample that fired the rule (before 2026-10-10 the latter overwrote the former)."""
    peak, hit = 0.0, None
    for s in samples:
        m = magnitude_g(s["ax"], s["ay"], s["az"])
        peak = max(peak, m)
        if hit is None and m >= threshold_g:
            sp = s.get("speed_kmh")
            if sp is None or sp > min_speed_kmh:
                hit = {"at_s": s["t"], "at_g": round(m, 2), "speed_checked": sp is not None, "speed_kmh": sp}
    return {"detected": hit is not None, **(hit or {"at_s": None, "at_g": None, "speed_checked": any(s.get("speed_kmh") is not None for s in samples), "speed_kmh": None}),
            "peak_g": round(peak, 2)}


def synthetic(kind: str, seed: int = SEED, rate_hz: int = RATE_HZ, seconds: int = SECONDS) -> dict:
    """A labelled synthetic trace: gravity on z plus Gaussian road noise (sd 0.15 g); a hard brake adds a 1.5 s half-sine
    pulse along x peaking at 1.5 g (total about 1.8 g); a crash-like jolt adds a 120 ms spike to 6.5 g at t = 12 s."""
    rng = random.Random(f"{kind}-{seed}")
    n = rate_hz * seconds
    samples = []
    for i in range(n):
        t = i / rate_hz
        ax, ay, az = rng.gauss(0, 0.15 * G), rng.gauss(0, 0.15 * G), G + rng.gauss(0, 0.15 * G)
        if kind == "hard_brake" and 12.0 <= t < 13.5:
            ax -= 1.5 * G * math.sin(math.pi * (t - 12.0) / 1.5)
        if kind == "crash_jolt" and 12.0 <= t < 12.12:
            ax += 6.5 * G * math.sin(math.pi * (t - 12.0) / 0.12)
        samples.append({"t": round(t, 3), "ax": round(ax, 3), "ay": round(ay, 3), "az": round(az, 3)})
    return {"label": LABEL, "kind": kind, "description": KINDS[kind], "generator": "core.safety.sos.synthetic", "seed": seed, "rate_hz": rate_hz, "seconds": seconds,
            "noise_sd_g": 0.15, "units": "m/s^2, accelerationIncludingGravity", "samples": samples}


def from_collision(collider_speed_mps: float, victim_speed_mps: float, source: dict, seed: int = SEED, rate_hz: int = RATE_HZ, seconds: int = SECONDS,
                   pulse_s: float = PULSE_S, phone_speed_mps: float | None = None) -> dict:
    """A trace from SUMO's collision record: gravity on z plus the same road noise as the synthetic traces; at AT_S a half-sine pulse along x
    of `pulse_s` whose integral is the closing speed |collider - victim| (peak = pi * dv / (2 * pulse_s)); `speed_kmh` on every sample is the
    speed at the contact of the car whose phone runs the rule (`phone_speed_mps`, SUMO's collider by default), so detect() applies WreckWatch's
    speed floor. `source` records which run and which record it came from."""
    dv = abs(float(collider_speed_mps) - float(victim_speed_mps))
    peak = math.pi * dv / (2 * pulse_s)
    speed_kmh = round(float(collider_speed_mps if phone_speed_mps is None else phone_speed_mps) * 3.6, 1)
    rng = random.Random(f"{COLLISION_KIND}-{seed}")
    n = rate_hz * seconds
    samples = []
    for i in range(n):
        t = i / rate_hz
        ax, ay, az = rng.gauss(0, 0.15 * G), rng.gauss(0, 0.15 * G), G + rng.gauss(0, 0.15 * G)
        if AT_S <= t < AT_S + pulse_s:
            ax -= peak * math.sin(math.pi * (t - AT_S) / pulse_s)
        samples.append({"t": round(t, 3), "ax": round(ax, 3), "ay": round(ay, 3), "az": round(az, 3), "speed_kmh": speed_kmh})
    tr = {"label": COLLISION_LABEL, "kind": COLLISION_KIND,
          "description": f"a collision SUMO detected in the car-to-car run: closing speed {dv:.2f} m/s as a {int(pulse_s * 1000)} ms pulse ({peak / G:.1f} g), at {speed_kmh} km/h",
          "generator": "core.safety.sos.from_collision", "seed": seed, "rate_hz": rate_hz, "seconds": seconds, "noise_sd_g": 0.15, "units": "m/s^2, accelerationIncludingGravity",
          "collision": {"collider_speed_mps": float(collider_speed_mps), "victim_speed_mps": float(victim_speed_mps), "closing_speed_mps": round(dv, 3), "phone_speed_kmh": speed_kmh, "pulse_s": pulse_s,
                        "pulse_peak_g": round(peak / G, 2), "pulse_assumed": f"the {int(pulse_s * 1000)} ms half-sine is ASSUMED (the synthetic trace's length); SUMO records the speeds at the contact, not the impact",
                        "source": source},
          "samples": samples}
    tr["detection"] = detect(samples)
    return tr


def write_collision_trace(tr: dict, path: Path = COLLISION_TRACE) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(tr, indent=0)
    path.write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()


def collision_row(path: Path | None = None) -> dict:
    """The live collision trace's row for the Research table and the Emergency chip: what SUMO recorded, what the rule did; or not available."""
    path = path or COLLISION_TRACE
    if not path.exists():
        return {"available": False, "kind": COLLISION_KIND, "reason": "no collision trace yet: run `make run-sos-collide` (or `make present`)"}
    tr = json.loads(path.read_text())
    d = detect(tr["samples"])
    return {"available": True, "kind": COLLISION_KIND, "label": tr["label"], "description": tr["description"], "samples": len(tr["samples"]), "peak_g": d["peak_g"],
            "detected": d["detected"], "at_s": d["at_s"], "at_g": d["at_g"], "speed_checked": d["speed_checked"], "speed_kmh": d["speed_kmh"],
            "collision": tr["collision"], "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def plain_numbers(rows: list[dict]) -> dict:
    """The one everyday line's numbers, from the same rows as the Research table: how many traces, how many detected, the peak of each."""
    return {"traces": len(rows), "detected": sum(1 for r in rows if r["detected"]), "peak_g": {r["kind"]: r["peak_g"] for r in rows}, "threshold_g": THRESHOLD_G}


def build(traces: Path = TRACES, evidence: Path | None = EVIDENCE) -> dict:
    traces.mkdir(parents=True, exist_ok=True)
    rows, sums = [], []
    for kind in KINDS:
        tr = synthetic(kind)
        body = json.dumps(tr, indent=0)
        sha = hashlib.sha256(body.encode()).hexdigest()
        (traces / f"{kind}.json").write_text(body)
        sums.append(f"{sha}  {kind}.json")
        d = detect(tr["samples"])
        rows.append({"kind": kind, "label": LABEL, "description": KINDS[kind], "samples": len(tr["samples"]), "peak_g": d["peak_g"], "detected": d["detected"], "at_s": d["at_s"], "at_g": d["at_g"],
                     "speed_checked": d["speed_checked"], "sha256": sha,
                     "note": "no speed in the trace, so the speed floor was not applied" if not d["speed_checked"] else None})
    (traces / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    out = {"label": LABEL, "built_utc": datetime.now(timezone.utc).isoformat(), "rule": {"threshold_g": THRESHOLD_G, "min_speed_kmh": MIN_SPEED_KMH, "countdown_s": COUNTDOWN_S, "source": SOURCE},
           "generator": {"rate_hz": RATE_HZ, "seconds": SECONDS, "seed": SEED, "noise_sd_g": 0.15}, "rows": rows}
    out["plain"] = plain_numbers(rows)
    out["sha256"] = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    if evidence:
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "results.json").write_text(json.dumps(out, indent=1))
        (evidence / "results.sha256").write_text(out["sha256"] + "\n")
    return out


def read(evidence: Path = EVIDENCE) -> dict:
    f = Path(evidence) / "results.json"
    if not f.exists():
        return {"available": False, "reason": "the synthetic traces have not been built (python -m core.safety.sos build)", "rows": [], "collision": collision_row()}
    return {"available": True, **json.loads(f.read_text()), "collision": collision_row()}     # R1: the live SUMO-collision trace's row, computed now, next to the saved table


def trace(kind: str, traces: Path = TRACES, collision: Path | None = None) -> dict | None:
    if kind == COLLISION_KIND:
        collision = collision or COLLISION_TRACE
        return json.loads(collision.read_text()) if collision.exists() else None
    f = Path(traces) / f"{kind}.json"
    return json.loads(f.read_text()) if kind in KINDS and f.exists() else None


def path_steps(city_id: str, online: bool, peak_g: float | None = None) -> dict:
    """The alert path, step by step, for a TEST SOS in this city: what the device detected, the countdown, and where the
    alert would go — the app's feed and the city's ambulance number shown (never dialled) when a mobile network is there,
    the phone-to-phone mesh otherwise, with the city's own saved mesh result. Every number is from a file or the config."""
    from core.common.data import city_config
    from core.networking.mesh import results as mesh
    try:
        cfg = city_config.load(city_id)
    except KeyError:
        return {"city_id": city_id, "available": False, "reason": "no data for this city: it has no config file"}
    number = (cfg.emergency_numbers or {}).get("ambulance")
    steps = [{"step": 1, "key": "detected", "stamp": "TEST", "values": {"peak_g": peak_g, "threshold_g": THRESHOLD_G, "source": SOURCE}},
             {"step": 2, "key": "countdown", "stamp": "TEST", "values": {"seconds": COUNTDOWN_S}}]
    if online:
        steps.append({"step": 3, "key": "network", "stamp": "TEST", "values": {"number": number, "has_number": number is not None}})
    else:
        table = mesh.read(city_id)
        rows = [r for r in table.get("rows", []) if r.get("delivery_ratio")]
        if table.get("available") and rows:
            p = table.get("plain") or mesh.plain_numbers(rows, table["scope"]["vehicles_simulated"])    # the same numbers the Offline alerts page states
            steps.append({"step": 3, "key": "mesh", "stamp": "SIMULATED", "values": {"vehicles": p["vehicles"], "pct": p["reached_pct"], "delay_s": p["delay_s"], "router": p["router"]}})
        else:
            steps.append({"step": 3, "key": "mesh_none", "stamp": "TEST", "values": {}})
    steps.append({"step": 4, "key": "never_sent", "stamp": "TEST", "values": {}})
    return {"city_id": city_id, "available": True, "online": online, "steps": steps}


def raise_test(city_id: str, peak_g: float | None, online: bool, source: str = "sensor") -> dict:
    """A TEST SOS alert for the feed: kept in memory on this machine, never sent anywhere (no SNS, no SMS, no call). The peak is
    tagged by where it came from: the device's own motion sensor (real), the SOS button (real, no peak) or a replayed synthetic trace
    (simulated)."""
    from core.common import tag
    now = datetime.now(timezone.utc)
    if source == "phone-sensor":                        # the phone's real sensor (step D, 2026-10-11): TEST stays on the phone; never in the feed
        return {"id": None, "kind": "sos", "stamp": "TEST", "city_id": city_id, "stored": False, "key": "alerts.sos",
                "values": {"at": now.strftime("%H:%M UTC"), "peak_g": peak_g, "path": "network" if online else "mesh"},
                "tag": tag.real("this phone's motion sensor, TEST mode: kept on the phone, nothing sent, not in the feed", now.isoformat()), "value": peak_g, "unit": "g"}
    if source == "button":                              # the SOS button: a person's action, no measured jolt (audit 2026-10-10)
        t, peak_g = tag.real("the SOS button pressed on this device, TEST mode: nothing was sent or dialled", now.isoformat()), None
    else:
        t = tag.real("this device's motion sensor, TEST mode: nothing was sent or dialled", now.isoformat()) if source == "sensor" \
            else tag.simulated("a trace built from SUMO's own collision record (make run-sos-collide), replayed on this device, TEST mode: nothing was sent or dialled", None) if source.endswith(COLLISION_KIND) \
            else tag.simulated(f"a synthetic trace replayed on this device ({source}), TEST mode: nothing was sent or dialled", None)
    item = {"id": f"sos-test-{len(_TEST_ALERTS) + 1}-{int(now.timestamp())}", "kind": "sos", "stamp": "TEST", "city_id": city_id,
            "key": "alerts.sos", "values": {"at": now.strftime("%H:%M UTC"), "peak_g": peak_g, "path": "network" if online else "mesh"}, "tag": t, "value": peak_g, "unit": "g"}
    _TEST_ALERTS.append(item)
    del _TEST_ALERTS[:-MAX_TEST_ALERTS]
    return item


def test_items(city_id: str) -> list[dict]:
    return [i for i in _TEST_ALERTS if i["city_id"] == city_id]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    a = ap.parse_args()
    got = build()
    print(json.dumps({"plain": got["plain"], "sha256": got["sha256"], "rows": [(r["kind"], r["peak_g"], r["detected"], r["at_s"]) for r in got["rows"]]}, indent=1))
