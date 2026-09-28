#!/usr/bin/env python3
"""Copy small forecasting result tables from a mounted Google Drive folder.

Colab writes large checkpoints/logs to Drive. This script copies only the small
CSV/Markdown benchmark summaries back into the repo.

Example after Drive is mounted locally:

    python src/pipeline/forecasting/pull_colab_results.py --drive /Volumes/GoogleDrive/MyDrive/dhakaflow/predict
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from traffictwin.paths import REPO
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--drive", type=Path, required=True,
                    help="Drive folder containing results/benchmark.csv and results/benchmark.md")
    ap.add_argument("--out", type=Path, default=REPO / "results/forecasting")
    args = ap.parse_args()

    src_dir = args.drive / "results"
    if not src_dir.exists():
        raise SystemExit(f"missing Drive result folder: {src_dir}")
    args.out.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in ("benchmark.csv", "benchmark.md"):
        src = src_dir / name
        if not src.exists():
            print(f"missing {src}; skipped")
            continue
        dst = args.out / name
        shutil.copy2(src, dst)
        copied.append(str(dst))
    if not copied:
        raise SystemExit("no Colab result files copied")
    print("copied:")
    for path in copied:
        print(" ", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
