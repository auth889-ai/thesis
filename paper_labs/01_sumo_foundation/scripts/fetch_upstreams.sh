#!/usr/bin/env bash
set -euo pipefail
UP="${DHAKAFLOW_UPSTREAM_ROOT:-/content/dhakaflow_upstreams/lab01}"
mkdir -p "$UP"
SUMO_TAG="v1_27_1"
SCEN_SHA="00f6eb479a9dc0fbaeb731495c11d48d7a9661d3"

# SUMO source is fetched for provenance/API inspection only. Runtime binaries
# come from the pinned eclipse-sumo==1.27.1 package installed in Colab.
if [ ! -d "$UP/sumo/.git" ]; then
  git clone --filter=blob:none --branch "$SUMO_TAG" --single-branch https://github.com/eclipse-sumo/sumo.git "$UP/sumo"
fi
git -C "$UP/sumo" fetch --tags --force origin "$SUMO_TAG"
git -C "$UP/sumo" checkout --detach "$SUMO_TAG"

if [ ! -d "$UP/sumo-scenarios/.git" ]; then
  git clone --filter=blob:none https://github.com/DLR-TS/sumo-scenarios.git "$UP/sumo-scenarios"
fi
git -C "$UP/sumo-scenarios" fetch origin "$SCEN_SHA" --depth 1 || git -C "$UP/sumo-scenarios" fetch origin
git -C "$UP/sumo-scenarios" checkout --detach "$SCEN_SHA"

cat <<EOF
SUMO_TAG=$SUMO_TAG
SUMO_SOURCE_SHA=$(git -C "$UP/sumo" rev-parse HEAD)
SCENARIOS_SHA=$(git -C "$UP/sumo-scenarios" rev-parse HEAD)
UPSTREAM_ROOT=$UP
EOF
