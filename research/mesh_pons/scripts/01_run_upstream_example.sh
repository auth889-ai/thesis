#!/bin/sh
# Runs PONS's own examples exactly as shipped (no file in upstream/ is edited) and saves their output.
# LOG_FILE is PONS's own environment switch; it only moves ext_ns2.py's event log out of /tmp.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PY="$HERE/.venv/bin/python"
cd "$HERE/upstream/PONS"
git rev-parse HEAD > "$HERE/evidence/upstream_commit.txt"
git status --porcelain > "$HERE/evidence/upstream_dirty.txt"
( time "$PY" sim.py ) > "$HERE/evidence/upstream_sim.log" 2>&1
( LOG_FILE="$HERE/work/upstream_ext_ns2_events.log" "$PY" examples/ext_ns2.py ) > "$HERE/evidence/upstream_ext_ns2.log" 2>&1
