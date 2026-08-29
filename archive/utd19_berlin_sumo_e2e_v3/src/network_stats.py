from __future__ import annotations

import argparse
from pathlib import Path

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--vclass", default="passenger")
    args = parser.parse_args()
    try:
        import sumolib  # type: ignore
    except Exception as exc:
        raise RuntimeError("sumolib is required") from exc
    net = sumolib.net.readNet(args.net, withInternal=False)
    edges = [edge for edge in net.getEdges() if not edge.isSpecial()]
    passenger = []
    for edge in edges:
        try:
            if edge.allows(args.vclass):
                passenger.append(edge)
        except Exception:
            passenger.append(edge)
    xmin, ymin, xmax, ymax = net.getBoundary()
    stats = {
        "all_edges": len(edges),
        "passenger_edges": len(passenger),
        "passenger_lanes": sum(len(edge.getLanes()) for edge in passenger),
        "passenger_lane_km": sum(edge.getLength() * len(edge.getLanes()) for edge in passenger) / 1000.0,
        "junctions": len(net.getNodes()),
        "network_bbox_width_km": (xmax - xmin) / 1000.0,
        "network_bbox_height_km": (ymax - ymin) / 1000.0,
        "network_bbox_area_km2": (xmax - xmin) * (ymax - ymin) / 1_000_000.0,
        "warning": "Bounding-box area is not the legal Berlin area; it is a reproducible network extent diagnostic.",
    }
    write_json(args.output, stats)
    print(stats)


if __name__ == "__main__":
    main()
