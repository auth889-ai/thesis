#!/bin/bash
# Runs ON the Valhalla instance (sent through SSM by infra/tiles/run.sh). Builds one PMTiles basemap per city with Planetiler
# (Apache-2.0) from the Geofabrik extract already on the machine, uploads it to the routing bucket, tags it, and writes the hashes.
#   build.sh <bucket> <planetiler_version> <city>=<extract.pbf>=<w,s,e,n> [...]
set -euo pipefail
BUCKET="$1"; VER="$2"; shift 2
cd /srv
command -v java >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-21-jre-headless >/dev/null; }
[ -f planetiler.jar ] || curl -fsSL -o planetiler.jar "https://github.com/onthegomap/planetiler/releases/download/v${VER}/planetiler.jar"
mkdir -p /srv/tiles && : > /srv/tiles/TILES_BASEMAP.txt
for spec in "$@"; do
  city="${spec%%=*}"; rest="${spec#*=}"; pbf="${rest%%=*}"; bounds="${rest#*=}"
  t0=$(date +%s)
  java -Xmx10g -jar planetiler.jar --osm-path="$pbf" --bounds="$bounds" --maxzoom=14 --download --download-dir=/srv/tiles/sources \
       --output="/srv/tiles/${city}.pmtiles" --force >> /srv/tiles/build.log 2>&1
  t1=$(date +%s)
  sha=$(sha256sum "/srv/tiles/${city}.pmtiles" | cut -d' ' -f1); size=$(stat -c %s "/srv/tiles/${city}.pmtiles")
  echo "${city} planetiler=${VER} bounds=${bounds} extract=${pbf} extract_sha256=$(sha256sum "$pbf" | cut -d' ' -f1) pmtiles_sha256=${sha} bytes=${size} seconds=$((t1 - t0))" >> /srv/tiles/TILES_BASEMAP.txt
  aws s3 cp "/srv/tiles/${city}.pmtiles" "s3://${BUCKET}/tiles/${city}/basemap.pmtiles" --region ap-south-1 --only-show-errors
  aws s3api put-object-tagging --bucket "$BUCKET" --key "tiles/${city}/basemap.pmtiles" --region ap-south-1 --tagging 'TagSet=[{Key=project,Value=dhakaflow},{Key=phase,Value=routing}]'
done
aws s3 cp /srv/tiles/TILES_BASEMAP.txt "s3://${BUCKET}/tiles/TILES_BASEMAP.txt" --region ap-south-1 --only-show-errors
aws s3api put-object-tagging --bucket "$BUCKET" --key tiles/TILES_BASEMAP.txt --region ap-south-1 --tagging 'TagSet=[{Key=project,Value=dhakaflow},{Key=phase,Value=routing}]'
cat /srv/tiles/TILES_BASEMAP.txt
