#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UP="${DHAKAFLOW_UPSTREAM_ROOT:-/content/dhakaflow_upstreams/lab01}"
REPO="$UP/sumo-scenarios"
SC="$REPO/bologna/acosta"
OUT="${1:-$ROOT/outputs/bologna_unmodified}"
mkdir -p "$OUT"
[ -d "$REPO/.git" ] || { echo "Run scripts/fetch_upstreams.sh first" >&2; exit 2; }
[ -f "$SC/run.sumocfg" ] || { echo "Acosta config missing" >&2; exit 3; }
BEFORE="$(git -C "$REPO" status --porcelain)"
if [ -n "$BEFORE" ]; then
  echo "Refusing: official upstream repo not clean before run" >&2
  git -C "$REPO" status --short
  exit 4
fi
set +e
(
  cd "$SC"
  /usr/bin/time -v sumo -c run.sumocfg --no-step-log true >"$OUT/stdout.log" 2>"$OUT/stderr_and_time.log"
)
CODE=$?
set -e
AFTER="$(git -C "$REPO" status --porcelain)"
cat > "$OUT/manifest.txt" <<EOF
repo_sha=$(git -C "$REPO" rev-parse HEAD)
sumo_version=$(sumo --version | head -1)
config=$SC/run.sumocfg
exit_code=$CODE
upstream_dirty_after_run=$([ -n "$AFTER" ] && echo yes || echo no)
EOF
exit "$CODE"
