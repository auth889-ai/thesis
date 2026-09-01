from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SUMO_DIR = ROOT / "sumo"
SUMO_DIR.mkdir(exist_ok=True)


NODES = """<nodes>
    <node id="n0" x="0.0" y="0.0" type="priority"/>
    <node id="n1" x="500.0" y="0.0" type="priority"/>
    <node id="n2" x="1000.0" y="0.0" type="priority"/>
</nodes>
"""

EDGES = """<edges>
    <edge id="e0" from="n0" to="n1" numLanes="1" speed="13.89"/>
    <edge id="e1" from="n1" to="n2" numLanes="1" speed="13.89"/>
</edges>
"""


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise SystemExit(
            f"{name!r} was not found. Install Eclipse SUMO and "
            "restart Terminal, then run this script again."
        )
    return path


def main() -> None:
    netconvert = require_binary("netconvert")

    nodes = SUMO_DIR / "simple.nod.xml"
    edges = SUMO_DIR / "simple.edg.xml"
    net = SUMO_DIR / "simple.net.xml"

    nodes.write_text(NODES)
    edges.write_text(EDGES)

    cmd = [
        netconvert,
        "--node-files", str(nodes),
        "--edge-files", str(edges),
        "--output-file", str(net),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    print("=== SUMO NETWORK CREATED ===")
    print("Input nodes:", nodes)
    print("Input edges:", edges)
    print("Output network:", net)


if __name__ == "__main__":
    main()
