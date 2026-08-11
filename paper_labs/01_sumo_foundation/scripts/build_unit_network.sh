#!/usr/bin/env bash
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SC="$LAB_ROOT/scenarios/unit_validation"
command -v netconvert >/dev/null || { echo "netconvert not found" >&2; exit 2; }
netconvert \
  --node-files "$SC/nodes.nod.xml" \
  --edge-files "$SC/edges.edg.xml" \
  --connection-files "$SC/connections.con.xml" \
  --tllogic-files "$SC/tls.tll.xml" \
  --output-file "$SC/network.net.xml" \
  --no-turnarounds true
netconvert --sumo-net-file "$SC/network.net.xml" --check-lane-foes.all true --output-file "$SC/network.checked.net.xml" >/dev/null 2>&1 || true
sumo -n "$SC/network.net.xml" --route-files "$SC/routes.empty.rou.xml" --begin 0 --end 1 --no-step-log true >/dev/null 2>&1 || true
echo "Built $SC/network.net.xml"
