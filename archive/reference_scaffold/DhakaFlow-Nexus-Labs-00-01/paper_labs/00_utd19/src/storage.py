from __future__ import annotations
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import sys


def sha256(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def file_manifest(paths):
    rows = []
    for p in map(Path, paths):
        if p.exists():
            rows.append({"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)})
    return rows


def environment_manifest():
    def cmd(args):
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as exc:
            return f"unavailable: {exc}"

    return {
        "python": sys.version,
        "platform": platform.platform(),
        "pip_freeze": cmd([sys.executable, "-m", "pip", "freeze"]),
    }


def save_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
