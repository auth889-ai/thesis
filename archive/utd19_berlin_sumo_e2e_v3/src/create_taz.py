from __future__ import annotations

import argparse
import math
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--net", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--grid-m", type=float, default=3000)
    parser.add_argument("--vclass", default="passenger")
    parser.add_argument("--min-edges", type=int, default=2)
    args = parser.parse_args()

    try:
        import sumolib  # type: ignore
    except Exception as exc:
        raise RuntimeError("sumolib is required") from exc

    net = sumolib.net.readNet(args.net, withInternal=False)
    groups: dict[tuple[int, int], list] = defaultdict(list)
    for edge in net.getEdges():
        if edge.isSpecial():
            continue
        try:
            allowed = edge.allows(args.vclass)
        except Exception:
            allowed = any(lane.allows(args.vclass) for lane in edge.getLanes())
        if not allowed:
            continue
        shape = edge.getShape()
        if not shape:
            continue
        x = sum(p[0] for p in shape) / len(shape)
        y = sum(p[1] for p in shape) / len(shape)
        groups[(math.floor(x / args.grid_m), math.floor(y / args.grid_m))].append(edge)

    root = ET.Element("additional")
    rows = []
    kept = 0
    for key, edges in sorted(groups.items()):
        if len(edges) < args.min_edges:
            continue
        taz_id = f"taz_{key[0]}_{key[1]}"
        edge_ids = [e.getID() for e in edges]
        xs = [p[0] for e in edges for p in e.getShape()]
        ys = [p[1] for e in edges for p in e.getShape()]
        shape = f"{min(xs)},{min(ys)} {max(xs)},{min(ys)} {max(xs)},{max(ys)} {min(xs)},{max(ys)}"
        taz = ET.SubElement(root, "taz", id=taz_id, edges=" ".join(edge_ids), shape=shape)
        # Uniform source/sink weights are explicit and reproducible.
        for edge_id in edge_ids:
            ET.SubElement(taz, "tazSource", id=edge_id, weight="1")
            ET.SubElement(taz, "tazSink", id=edge_id, weight="1")
            rows.append({"taz_id": taz_id, "edge_id": edge_id})
        kept += 1

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(root)
    tree.write(out / "berlin.taz.xml", encoding="utf-8", xml_declaration=True)
    pd.DataFrame(rows).to_csv(out / "edge_to_taz.csv", index=False)
    write_json(out / "taz_audit.json", {
        "grid_m": args.grid_m, "taz_count": kept, "assigned_edges": len(rows),
        "note": "The paper does not publish its TAZ definitions. This grid-based TAZ construction is a documented reconstruction.",
    })
    print(f"Created {kept} TAZs covering {len(rows)} edges")


if __name__ == "__main__":
    main()
