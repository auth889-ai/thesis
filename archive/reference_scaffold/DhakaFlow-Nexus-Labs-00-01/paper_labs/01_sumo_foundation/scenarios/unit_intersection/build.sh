#!/usr/bin/env bash
set -euo pipefail
netconvert \
  --node-files nodes.nod.xml \
  --edge-files edges.edg.xml \
  --connection-files connections.con.xml \
  --output-file network.net.xml \
  --no-turnarounds true
sumo -c unit.sumocfg --check-route-files true --no-step-log true --end 1
printf 'unit intersection validated\n'
