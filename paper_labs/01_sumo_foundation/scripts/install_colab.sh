#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python -m pip install -q --upgrade pip
python -m pip install -q -r "$ROOT/requirements-colab.txt"
python -m pip install -q -e "$ROOT"
python - <<'PYINNER'
import json, os
import sumo
import traci, sumolib
home = sumo.SUMO_HOME
checks = {
    "SUMO_HOME": home,
    "sumo_package": getattr(sumo, "__file__", None),
    "traci": getattr(traci, "__file__", None),
    "sumolib": getattr(sumolib, "__file__", None),
    "sumo_binary": os.path.join(home, "bin", "sumo"),
    "netconvert_binary": os.path.join(home, "bin", "netconvert"),
}
for key in ["sumo_binary", "netconvert_binary"]:
    if not os.path.exists(checks[key]):
        raise SystemExit(f"Missing expected SUMO binary: {checks[key]}")
print(json.dumps(checks, indent=2))
PYINNER
