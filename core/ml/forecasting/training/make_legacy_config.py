"""Generate a DhakaR1 config for one legacy-BasicTS baseline from its own
PEMS04 config — the official config is the template, we patch dataset name and
node count only (adapter rule: translate, never alter the algorithm).

Usage (inside the legacy checkout):
    python make_legacy_config.py --bts /path/BasicTS_legacy --model STID
Writes baselines/<MODEL>/DhakaR1SensorGraph_legacy.py
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

DATASET = "DhakaR1SensorGraph_legacy"
NUM_NODES = 250


def make(bts: Path, model: str) -> Path:
    src = bts / "baselines" / model / "PEMS04.py"
    if not src.exists():
        raise SystemExit(f"{src} missing — model folder layout changed?")
    text = src.read_text()
    text = text.replace("DATA_NAME = 'PEMS04'", f"DATA_NAME = '{DATASET}'")
    text = re.sub(r'("num_nodes"\s*:\s*)307', rf"\g<1>{NUM_NODES}", text)
    # Some configs carry PEMS04 node count under different keys.
    text = re.sub(r'("num_of_vertices"\s*:\s*)307', rf"\g<1>{NUM_NODES}", text)
    out = src.with_name(f"{DATASET}.py")
    out.write_text(text)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bts", type=Path, required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    print(make(args.bts, args.model))
