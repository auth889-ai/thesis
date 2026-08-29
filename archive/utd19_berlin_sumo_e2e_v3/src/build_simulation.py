from __future__ import annotations

import argparse
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from .utils import write_json


def copy(src: str, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--routes", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--begin", type=int, default=0)
    parser.add_argument("--end", type=int, default=86400)
    parser.add_argument("--step-length", type=float, default=1)
    parser.add_argument("--time-to-teleport", type=int, default=900)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gui-delay-ms", type=int, default=20)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    net = copy(args.net, out / "berlin.net.xml")
    routes = copy(args.routes, out / "calibrated.rou.xml")
    mapping = pd.read_csv(args.mapping).dropna(subset=["edge_id"])
    edges = sorted(mapping["edge_id"].astype(str).unique())

    additional = ET.Element("additional")
    ET.SubElement(
        additional, "edgeData", id="monitoredEdgeCounts",
        file="simulated_edge_counts.xml", period="3600",
        begin=str(args.begin), end=str(args.end),
        edges=" ".join(edges), excludeEmpty="false", trackVehicles="true",
    )
    for row in mapping.drop_duplicates("detid").itertuples(index=False):
        try:
            if hasattr(row, "lane_id") and pd.notna(row.lane_id):
                length_m = float(getattr(row, "length_km", 0) or 0) * 1000.0
                downstream_m = float(getattr(row, "pos_km", 0) or 0) * 1000.0
                position_m = max(0.1, length_m - downstream_m) if length_m else 1.0
                ET.SubElement(
                    additional, "poi", id=f"detector_{row.detid}", type="traffic_detector",
                    lane=str(row.lane_id), pos=f"{position_m:.2f}",
                    color="255,0,0", layer="100", width="5", height="5",
                )
            elif hasattr(row, "longitude") and hasattr(row, "latitude"):
                ET.SubElement(
                    additional, "poi", id=f"detector_{row.detid}", type="traffic_detector",
                    lon=str(float(row.longitude)), lat=str(float(row.latitude)), geo="true",
                    color="255,0,0", layer="100", width="5", height="5",
                )
        except Exception:
            pass
    ET.ElementTree(additional).write(out / "detectors.add.xml", encoding="utf-8", xml_declaration=True)

    config = ET.Element("configuration")
    input_node = ET.SubElement(config, "input")
    ET.SubElement(input_node, "net-file", value=net.name)
    ET.SubElement(input_node, "route-files", value=routes.name)
    ET.SubElement(input_node, "additional-files", value="detectors.add.xml")
    time_node = ET.SubElement(config, "time")
    ET.SubElement(time_node, "begin", value=str(args.begin))
    ET.SubElement(time_node, "end", value=str(args.end))
    ET.SubElement(time_node, "step-length", value=str(args.step_length))
    processing = ET.SubElement(config, "processing")
    ET.SubElement(processing, "time-to-teleport", value=str(args.time_to_teleport))
    ET.SubElement(processing, "ignore-route-errors", value="true")
    report = ET.SubElement(config, "report")
    ET.SubElement(report, "verbose", value="true")
    ET.SubElement(report, "no-step-log", value="true")
    output_node = ET.SubElement(config, "output")
    ET.SubElement(output_node, "summary-output", value="summary.xml")
    ET.SubElement(output_node, "statistic-output", value="statistics.xml")
    ET.SubElement(output_node, "tripinfo-output", value="tripinfo.xml")
    ET.SubElement(output_node, "vehroute-output", value="vehroute.xml")
    random_node = ET.SubElement(config, "random_number")
    ET.SubElement(random_node, "seed", value=str(args.seed))
    gui = ET.SubElement(config, "gui_only")
    ET.SubElement(gui, "gui-settings-file", value="viewsettings.xml")
    ET.ElementTree(config).write(out / "berlin.sumocfg", encoding="utf-8", xml_declaration=True)

    view = ET.Element("viewsettings")
    ET.SubElement(view, "delay", value=str(args.gui_delay_ms))
    ET.SubElement(view, "scheme", name="real world")
    ET.SubElement(view, "viewport", zoom="100", x="0", y="0")
    ET.ElementTree(view).write(out / "viewsettings.xml", encoding="utf-8", xml_declaration=True)

    (out / "run_headless.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\nsumo -c berlin.sumocfg\n',
        encoding="utf-8",
    )
    (out / "run_gui.sh").write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\ncd "$(dirname "$0")"\nsumo-gui -c berlin.sumocfg --start\n',
        encoding="utf-8",
    )
    (out / "run_headless.sh").chmod(0o755)
    (out / "run_gui.sh").chmod(0o755)
    write_json(out / "simulation_manifest.json", {
        "config": str(out / "berlin.sumocfg"), "net": str(net), "routes": str(routes),
        "monitored_edges": len(edges), "begin": args.begin, "end": args.end,
        "outputs": ["summary.xml", "statistics.xml", "tripinfo.xml", "vehroute.xml", "simulated_edge_counts.xml"],
    })
    print(f"Built SUMO configuration: {out / 'berlin.sumocfg'}")


if __name__ == "__main__":
    main()
