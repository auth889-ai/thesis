#!/usr/bin/env python3
"""CitySpec -> OSM -> netconvert -> a runnable SUMO scenario, for a city nobody hard-coded.

    python pipeline/city/sumo_scenario.py --city nairobi_kenya --build
    python pipeline/city/sumo_scenario.py --city nairobi_kenya --gui

The digital-twin half of the system was reachable only for the six Dhaka corridors that had been
mapped by hand. This closes that: any city the registry can instantiate can also be converted into
a SUMO network and given a runnable scenario.

WHAT IS AND IS NOT REAL HERE — the distinction the whole project rests on
    The NETWORK is real: OpenStreetMap geometry for that city, converted by SUMO's own netconvert.
    The DEMAND is not. Where no measured origin-destination data exists we generate trips with
    SUMO's randomTrips, and every artefact is stamped SYNTHETIC_WHAT_IF. Such a scenario shows
    mechanism, never a measurement of that city's traffic.

    The two calibrated cases stay separate evidence and are not produced by this path: Dhaka R1
    (frozen network, calibrated demand) and Athens pNEUMA (drone-measured vehicles, validated to
    3.0 m/s speed MAE). Nothing generated here may be quoted alongside them.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from pipeline.city.registry import CITY_DIR, registry     # noqa: E402

CALIBRATED = {"dhaka_r1", "athens_pneuma"}


def scenario_dir(city_id: str) -> Path:
    return CITY_DIR / city_id / "sumo"


def _tool(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    home = Path(sys.prefix) / "share/sumo/tools" / name
    return str(home) if home.exists() else None


def build(city_id: str, seed: int = 11, period: float = 2.0, end: int = 1800) -> dict:
    """OSM extract -> netconvert -> randomTrips -> a scenario SUMO can actually run."""
    spec = registry.get(city_id)
    if not spec:
        raise SystemExit(f"unknown city {city_id!r}; create it first")
    if not spec.bbox:
        raise SystemExit(f"{city_id} has no bounding box")
    if not shutil.which("netconvert"):
        raise SystemExit("netconvert not on PATH — SUMO tools are required")

    out = scenario_dir(city_id)
    out.mkdir(parents=True, exist_ok=True)
    s, w, n, e = spec.bbox
    osm = out / f"{city_id}.osm.xml"
    net = out / f"{city_id}.net.xml"

    # 1. OSM extract via the Overpass API (the same source the road graph came from)
    if not osm.exists():
        import urllib.request
        q = (f"[out:xml][timeout:180];(way[highway~'^(motorway|trunk|primary|secondary|"
             f"tertiary)(_link)?$']({s},{w},{n},{e}););(._;>;);out body;")
        req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                     data=q.encode(), headers={"User-Agent": "dhakaflow/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            osm.write_bytes(r.read())

    # 2. netconvert — SUMO's own converter, not a reimplementation
    if not net.exists():
        subprocess.run(["netconvert", "--osm-files", str(osm), "--output-file", str(net),
                        "--geometry.remove", "--roundabouts.guess", "--ramps.guess",
                        "--junctions.join", "--tls.guess-signals", "--tls.discard-simple",
                        "--tls.join", "--no-turnarounds", "--remove-edges.isolated",
                        "--keep-edges.by-vclass", "passenger", "--no-warnings"],
                       check=True, capture_output=True, text=True)

    # 3. demand — SYNTHETIC unless this city has measured OD data (none do on this path)
    trips, routes = out / f"{city_id}.trips.xml", out / f"{city_id}.rou.xml"
    demand_reality = "SYNTHETIC_WHAT_IF"
    if not routes.exists():
        # SUMO's randomTrips.py is not shipped with every distribution (it is absent from this
        # one), so trips are generated directly from the network with sumolib and routed by
        # duarouter. Same result, one fewer external dependency.
        import random

        import sumolib
        N0 = sumolib.net.readNet(str(net))
        usable = [e for e in N0.getEdges()
                  if e.getLength() > 50 and e.allows("passenger") and e.getOutgoing()]
        if len(usable) < 2:
            raise SystemExit(f"{city_id}: network has too few usable edges to generate demand")
        rng = random.Random(seed)
        lines, t, i = [], 0.0, 0
        while t < end:
            o, d = rng.choice(usable), rng.choice(usable)
            if o.getID() != d.getID():
                lines.append(f'    <trip id="v{i}" depart="{t:.1f}" from="{o.getID()}" '
                             f'to="{d.getID()}"/>')
                i += 1
            t += period
        trips.write_text('<routes>\n' + "\n".join(lines) + '\n</routes>\n')
        subprocess.run(["duarouter", "--net-file", str(net), "--route-files", str(trips),
                        "--output-file", str(routes), "--ignore-errors", "--no-warnings",
                        "--no-step-log", "--seed", str(seed), "--routing-threads", "4"],
                       check=True, capture_output=True, text=True)

    cfg = out / f"{city_id}.sumocfg"
    cfg.write_text(f"""<configuration>
    <input>
        <net-file value="{net.name}"/>
        <route-files value="{routes.name}"/>
    </input>
    <time><begin value="0"/><end value="{end}"/></time>
    <report><no-step-log value="true"/><duration-log.statistics value="true"/></report>
</configuration>
""")

    import sumolib
    N = sumolib.net.readNet(str(net))
    manifest = {
        "city_id": city_id, "display_name": spec.display_name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "network_reality": "REAL — OpenStreetMap geometry converted by SUMO netconvert",
        "demand_reality": demand_reality,
        "label": "SYNTHETIC_WHAT_IF",
        "warning": ("The network is real; the DEMAND is generated. This scenario demonstrates "
                    "mechanism and is not a measurement of this city's traffic. It must never be "
                    "quoted alongside the calibrated Dhaka R1 or Athens pNEUMA cases."),
        "edges": len(N.getEdges()), "junctions": len(N.getNodes()),
        "traffic_lights": len(N.getTrafficLights()),
        "total_lane_km": round(sum(e.getLength() * e.getLaneNumber() for e in N.getEdges()) / 1000, 2),
        "bbox": list(spec.bbox), "seed": seed, "horizon_s": end,
        "files": {k: str((out / v).relative_to(REPO)) for k, v in
                  {"net": net.name, "routes": routes.name, "config": cfg.name}.items()},
        "run": f"sumo -c {cfg.relative_to(REPO)}   |   sumo-gui -c {cfg.relative_to(REPO)}",
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))

    spec.sumo_network = str(net.relative_to(REPO))
    registry.save(spec)
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--city", required=True)
    p.add_argument("--build", action="store_true")
    p.add_argument("--gui", action="store_true")
    p.add_argument("--seed", type=int, default=11)
    p.add_argument("--period", type=float, default=2.0)
    p.add_argument("--end", type=int, default=1800)
    a = p.parse_args()

    if a.build:
        m = build(a.city, a.seed, a.period, a.end)
        print(f"[sumo] {m['display_name']}: {m['edges']} edges, {m['junctions']} junctions, "
              f"{m['traffic_lights']} traffic lights, {m['total_lane_km']} lane-km")
        print(f"[sumo] network: {m['network_reality']}")
        print(f"[sumo] demand:  {m['demand_reality']}  <- {m['label']}")
        print(f"[sumo] run: {m['run']}")
    if a.gui:
        cfg = scenario_dir(a.city) / f"{a.city}.sumocfg"
        if not cfg.exists():
            raise SystemExit(f"no scenario for {a.city}; run with --build first")
        subprocess.Popen(["sumo-gui", "-c", str(cfg)])
        print(f"[sumo] launched sumo-gui for {a.city}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
