"""Vehicle movement from a city's built SUMO network to an ns2 trace (SUMO's own traceExporter).

Reads the city config and the network; writes only under research/mesh_pons/. The demand is
SUMO's randomTrips with the city's `sumo.build` values: SYNTHETIC and UNCALIBRATED.

PONS's Ns2Movement parks a node at its first position before its first entry and at its last
position afterwards, so a vehicle that is absent for part of the window would become a parked
relay that does not exist. Only vehicles present at every step of the window are therefore kept
(a selection; positions are not changed) and time is shifted so the window starts at 0.
"""
import argparse, hashlib, json, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd, log):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, cwd=HERE / "work")
    log.write(f"$ {' '.join(str(c) for c in cmd)}\n{r.stdout}{r.stderr}\n")
    if r.returncode != 0:
        raise SystemExit(f"failed: {cmd[0]} (see log)\n{(r.stderr or r.stdout)[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(HERE / "configs/dhaka.yaml"))
    ap.add_argument("--sumo-python", default=sys.executable, help="python used for SUMO's tools")
    ap.add_argument("--sumo-tools", required=True, help="directory holding randomTrips.py and traceExporter.py")
    a = ap.parse_args()
    exp = yaml.safe_load(open(a.config))
    city_id = exp["city_id"]
    city = yaml.safe_load(open(ROOT / "config/cities" / f"{city_id}.yaml"))
    sumo = (city.get("sumo") or {})
    if "prebuilt" not in sumo or "build" not in sumo:
        raise SystemExit(f"no data for this city: {city_id} has no built SUMO network / build settings in its config")
    net = ROOT / sumo["prebuilt"]["network"]
    seed, period, horizon = sumo["build"]["seed"], sumo["build"]["period_s"], sumo["build"]["horizon_s"]
    begin, end = exp["window"]["begin_s"], exp["window"]["end_s"]
    work, tools = HERE / "work", Path(a.sumo_tools)
    work.mkdir(exist_ok=True)
    trips, routes = work / f"{city_id}.trips.xml", work / f"{city_id}.rou.xml"
    fcd, fcd_win, ns2 = work / f"{city_id}.fcd.xml", work / f"{city_id}.window.fcd.xml", work / f"{city_id}.ns2.tcl"

    with open(HERE / "evidence" / "export_movement.log", "w") as log:
        # the same randomTrips call as core/simulation/twin/scenario_builder.py run_random_trips (osmWebWizard passenger)
        run([a.sumo_python, tools / "randomTrips.py", "-n", net, "-o", trips, "-r", routes, "-b", 0, "-e", horizon,
             "-p", period, "--seed", seed, "--fringe-factor", 5, "--fringe-start-attributes", 'departSpeed="max"',
             "--vehicle-class", "passenger", "--vclass", "passenger", "--prefix", "veh", "--min-distance", 300,
             "--min-distance.fringe", 10, "--allow-fringe.min-length", 1000, "--lanes",
             "--trip-attributes", 'departLane="best"', "--validate"], log)
        run(["sumo", "-n", net, "-r", routes, "--begin", 0, "--end", horizon, "--seed", seed,
             "--fcd-output", fcd, "--no-step-log", "--no-warnings"], log)

        # pass 1: who is present at every step of [begin, end)
        present, steps, seen = {}, 0, set()
        for _, el in ET.iterparse(fcd, events=("end",)):
            if el.tag == "timestep":
                t = float(el.get("time"))
                if begin <= t < end:
                    steps += 1
                    for v in el.findall("vehicle"):
                        present[v.get("id")] = present.get(v.get("id"), 0) + 1
                        seen.add(v.get("id"))
                el.clear()
        keep = {v for v, n in present.items() if n == steps}
        # pass 2: the window, kept vehicles only, time shifted to start at 0
        with open(fcd_win, "w") as out:
            out.write("<fcd-export>\n")
            for _, el in ET.iterparse(fcd, events=("end",)):
                if el.tag == "timestep":
                    t = float(el.get("time"))
                    if begin <= t < end:
                        out.write(f'  <timestep time="{t - begin:.2f}">\n')
                        for v in el.findall("vehicle"):
                            if v.get("id") in keep:
                                out.write("    " + ET.tostring(v, encoding="unicode").strip() + "\n")
                        out.write("  </timestep>\n")
                    el.clear()
            out.write("</fcd-export>\n")
        run([a.sumo_python, tools / "traceExporter.py", "--fcd-input", fcd_win, "--ns2mobility-output", ns2], log)

    meta = {"city": city_id, "network": sumo["prebuilt"]["network"], "network_sha256_gz_file": sha256(net),
            "network_sha256_uncompressed_in_city_config": sumo["prebuilt"]["network_sha256"],
            "demand": {"kind": "SYNTHETIC randomTrips, UNCALIBRATED", "seed": seed, "period_s": period, "horizon_s": horizon},
            "sumo_version": subprocess.run(["sumo", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
            "window_s": [begin, end], "window_steps": steps, "vehicles_seen_in_window": len(seen),
            "vehicles_kept_present_whole_window": len(keep),
            "routes_sha256": sha256(routes), "ns2_trace": str(ns2.relative_to(HERE)), "ns2_trace_sha256": sha256(ns2)}
    (HERE / "evidence" / "movement.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
