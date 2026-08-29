#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m src.pipeline --config config/full_colab.yaml "$@"
