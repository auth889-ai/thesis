#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

MANIFEST="${DHAKAFLOW_ASSET_MANIFEST:-docs/ASSET_MANIFEST.json}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Asset manifest missing: $MANIFEST"
  echo "Run: python scripts/build_asset_manifest.py"
  exit 1
fi

if [[ -n "${DHAKAFLOW_ASSET_ROOT:-}" ]]; then
  python scripts/restore_assets.py --manifest "$MANIFEST" --source "$DHAKAFLOW_ASSET_ROOT"
else
  echo "DHAKAFLOW_ASSET_ROOT is not set; verifying assets already present in this clone."
  echo "To restore from Drive/S3/GCS export, mirror files by relative path and set:"
  echo "  DHAKAFLOW_ASSET_ROOT=/path/to/DhakaFlow-assets"
  python scripts/restore_assets.py --manifest "$MANIFEST" --check-only
fi
