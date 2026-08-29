from __future__ import annotations

import json
import py_compile
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

required = [
    "paper/Advanced_Traffic_Demand_Generation_VTC2024.pdf",
    "notebooks/UTD19_Berlin_SUMO_Full_End_to_End.ipynb",
    "src/pipeline.py",
    "src/preprocess_utd19.py",
    "src/train_models.py",
    "src/preprocess_berlin.py",
    "src/build_network.py",
    "src/map_detectors.py",
    "src/generate_candidates.py",
    "src/calibrate.py",
    "src/run_simulation.py",
    "src/evaluate.py",
]
for rel in required:
    assert (ROOT / rel).exists(), rel

for script in (ROOT / "src").glob("*.py"):
    py_compile.compile(str(script), doraise=True)

for cfg in (ROOT / "config").glob("*.yaml"):
    data = yaml.safe_load(cfg.read_text())
    assert data["simulation"]["end"] > data["simulation"]["begin"]
    assert data["utd19"]["hourly_aggregation"] in {"mean", "median"}

for xml in [ROOT / "demo/demo.nod.xml", ROOT / "demo/demo.edg.xml"]:
    ET.parse(xml)

notebook = json.loads((ROOT / "notebooks/UTD19_Berlin_SUMO_Full_End_to_End.ipynb").read_text())
assert len(notebook["cells"]) >= 50
assert len(list((ROOT / "paper/pages").glob("page_*.png"))) == 7
print("Project static verification passed")
