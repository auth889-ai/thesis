#!/usr/bin/env python3
"""Restore and verify DhakaFlow rebuild assets.

This script copies missing or mismatched files from a local asset mirror and
then verifies every checksum in docs/ASSET_MANIFEST.json. It never calls APIs.

    python scripts/restore_assets.py --check-only
    DHAKAFLOW_ASSET_ROOT=/Volumes/Drive/DhakaFlow-assets python scripts/restore_assets.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO / "docs/ASSET_MANIFEST.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def status_for(path: Path, expected_sha256: str) -> str:
    if not path.exists():
        return "missing"
    actual = sha256_file(path)
    return "ok" if actual == expected_sha256 else "sha256_mismatch"


def copy_from_source(source_root: Path, rel: str, dst: Path) -> bool:
    src = source_root / rel
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=REPO)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--source", type=Path, default=os.environ.get("DHAKAFLOW_ASSET_ROOT"))
    ap.add_argument("--check-only", action="store_true", help="verify only; do not copy from --source")
    args = ap.parse_args()

    repo = args.repo.resolve()
    manifest_path = args.manifest if args.manifest.is_absolute() else repo / args.manifest
    if not manifest_path.exists():
        raise SystemExit(f"asset manifest not found: {manifest_path}; run python scripts/build_asset_manifest.py")

    manifest = json.loads(manifest_path.read_text())
    source_root = args.source.resolve() if args.source else None
    report = {"ok": [], "restored": [], "missing": [], "sha256_mismatch": []}

    for asset in manifest.get("assets", []):
        rel = asset["path"]
        dst = repo / rel
        state = status_for(dst, asset["sha256"])
        if state == "ok":
            report["ok"].append(rel)
            continue
        if not args.check_only and source_root and copy_from_source(source_root, rel, dst):
            state = status_for(dst, asset["sha256"])
            if state == "ok":
                report["restored"].append(rel)
                continue
        report[state].append(rel)

    print(json.dumps({
        "ok": len(report["ok"]),
        "restored": len(report["restored"]),
        "missing": len(report["missing"]),
        "sha256_mismatch": len(report["sha256_mismatch"]),
        "source": str(source_root) if source_root else None,
        "manifest": str(manifest_path),
    }, indent=1))

    if report["missing"] or report["sha256_mismatch"]:
        if report["missing"]:
            print("\nmissing:")
            for rel in report["missing"]:
                print(f"  {rel}")
        if report["sha256_mismatch"]:
            print("\nsha256_mismatch:")
            for rel in report["sha256_mismatch"]:
                print(f"  {rel}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
