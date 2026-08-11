#!/usr/bin/env bash
# Build the Colab bootstrap zip for Lab 01 (source only, no outputs/caches).
# Upload the result to MyDrive/DhakaFlow-Nexus-Data/Lab01_SUMO/lab02_source.zip
set -euo pipefail
LAB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$LAB_ROOT/outputs/lab02_source.zip}"
STAGE="$(mktemp -d)/02_dhaka_osm"
mkdir -p "$STAGE"
rsync -a "$LAB_ROOT/" "$STAGE/" \
  --exclude outputs --exclude logs --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '*.egg-info' \
  --exclude 'scenarios/unit_validation/network*.net.xml'
mkdir -p "$(dirname "$OUT")"
(cd "$(dirname "$STAGE")" && zip -qr "$OUT" "$(basename "$STAGE")")
echo "Wrote $OUT ($(du -h "$OUT" | cut -f1))"
