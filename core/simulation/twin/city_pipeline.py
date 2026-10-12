#!/usr/bin/env python3
"""City config -> OpenStreetMap extract -> SUMO network -> random demand, one command per city.

    python -m core.simulation.twin.city_pipeline --city <city_id>

The city is whatever config/cities/<city_id>.yaml says. A city whose config gives a bounding box is built with the
same steps as `scenario_builder` (Overpass extract, SUMO's netconvert with the osmWebWizard options, SUMO's
randomTrips); a left-driving city adds `--lefthand`. A city whose config names a prebuilt network is not rebuilt:
its files are checked against the recorded hashes, and if the config also has a `build` block, new uncalibrated demand
is generated on that network. Buildings are not fetched: the map draws Overture Maps' worldwide buildings. Every city
that gets demand also gets the MANIFEST.json the live twin looks for. A city with no box is refused, with the reason.

The network and demand go to data/cities/<city_id>/sumo/ (not tracked). What is tracked is the evidence:
evidence/cities/<city_id>/build.json with the OSM data date, the hash of every file, the commands and the SUMO
version, beside build.log. The network is real geometry; the demand is generated (SYNTHETIC_WHAT_IF) and is never a
measurement of the city's traffic.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from core.common.data import city_config
from core.common.paths import REPO
from core.simulation.twin import scenario_builder as sb

CITY_DIR = REPO / "data/cities"
EVIDENCE_DIR = REPO / "evidence/cities"


def sha256(path: Path, uncompress: bool = False) -> str:
    h = hashlib.sha256()
    with (gzip.open(path, "rb") if uncompress else open(path, "rb")) as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def osm_data_date(osm: Path) -> str | None:
    """The `osm_base` timestamp Overpass stamps on an extract: the moment of the OSM data it answered from."""
    with open(osm, "r", errors="ignore") as fh:
        m = re.search(r'osm_base="([^"]+)"', fh.read(4096))
    return m.group(1) if m else None


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def _sumo_version() -> str:
    return subprocess.run(["sumo", "--version"], capture_output=True, text=True).stdout.splitlines()[0]


def verify_prebuilt(cfg: city_config.CityConfig) -> dict:
    """A frozen network is evidence already; this checks it is the recorded one and records that."""
    pre = cfg.sumo.prebuilt
    net, routes = REPO / pre.network, REPO / pre.routes
    found = {"network_sha256": sha256(net, uncompress=net.suffix == ".gz"), "routes_sha256": sha256(routes)}
    wrong = [k for k, v in found.items() if v != getattr(pre, k)]
    if wrong:
        raise SystemExit(f"{cfg.city_id}: {', '.join(wrong)} differ from the config; the frozen files have changed")
    return {"mode": "prebuilt", "network_id": pre.network_id, "network": pre.network, "routes": pre.routes, **found,
            "demand_scale": pre.demand_scale, "verified": "both hashes equal the config's"}


def build_network(cfg: city_config.CityConfig, out: Path, log: list[str]) -> dict:
    if cfg.bounding_box is None:
        raise SystemExit(f"{cfg.city_id}: no bounding box in its config, so no network can be built (see the config for why)")
    if cfg.sumo.build is None:
        raise SystemExit(f"{cfg.city_id}: its config has neither sumo.prebuilt nor sumo.build")
    if not shutil.which("netconvert"):
        raise SystemExit("netconvert not on PATH — SUMO tools are required")
    b, name = cfg.sumo.build, cfg.city_id
    out.mkdir(parents=True, exist_ok=True)
    osm, net = out / f"{name}.osm.xml", out / f"{name}.net.xml"
    trips, routes = out / f"{name}.trips.xml", out / f"{name}.rou.xml"
    query = sb.fetch_osm(cfg.bounding_box.tuple, osm)
    log.append(f"overpass {sb.OVERPASS}\n  {query}\n  -> {osm.name} ({osm.stat().st_size} bytes)")
    net_opts = sb.run_netconvert(osm, net, lefthand=cfg.drive_side == "left")
    log.append("netconvert --osm-files " + osm.name + " --output-file " + net.name + " " + " ".join(net_opts))
    trip_opts = sb.run_random_trips(net, trips, routes, b.seed, b.period_s, b.horizon_s)
    log.append("randomTrips.py " + " ".join(o if o not in (str(net), str(trips), str(routes)) else Path(o).name for o in trip_opts))
    cfg_file, _ = sb.write_sumocfg(out, name, net, routes, b.horizon_s)
    import sumolib
    graph = sumolib.net.readNet(str(net))
    return {"mode": "built", "bounding_box": list(cfg.bounding_box.tuple), "drive_side": cfg.drive_side,
            "osm": {"source": "OpenStreetMap contributors (ODbL), Overpass API", "endpoint": sb.OVERPASS, "query": query,
                    "data_date": osm_data_date(osm), "file": _rel(osm), "sha256": sha256(osm), "bytes": osm.stat().st_size},
            "network": {"file": _rel(net), "sha256": sha256(net), "netconvert_options": net_opts, "edges": len(graph.getEdges()),
                        "junctions": len(graph.getNodes()), "traffic_lights": len(graph.getTrafficLights())},
            "demand": {"file": _rel(routes), "sha256": sha256(routes), "label": "SYNTHETIC_WHAT_IF", "seed": b.seed,
                       "period_s": b.period_s, "horizon_s": b.horizon_s, "randomtrips_options": [o for o in trip_opts if not o.startswith("/")],
                       "vehicles": len(re.findall(r"<vehicle ", routes.read_text()))},
            "config": _rel(cfg_file), "run": f"sumo -c {_rel(cfg_file)}"}


def generated_demand(cfg: city_config.CityConfig, out: Path, log: list[str]) -> dict:
    """New generated demand on a prebuilt network (the network is not rebuilt; its old demand file is left alone)."""
    b, name = cfg.sumo.build, cfg.city_id
    out.mkdir(parents=True, exist_ok=True)
    net = REPO / cfg.sumo.prebuilt.network
    trips, routes = out / f"{name}.trips.xml", out / f"{name}.rou.xml"
    trip_opts = sb.run_random_trips(net, trips, routes, b.seed, b.period_s, b.horizon_s)
    log.append("randomTrips.py " + " ".join(o if o not in (str(net), str(trips), str(routes)) else Path(o).name for o in trip_opts))
    import sumolib
    graph = sumolib.net.readNet(str(net))
    return {"network": {"file": _rel(net), "edges": len(graph.getEdges()), "junctions": len(graph.getNodes()), "traffic_lights": len(graph.getTrafficLights())},
            "demand": {"file": _rel(routes), "sha256": sha256(routes), "label": "SYNTHETIC_WHAT_IF", "calibration": "none", "seed": b.seed,
                       "period_s": b.period_s, "horizon_s": b.horizon_s, "randomtrips_options": [o for o in trip_opts if not o.startswith("/")],
                       "vehicles": len(re.findall(r"<vehicle ", routes.read_text()))}}


MIX_MARK = "<!-- vehicle mix applied -->"


def apply_mix(cfg: city_config.CityConfig, routes: Path, net_file: Path, seed: int, log: list[str]) -> dict | None:
    """Give each generated vehicle one of the city's vehicle classes, drawn at the shares the city's config states.

    The routes were made for passenger cars. A vehicle keeps its route and gets a class only if every section of that
    route and every turn between them admits the class (a bus is not put on a road or a turn closed to buses); when no remaining route admits a class, fewer
    vehicles get it, and the shares achieved are reported beside the shares asked for. Classes are SUMO's own, with
    SUMO's default parameters. A city with no `vehicle_mix` keeps one class, and None is returned."""
    mix = cfg.vehicle_mix
    if mix is None:
        return None
    import random
    import xml.etree.ElementTree as ET
    import sumolib
    text = routes.read_text()
    tree = ET.ElementTree(ET.fromstring(text))
    root = tree.getroot()
    vehicles = [v for v in root.findall("vehicle") if v.find("route") is not None]      # a vehicle without its own route is left as it is
    if not vehicles:
        return None
    if MIX_MARK not in text:
        net = sumolib.net.readNet(str(net_file))
        rng = random.Random(seed)
        def admits(v, vclass: str) -> bool:                                   # every section, and every turn from one to the next
            path = [net.getEdge(e) for e in v.find("route").get("edges").split()]
            return all(e.allows(vclass) for e in path) and all(b in a.getAllowedOutgoing(vclass) for a, b in zip(path, path[1:]))
        want = {c.name: round(len(vehicles) * c.share_pct / 100) for c in mix.classes}
        left = list(vehicles)
        rng.shuffle(left)
        for c in sorted(mix.classes, key=lambda c: c.share_pct):              # the rarest class chooses first
            fit = [v for v in left if admits(v, c.sumo_class)][:want[c.name]]
            for v in fit:
                v.set("type", c.name)
            chosen = set(map(id, fit))
            left = [v for v in left if id(v) not in chosen]
        common = max(mix.classes, key=lambda c: c.share_pct)
        for v in left:                                                         # rounding leftovers and classes that found no admitting route
            v.set("type", common.name)
        for i, c in enumerate(mix.classes):
            root.insert(i, ET.Element("vType", {"id": c.name, "vClass": c.sumo_class}))
        ET.indent(tree)
        routes.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + MIX_MARK + "\n" + ET.tostring(root, encoding="unicode") + "\n")
    got = {c.name: sum(1 for v in vehicles if v.get("type") == c.name) for c in mix.classes}
    out = {"source": mix.source, "citation": mix.citation, "simulated_as": mix.simulated_as, "seed": seed, "vehicles": len(vehicles),
           "classes": [{"name": c.name, "sumo_class": c.sumo_class, "asked_pct": c.share_pct, "vehicles": got[c.name], "achieved_pct": round(100 * got[c.name] / len(vehicles), 2)} for c in mix.classes]}
    log.append("vehicle mix: " + ", ".join(f"{c['name']} {c['achieved_pct']} % (asked {c['asked_pct']})" for c in out["classes"]))
    return out


def buildings(cfg: city_config.CityConfig, out: Path, log: list[str]) -> dict | None:
    """Where this city's 3D buildings come from. They are not fetched per city any more: the map draws Overture Maps'
    worldwide buildings directly, so the build only records which release that is."""
    from core.simulation.twin import buildings_source
    src = buildings_source.source()
    log.append(f"buildings: not fetched; drawn by the map from Overture Maps release {src['release']} ({src['url']})")
    return {"source": "Overture Maps buildings theme (ODbL), drawn directly by the map", "release": src["release"], "url": src["url"], "found": src["found"], "file": None, "count": None}


def write_manifest(cfg: city_config.CityConfig, out: Path, result: dict) -> Path:
    """The file the live twin looks for: which network and which demand a city runs on, and what they are."""
    manifest = {"city_id": cfg.city_id, "display_name": cfg.label(), "generated_utc": datetime.now(timezone.utc).isoformat(),
                "network_reality": "REAL — OpenStreetMap geometry converted by SUMO netconvert", "demand_reality": "SYNTHETIC_WHAT_IF", "label": "SYNTHETIC_WHAT_IF",
                "warning": "The network is real; the demand is generated and uncalibrated. This is a simulation, not a measurement of this city's traffic.",
                "edges": result["network"]["edges"], "junctions": result["network"]["junctions"], "traffic_lights": result["network"]["traffic_lights"],
                "bbox": list(cfg.bounding_box.tuple), "seed": cfg.sumo.build.seed, "horizon_s": cfg.sumo.build.horizon_s,
                "files": {"net": result["network"]["file"], "routes": result["demand"]["file"], "buildings": (result.get("buildings") or {}).get("file")}}
    path = out / "MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=1))
    return path


def run(city_id: str, config_dir: Path = city_config.CONFIG_DIR, city_dir: Path = CITY_DIR, evidence_dir: Path = EVIDENCE_DIR) -> dict:
    cfg = city_config.load(city_id, config_dir)
    log: list[str] = []
    out = city_dir / city_id / "sumo"
    result: dict = {}
    if cfg.sumo.prebuilt:
        result = verify_prebuilt(cfg)
        if cfg.sumo.build:                          # the frozen network with newly generated, uncalibrated demand
            result = {"mode": "prebuilt network, generated demand", "prebuilt": result, **generated_demand(cfg, out, log)}
    else:
        result = build_network(cfg, out, log)
    if "demand" in result:
        mixed = apply_mix(cfg, REPO / result["demand"]["file"], REPO / result["network"]["file"], result["demand"]["seed"], log)
        if mixed:
            result["demand"].update(vehicle_mix=mixed, sha256=sha256(REPO / result["demand"]["file"]))
        result["buildings"] = buildings(cfg, out, log)
        if cfg.bounding_box is not None:
            result["manifest"] = _rel(write_manifest(cfg, out, result))
    record = {"city_id": city_id, "display_name": cfg.label(), "config": _rel(Path(config_dir) / f"{city_id}.yaml"),
              "generated_utc": datetime.now(timezone.utc).isoformat(), "sumo": _sumo_version(), **result}
    ev = Path(evidence_dir) / city_id
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "build.json").write_text(json.dumps(record, indent=1) + "\n")
    (ev / "build.log").write_text("\n".join(log or [f"prebuilt network verified: {json.dumps(result)}"]) + "\n")
    return record


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", required=True, help="a city id with a file in config/cities/")
    r = run(p.parse_args().city)
    if r["mode"] == "prebuilt":
        print(f"[city] {r['display_name']}: prebuilt network {r['network_id']} verified against its recorded hashes")
    else:
        n, d, b = r["network"], r["demand"], r.get("buildings") or {}
        print(f"[city] {r['display_name']} ({r['mode']}): {n['edges']} edges, {n['junctions']} junctions, {n['traffic_lights']} traffic lights, "
              f"{d['vehicles']} generated vehicles ({d['label']}); buildings drawn from Overture release {b.get('release')}")
    print(f"[city] evidence: {_rel(EVIDENCE_DIR / r['city_id'] / 'build.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
