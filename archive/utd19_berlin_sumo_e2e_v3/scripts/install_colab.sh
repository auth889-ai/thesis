#!/usr/bin/env bash
set -euo pipefail

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq osmium-tool unzip > /dev/null
python -m pip install -q -r requirements-colab.txt
python - <<'PY'
import pathlib
import sumolib
print("sumolib:", sumolib.__file__)
print("SUMO Python package is installed")
PY
sumo --version | head -4
netconvert --version | head -4
duarouter --version | head -4
