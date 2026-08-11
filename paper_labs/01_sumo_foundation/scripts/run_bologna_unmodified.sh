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
# MODIFIED_BY_US 2026-08-11: /usr/bin/time does not exist in the Colab image
# (original run exited 127 before SUMO started). Wall time is measured with
# bash SECONDS instead; peak-RSS reporting was dropped.
set +e
SECONDS=0
(
  cd "$SC"
  sumo -c run.sumocfg --no-step-log true >"$OUT/stdout.log" 2>"$OUT/stderr_and_time.log"
)
CODE=$?
WALL="$SECONDS"
set -e
# MODIFIED_BY_US 2026-08-11: the unmodified acosta config writes its outputs
# into the scenario directory, so plain `git status` is always dirty after a
# successful run (untracked generated files). Upstream integrity means no
# TRACKED file changed; untracked outputs are listed for the record.
AFTER="$(git -C "$REPO" status --porcelain --untracked-files=no)"
UNTRACKED="$(git -C "$REPO" status --porcelain | grep -c '^??' || true)"
cat > "$OUT/manifest.txt" <<EOF
repo_sha=$(git -C "$REPO" rev-parse HEAD)
sumo_version=$(sumo --version | head -1)
config=$SC/run.sumocfg
exit_code=$CODE
wall_seconds=$WALL
tracked_files_modified=$([ -n "$AFTER" ] && echo yes || echo no)
untracked_generated_files=$UNTRACKED
EOF
exit "$CODE"
