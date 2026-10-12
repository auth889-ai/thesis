#!/bin/bash
# From the owner's machine (after `aws login`): sends infra/tiles/build.sh to the running Valhalla instance through SSM and waits.
# No new instance; the build uses the extracts already on it. Writes evidence/tiles/TILES_BASEMAP.txt when done.
#   infra/tiles/run.sh [instance-id]
set -euo pipefail
ID="${1:-i-0e8476dac1d2fa7c1}"; REGION=ap-south-1; VER="${PLANETILER_VERSION:-0.10.2}"                       # latest release read 2026-10-06
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUCKET="dhakaflow-routing-$(aws sts get-caller-identity --query Account --output text)"
DHAKA="90.30,23.66,90.52,23.92"                                  # the extent of the hospitals file and the reach grid (evidence/reach/dhaka)
LA="$(cd "$ROOT/backend" && DHAKAFLOW_NO_OBSERVATORY=1 python -c 'from core.simulation.routing.trip import places; b=places.city_box("Los Angeles")["bbox"]; print(",".join(str(round(x,4)) for x in b))')"
SCRIPT="$(base64 < "$ROOT/infra/tiles/build.sh" | tr -d '\n')"
CMD="echo $SCRIPT | base64 -d > /srv/tiles_build.sh && bash /srv/tiles_build.sh $BUCKET $VER dhaka=/srv/valhalla/dhaka/bangladesh-latest.osm.pbf=$DHAKA los_angeles=/srv/valhalla/los_angeles/socal-latest.osm.pbf=$LA"
CID="$(aws ssm send-command --region $REGION --instance-ids "$ID" --document-name AWS-RunShellScript --timeout-seconds 7200 \
      --parameters "commands=[\"$CMD\"],executionTimeout=[\"7200\"]" --query Command.CommandId --output text)"
echo "build sent: $CID (Dhaka $DHAKA, Los Angeles $LA)"
while :; do
  ST="$(aws ssm get-command-invocation --region $REGION --command-id "$CID" --instance-id "$ID" --query Status --output text 2>/dev/null || echo Pending)"
  case "$ST" in Pending|InProgress|Delayed) sleep 30;; *) break;; esac
done
mkdir -p "$ROOT/evidence/tiles"
aws ssm get-command-invocation --region $REGION --command-id "$CID" --instance-id "$ID" --query StandardOutputContent --output text | tee "$ROOT/evidence/tiles/TILES_BASEMAP.txt"
echo "status: $ST"
