from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd

from .utils import find_sumo_home, run, which_or_fail, write_json


def detector_bbox(locations_csv: str, buffer_km: float) -> tuple[float, float, float, float]:
    df = pd.read_csv(locations_csv).dropna(subset=["longitude", "latitude"])
    if df.empty:
        raise RuntimeError("No locations available for OSM clipping.")
    mean_lat = float(df["latitude"].mean())
    lat_buffer = buffer_km / 111.0
    lon_buffer = buffer_km / max(1.0, 111.0 * abs(__import__("math").cos(__import__("math").radians(mean_lat))))
    return (
        float(df["longitude"].min() - lon_buffer),
        float(df["latitude"].min() - lat_buffer),
        float(df["longitude"].max() + lon_buffer),
        float(df["latitude"].max() + lat_buffer),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pbf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--locations")
    parser.add_argument("--clip", action="store_true")
    parser.add_argument("--buffer-km", type=float, default=4.0)
    parser.add_argument("--demo-nodes")
    parser.add_argument("--demo-edges")
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "network_build.log"
    net = out / "berlin.net.xml"

    if args.demo_nodes and args.demo_edges:
        run([
            which_or_fail("netconvert"), "--node-files", args.demo_nodes,
            "--edge-files", args.demo_edges, "--output-file", str(net),
            "--no-turnarounds", "true",
        ], log=log)
        write_json(out / "network_manifest.json", {"mode": "demo", "net": str(net)})
        return

    which_or_fail("osmium")
    source_pbf = Path(args.pbf)
    working_pbf = source_pbf
    bbox = None
    if args.clip:
        if not args.locations:
            raise ValueError("--locations is required with --clip")
        bbox = detector_bbox(args.locations, args.buffer_km)
        working_pbf = out / "berlin_clipped.osm.pbf"
        run([
            "osmium", "extract", "-b", ",".join(map(str, bbox)),
            str(source_pbf), "-o", str(working_pbf), "--overwrite",
        ], log=out / "osmium_extract.log")

    osm_xml = out / "berlin.osm.xml"
    run(["osmium", "cat", str(working_pbf), "-o", str(osm_xml), "--overwrite"],
        log=out / "osmium_convert.log")

    sumo_home = find_sumo_home()
    typemap = sumo_home / "data/typemap"
    type_files = [
        typemap / "osmNetconvert.typ.xml",
        typemap / "osmNetconvertUrbanDe.typ.xml",
    ]
    cmd = [
        which_or_fail("netconvert"),
        "--osm-files", str(osm_xml),
        "--output-file", str(net),
        "--geometry.remove", "true",
        "--roundabouts.guess", "true",
        "--ramps.guess", "true",
        "--junctions.join", "true",
        "--tls.guess-signals", "true",
        "--tls.discard-simple", "true",
        "--tls.join", "true",
        "--keep-edges.by-vclass", "passenger",
        "--remove-edges.isolated", "true",
        "--osm.all-attributes", "true",
        "--output.street-names", "true",
        "--output.original-names", "true",
        "--no-turnarounds", "true",
    ]
    existing_types = [str(p) for p in type_files if p.exists()]
    if existing_types:
        cmd += ["--type-files", ",".join(existing_types)]
    run(cmd, log=log)
    write_json(out / "network_manifest.json", {
        "pbf": str(source_pbf), "working_pbf": str(working_pbf),
        "osm_xml": str(osm_xml), "net": str(net), "bbox": bbox,
        "note": "Exact paper OSM snapshot unavailable; inspect import warnings and manually patch if needed.",
    })


if __name__ == "__main__":
    main()
