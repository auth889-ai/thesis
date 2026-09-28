#!/usr/bin/env python3
"""CitySpec -> OSM -> netconvert -> a runnable SUMO scenario, for a city nobody hard-coded.

    python src/pipeline/city/sumo_scenario.py --city nairobi_kenya --build
    python src/pipeline/city/sumo_scenario.py --city nairobi_kenya --gui

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

from traffictwin.paths import REPO
sys.path.insert(0, str(REPO))

from traffictwin.data.cities import CITY_DIR, registry     # noqa: E402

CALIBRATED = {"dhaka_r1", "athens_pneuma"}


def scenario_dir(city_id: str) -> Path:
    return CITY_DIR / city_id / "sumo"


def sumo_tools_dir() -> Path:
    """SUMO's own tools directory: the pinned checkout when present, else the pip package's copy
    of the same release (eclipse-sumo==1.27.1 == tag v1_27_1)."""
    pinned = Path.home() / ".dhakaflow/upstream/sumo/tools"
    if (pinned / "randomTrips.py").exists() and (pinned.parent / "data/typemap/osmNetconvert.typ.xml").exists():
        return pinned
    import sumo as _sumo
    return Path(_sumo.__file__).parent / "tools"


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
        # every drivable road class, as osmGet.py / the wizard fetch the whole extract; the passenger
        # network is then selected by netconvert exactly as osmBuild does
        q = (f"[out:xml][timeout:180];(way[highway~'^(motorway|trunk|primary|secondary|tertiary|unclassified|"
             f"residential|living_street)(_link)?$']({s},{w},{n},{e}););(._;>;);out body;")
        req = urllib.request.Request("https://overpass-api.de/api/interpreter",
                                     data=q.encode(), headers={"User-Agent": "dhakaflow/1.0"})
        with urllib.request.urlopen(req, timeout=300) as r:
            osm.write_bytes(r.read())

    # 2. netconvert — SUMO's own converter, with the options and OSM typemap that SUMO's own
    #    osmWebWizard / osmBuild use (tools/osmBuild.py DEFAULT_NETCONVERT_OPTS + the wizard's
    #    --tls.default-type actuated), restricted to the passenger network as the wizard does
    tools = sumo_tools_dir()
    typemap = tools.parent / "data" / "typemap" / "osmNetconvert.typ.xml"
    netconvert_opts = ["--geometry.remove", "--ramps.guess", "--junctions.join", "--tls.guess-signals", "--tls.discard-simple",
                       "--tls.join", "--output.original-names", "--output.street-names",      # osmBuild.DEFAULT_NETCONVERT_OPTS
                       "--tls.default-type", "actuated",                                        # osmWebWizard.build
                       # cities whose OSM carries no highway=traffic_signals nodes would get no signals at all;
                       # netconvert's own guess (documented option) adds them at busy junctions — recorded below
                       "--tls.guess", "--tls.guess.threshold", "30",
                       "--keep-edges.by-vclass", "passenger", "--remove-edges.isolated", "--no-warnings"]
    if not net.exists():
        subprocess.run(["netconvert", "--osm-files", str(osm), "--output-file", str(net)]
                       + (["-t", str(typemap)] if typemap.exists() else []) + netconvert_opts,
                       check=True, capture_output=True, text=True)

    # 3. demand — SYNTHETIC unless this city has measured OD data (none do on this path):
    #    SUMO's own randomTrips.py, called the way osmWebWizard calls it for passenger cars
    trips, routes = out / f"{city_id}.trips.xml", out / f"{city_id}.rou.xml"
    demand_reality = "SYNTHETIC_WHAT_IF"
    random_trips = tools / "randomTrips.py"
    rt_opts = ["-n", str(net), "-o", str(trips), "-r", str(routes), "-b", "0", "-e", str(end), "-p", str(period), "--seed", str(seed),
               "--fringe-factor", "5", "--fringe-start-attributes", 'departSpeed="max"',           # osmWebWizard CP / passenger
               "--vehicle-class", "passenger", "--vclass", "passenger", "--prefix", "veh",
               "--min-distance", "300", "--min-distance.fringe", "10", "--allow-fringe.min-length", "1000", "--lanes",
               "--trip-attributes", 'departLane="best"', "--validate"]
    if not routes.exists():
        r = subprocess.run([sys.executable, str(random_trips)] + rt_opts, check=False, capture_output=True, text=True, cwd=out)
        if r.returncode != 0 or not routes.exists():
            raise SystemExit(f"{city_id}: randomTrips.py failed: {(r.stderr or r.stdout)[-600:]}")

    # 4. the wizard's view settings, so sumo-gui opens with the 'real world' scheme
    view = out / "osm.view.xml"
    # the wizard's scheme, plus SUMO's own vehicle exaggeration so cars are visible at city scale
    view.write_text('<viewsettings>\n    <scheme name="real world"/>\n    <delay value="20"/>\n'
                    '    <vehicles vehicleMode="0" vehicleQuality="2" vehicle_minSize="4.00" vehicle_exaggeration="3.00" vehicle_constantSize="0" showBlinker="1"/>\n'
                    '    <junctions drawShape="true" tlsPhaseIndex="true"/>\n</viewsettings>\n')
    cfg = out / f"{city_id}.sumocfg"
    cfg.write_text(f"""<configuration>
    <input>
        <net-file value="{net.name}"/>
        <route-files value="{routes.name}"/>
    </input>
    <time><begin value="0"/><end value="{end}"/></time>
    <processing><ignore-route-errors value="true"/></processing>
    <routing><device.rerouting.adaptation-steps value="18"/><device.rerouting.adaptation-interval value="10"/></routing>
    <report><verbose value="true"/><duration-log.statistics value="true"/><no-step-log value="true"/></report>
    <gui_only><gui-settings-file value="{view.name}"/></gui_only>
</configuration>
""")
    process = {"upstream": "eclipse-sumo/sumo", "tag": "v1_27_1", "sha": "7717f2379d9e314a0c81c5cec748444de06a2a91", "license": "EPL-2.0",
               "followed": ["tools/osmWebWizard.py (build: netconvert options, randomTrips passenger call, sumocfg + osm.view.xml)",
                            "tools/osmBuild.py (DEFAULT_NETCONVERT_OPTS, typemap osmNetconvert.typ.xml)", "tools/randomTrips.py (demand)"],
               "netconvert_options": netconvert_opts, "deviation_from_wizard": "--tls.guess (documented netconvert option) so cities without tagged signals still get them; vehicleExaggeration=3 in the view settings", "randomtrips_options": rt_opts, "osm_source": "Overpass API extract of the bbox (highway=motorway…tertiary)"}

    import sumolib
    N = sumolib.net.readNet(str(net))
    manifest = {
        "city_id": city_id, "display_name": spec.display_name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "network_reality": "REAL — OpenStreetMap geometry converted by SUMO netconvert",
        "process": process, "gui_settings": str(view.relative_to(REPO)),
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
