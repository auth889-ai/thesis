#!/usr/bin/env bash
set -euo pipefail

echo "Python:"
python3 --version

echo
echo "SUMO binaries:"
for cmd in sumo sumo-gui netconvert; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "  OK  $cmd -> $(command -v "$cmd")"
  else
    echo "  MISSING  $cmd"
  fi
done

echo
echo "Python packages:"
python3 - <<'PY'
mods = ["pandas", "numpy", "sklearn", "matplotlib"]
for name in mods:
    try:
        __import__(name)
        print("  OK ", name)
    except Exception as exc:
        print("  MISSING", name, "-", exc)
PY
