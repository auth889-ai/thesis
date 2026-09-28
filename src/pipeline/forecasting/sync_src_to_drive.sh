#!/usr/bin/env bash
# Push the REAL source tree to Drive so Colab runs the same code as the repo (no copy-paste drift).
#   bash src/pipeline/forecasting/sync_src_to_drive.sh
set -euo pipefail
R=gdrive2tb:dhakaflow/src
for d in predict route network nlp dhakaflow research results; do
  rclone sync "$d" "$R/$d" \
    --include "*.py" --include "*.json" --include "*.yaml" --include "*.sh" \
    --exclude "**/__pycache__/**" --exclude "**/data/**" --exclude "**/results/**" \
    --exclude "**/scenarios/**" 2>&1 | grep -v client_id || true
done
# measured V2X statistics: the federated experiment's network model reads these
rclone sync results/networking "$R/../network/results" --include "penetration_p*_s*.json" 2>&1 | grep -v client_id || true
echo "synced source -> $R"
rclone lsf -R "$R" | grep -c '\.py$' | xargs echo "python files on Drive:"
