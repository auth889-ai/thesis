#!/bin/bash
# Package the hosted app (Q5): the backend, configs, the built frontend, the evidence and only the data/result files the pages read
# (infra/app/package_paths.txt for whole folders; infra/app/data_files.txt, listed by recording the files the backend opened while headless Chrome visited every page). No .env.
#   infra/app/package.sh   -> /tmp/traffictwin-app.tar.gz and s3://dhakaflow-routing-<acct>/app/traffictwin-app.tar.gz (tagged)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; cd "$ROOT"
OUT="${TMPDIR:-/tmp}/traffictwin-app.tar.gz"
[ -f frontend/dist/index.html ] || { echo "build the frontend first (cd frontend && npx vite build)"; exit 1; }
[ -f frontend/map/dist/spa/index.html ] || { echo "build the map app first (cd frontend && npx vite build --config vite.maplink.config.ts && cd map && yarn build)"; exit 1; }
LIST="$(mktemp)"
{ grep -v '^#' infra/app/package_paths.txt; cat infra/app/data_files.txt; } > "$LIST"                # whole folders, then single files
TAR="${OUT%.gz}"
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='__pycache__' --exclude='backend/tests' --exclude='*.pyc' --exclude='.env' --exclude='evidence/qa' -cf "$TAR" -T "$LIST"
# The Model Lab: RQ1's pinned BasicTS harness (Apache-2.0, ~/.dhakaflow/upstream/BasicTS_legacy at its pinned commit), its code and the
# METR-LA dataset only, as third_party_runtime/BasicTS_legacy (DHAKAFLOW_BTS on the server). Skipped when the harness is not on this machine.
BTS="$HOME/.dhakaflow/upstream/BasicTS_legacy"
if [ -d "$BTS/datasets/METR-LA" ]; then
  echo "BasicTS harness at $(git -C "$BTS" rev-parse HEAD)"
  COPYFILE_DISABLE=1 tar --no-xattrs --exclude='__pycache__' --exclude='*.pyc' --exclude='DF_user*' -rf "$TAR" -C "$HOME/.dhakaflow/upstream" -s ',^BasicTS_legacy,third_party_runtime/BasicTS_legacy,' \
    BasicTS_legacy/basicts BasicTS_legacy/baselines BasicTS_legacy/LICENSE BasicTS_legacy/datasets/METR-LA
fi
# The Model Lab's recorded speeds: OpenCity's METR_LA.npz (RQ1's file, ~/.dhakaflow/upstream/OpenCity), as
# third_party_runtime/OpenCity/... (DHAKAFLOW_UPSTREAM on the server). Without it a forecast cannot run and the page says so.
if [ -f "$HOME/.dhakaflow/upstream/OpenCity/data/METR_LA/METR_LA.npz" ]; then
  COPYFILE_DISABLE=1 tar --no-xattrs -rf "$TAR" -C "$HOME/.dhakaflow/upstream" -s ',^OpenCity,third_party_runtime/OpenCity,' OpenCity/data/METR_LA/METR_LA.npz
fi
gzip -f "$TAR"
echo "package: $(du -h "$OUT" | cut -f1) $(shasum -a 256 "$OUT" | cut -d' ' -f1)"
BUCKET="dhakaflow-routing-$(aws sts get-caller-identity --query Account --output text)"
aws s3 cp "$OUT" "s3://$BUCKET/app/traffictwin-app.tar.gz" --region ap-south-1 --only-show-errors
aws s3api put-object-tagging --bucket "$BUCKET" --key app/traffictwin-app.tar.gz --region ap-south-1 --tagging 'TagSet=[{Key=project,Value=dhakaflow},{Key=phase,Value=routing}]'
echo "uploaded to s3://$BUCKET/app/traffictwin-app.tar.gz"
