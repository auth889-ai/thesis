#!/bin/bash
# Valhalla routing server for TrafficTwin: one container per OpenStreetMap extract (Geofabrik, ODbL), the official
# image unchanged (MIT; third_party/SOURCES.md, "Whole-city routing"). Runs as EC2 user data. Logs: /var/log/dhakaflow.log.
# Cost rule 4: the machine shuts itself down after @MAXH@ hours whatever happens.
set -u
exec > >(tee -a /var/log/dhakaflow.log) 2>&1
( sleep $((@MAXH@ * 3600)); echo "watchdog: @MAXH@ h reached, shutting down"; shutdown -h now ) &
echo "start $(date -u +%FT%TZ) image=@IMAGE@"
apt-get update -y && apt-get install -y docker.io curl
systemctl enable --now docker
mkdir -p /srv/valhalla && cd /srv/valhalla
: > SOURCES.txt
apt-get install -y unzip && curl -fsSL -o /tmp/awscli.zip "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install
BUCKET="@BUCKET@"; FROM_S3="@FROMS3@"
port=8002
for spec in @EXTRACTS@; do                       # city_id=geofabrik/path, e.g. dhaka=asia/bangladesh
  city="${spec%%=*}"; path="${spec#*=}"; name="$(basename "$path")"
  mkdir -p "$city"
  if [ "$FROM_S3" = "1" ]; then                   # saved tiles: ready in minutes, no extract download, no build
    aws s3 cp "s3://$BUCKET/tiles/$city/" "/srv/valhalla/$city/" --recursive --region ap-south-1 || { echo "no saved tiles for $city"; shutdown -h now; }
    [ -f "$city/valhalla_tiles.tar" ] || { echo "saved tiles for $city are incomplete"; shutdown -h now; }
    echo "$city tiles restored from s3://$BUCKET/tiles/$city/ $(sha256sum "$city/valhalla_tiles.tar" | cut -d' ' -f1)" >> SOURCES.txt
  else
    url="https://download.geofabrik.de/${path}-latest.osm.pbf"
    curl -fsSL -o "$city/${name}-latest.osm.pbf" "$url" || { echo "download failed: $url"; shutdown -h now; }
    sha="$(sha256sum "$city/${name}-latest.osm.pbf" | cut -d' ' -f1)"
    mod="$(curl -sI "$url" | grep -i last-modified | tr -d '\r')"
    echo "$city $url sha256=$sha $mod" >> SOURCES.txt
  fi
  docker run -d --restart unless-stopped --name "valhalla-$city" -p "$port:8002" -v "/srv/valhalla/$city:/custom_files" \
    -e build_elevation=False -e build_transit=False -e server_threads=2 -e use_tiles_ignore_pbf=True "@IMAGE@"
  echo "$city on port $port"
  port=$((port + 1))
done
# READY when every service answers /status
for i in $(seq 1 720); do
  ok=1; p=8002
  for spec in @EXTRACTS@; do curl -fs "http://127.0.0.1:$p/status" >/dev/null || ok=0; p=$((p + 1)); done
  if [ "$ok" = 1 ]; then echo "READY $(date -u +%FT%TZ)"; cp SOURCES.txt READY; break; fi
  sleep 10
done
if [ "$FROM_S3" != "1" ] && [ -f READY ]; then      # keep the built tiles: the next server starts from them in minutes
  for spec in @EXTRACTS@; do
    city="${spec%%=*}"
    for f in valhalla_tiles.tar valhalla.json; do
      [ -f "$city/$f" ] && echo "$city/$f sha256=$(sha256sum "$city/$f" | cut -d' ' -f1) bytes=$(stat -c %s "$city/$f")" >> TILES.txt
    done
    aws s3 cp "/srv/valhalla/$city/" "s3://$BUCKET/tiles/$city/" --recursive --exclude "*" --include "valhalla_tiles.tar" --include "valhalla.json" --include "*.sqlite" \
      --region ap-south-1 && echo "tiles saved to s3://$BUCKET/tiles/$city/"
  done
  aws s3 cp TILES.txt "s3://$BUCKET/tiles/TILES.txt" --region ap-south-1
  aws s3 cp SOURCES.txt "s3://$BUCKET/tiles/SOURCES.txt" --region ap-south-1
  for key in $(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix tiles/ --query 'Contents[].Key' --output text --region ap-south-1); do   # cost rule 3: every object tagged (s3 cp has no --tagging; s3api does)
    aws s3api put-object-tagging --bucket "$BUCKET" --key "$key" --region ap-south-1 --tagging 'TagSet=[{Key=project,Value=dhakaflow},{Key=phase,Value=routing}]'
  done
fi
echo "end of user data $(date -u +%FT%TZ)"
