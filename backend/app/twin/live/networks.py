"""The networks the twin can run, and the provenance facts recorded for every run (validation
status, file hashes, the SUMO version, the scenario label)."""
from __future__ import annotations

import json
from pathlib import Path

from app import evidence_paths as config

from .settings import DHAKA_CENTER

VALIDATION_METRICS = config.REPO / "results/final_validation/metrics.json"
_FILE_HASH: dict[str, str] = {}


def dhaka_validation() -> dict:
    """The currently recorded local validation status, without turning an attempted calibration
    into a claim. A missing or failing evidence file is explicitly not validated."""
    try:
        evidence = json.loads(VALIDATION_METRICS.read_text())
        checks = evidence.get("checks") or {}
        passed = bool(checks) and all(checks.values())
        return {"status": "VALIDATED" if passed else "NOT_VALIDATED", "passed": passed,
                "checks": checks, "speed_mae_ms": evidence.get("speed_mae_ms"),
                "travel_time_median_rel_err": evidence.get("travel_time_median_rel_err"),
                "teleports": evidence.get("teleports"), "collisions": evidence.get("collisions"),
                "evidence_file": str(VALIDATION_METRICS.relative_to(config.REPO))}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "UNAVAILABLE", "passed": False, "checks": {},
                "evidence_file": str(VALIDATION_METRICS.relative_to(config.REPO))}


def file_hash(path, n: int = 12) -> str | None:
    """sha256 prefix of a file, cached by path+mtime (network and demand hashes for provenance)."""
    import hashlib
    try:
        p = Path(path); key = f"{p}:{p.stat().st_mtime_ns}"
        if key not in _FILE_HASH:
            _FILE_HASH[key] = hashlib.sha256(p.read_bytes()).hexdigest()[:n]
        return _FILE_HASH[key]
    except OSError:
        return None


def sumo_version() -> str:
    import subprocess
    try:
        return subprocess.run(["sumo", "--version"], capture_output=True, text=True, timeout=20).stdout.splitlines()[0].strip()
    except Exception as exc:                            # noqa: BLE001
        return f"unknown ({exc})"


def scenario_label(netinfo: dict) -> dict:
    """Where the running scenario's road network and demand come from — always visible."""
    if netinfo.get("live_coupled"):
        validation = dhaka_validation()
        if validation["passed"]:
            return {"demand": "CONFIGURED DHAKA DEMAND (LOCALLY VALIDATED)", "network": "FROZEN OSM ROAD NETWORK (Dhaka R1)",
                    "note": "local validation passed; continuous mode reads corridor state from the provider", "validation": validation}
        return {"demand": "SIMULATED DHAKA DEMAND (NOT LOCALLY VALIDATED)", "network": "FROZEN OSM ROAD NETWORK (Dhaka R1)",
                "note": "the recorded local validation checks have not passed; use this as a simulated what-if, not a live-road forecast",
                "validation": validation}
    d = str(netinfo.get("demand") or "SYNTHETIC_WHAT_IF")
    return {"demand": "UPLOADED FLOW DATA" if d.startswith("UPLOADED") else "SYNTHETIC WHAT-IF DEMAND",
            "network": "REAL OSM ROAD NETWORK", "note": "randomTrips demand (osmWebWizard parameters) is NOT real traffic; it demonstrates mechanism only"}


def networks() -> list[dict]:
    """Every network the twin can run: Dhaka R1 plus any city generated from OSM."""
    from app.data.cities import CITY_DIR
    validation = dhaka_validation()
    label = "Dhaka R1 (locally validated)" if validation["passed"] else "Dhaka R1 (simulation; validation pending)"
    out = [{"id": "dhaka_r1", "name": label, "demand": "CALIBRATION_ATTEMPTED",
            "center": list(DHAKA_CENTER), "live_coupled": True,
            "validation": validation,
            "note": "frozen OSM network; live corridor state comes from Google when continuous"}]
    if CITY_DIR.exists():
        for d in sorted(CITY_DIR.iterdir()):
            m = d / "sumo" / "MANIFEST.json"
            if m.exists():
                try:
                    man = json.loads(m.read_text())
                except json.JSONDecodeError:
                    continue
                s_, w, n, e = man["bbox"]
                out.append({"id": man["city_id"], "name": man.get("display_name") or man["city_id"],
                            "demand": man["demand_reality"], "center": [(w + e) / 2, (s_ + n) / 2],
                            "bbox": man["bbox"], "edges": man["edges"], "traffic_lights": man["traffic_lights"],
                            "live_coupled": False, "generated_utc": man["generated_utc"],
                            "note": man["warning"]})
    return out


def resolve_network(network: str) -> dict:
    from app.twin import runtime as pr
    if network in ("dhaka_r1", "", None):
        return {"id": "dhaka_r1", "net": Path(pr.DEFAULT_NET), "routes": Path(pr.DEFAULT_ROUTES),
                "demand": "CALIBRATION_ATTEMPTED", "center": DHAKA_CENTER, "live_coupled": True,
                "validation": dhaka_validation()}
    from app.twin.scenario_builder import scenario_dir
    m = scenario_dir(network) / "MANIFEST.json"
    if not m.exists():
        raise ValueError(f"no generated network for {network!r}; generate it first")
    man = json.loads(m.read_text())
    s_, w, n, e = man["bbox"]
    return {"id": network, "net": config.REPO / man["files"]["net"], "routes": config.REPO / man["files"]["routes"],
            "demand": man["demand_reality"], "center": ((w + e) / 2, (s_ + n) / 2), "live_coupled": False}
