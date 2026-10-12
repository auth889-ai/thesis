"""Move busy folders (many small files) to Drive as one compressed archive each, streamed: tar | zstd | rclone rcat, no local copy.

    python scripts/storage/archive.py upload [path ...]   # default: every MANIFEST entry with archive: true
    python scripts/storage/archive.py verify [path ...]   # Drive's md5 of each archive against the md5 taken while streaming

Per archive, under evidence/storage/archives/<name>/: files.md5 (md5 of every file inside, taken before upload), archive.json (archive
md5 and sha256, bytes, file count, Drive path, Drive md5, match). Nothing local is deleted here; removal stays `offload.py remove --yes`.
Restore: rclone cat <drive path> | zstd -d | tar -xf - -C <parent>.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from offload import EVID, load, local  # noqa: E402

OUT = EVID / "archives"
CHUNK = 1 << 20


def name_of(path: str) -> str:
    """Archive name of an entry: its path with / -> __ and ~ dropped. Pure."""
    return path.lstrip("~/").replace("/", "__")


def drive_path(m: dict, path: str) -> str:
    return f"{m['drive_remote']}:{m['drive_root']}/archives/{name_of(path)}.tar.zst"


def file_hashes(folder: Path, out: Path) -> int:
    """md5 of every regular file (symlinks skipped, as tar keeps them as links), sorted by path; returns the count."""
    files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.is_symlink())
    with out.open("w") as f:
        for p in files:
            h = hashlib.md5()
            with p.open("rb") as r:
                for b in iter(lambda: r.read(CHUNK), b""):
                    h.update(b)
            f.write(f"{h.hexdigest()}  {p.relative_to(folder.parent)}\n")
    return len(files)


def upload(m: dict, path: str) -> dict:
    src, dest, d = local(path), drive_path(m, path), OUT / name_of(path)
    d.mkdir(parents=True, exist_ok=True)
    n = file_hashes(src, d / "files.md5")
    tar = subprocess.Popen(["tar", "--no-xattrs", "-cf", "-", "-C", str(src.parent), src.name], stdout=subprocess.PIPE,
                           env={"COPYFILE_DISABLE": "1", "PATH": "/usr/bin:/bin"})
    zst = subprocess.Popen(["zstd", "-T0", "-3", "-q", "-c"], stdin=tar.stdout, stdout=subprocess.PIPE)
    tar.stdout.close()
    rc = subprocess.Popen(["rclone", "rcat", dest], stdin=subprocess.PIPE)
    md5, sha, size = hashlib.md5(), hashlib.sha256(), 0
    for b in iter(lambda: zst.stdout.read(CHUNK), b""):
        md5.update(b); sha.update(b); size += len(b)
        rc.stdin.write(b)
    rc.stdin.close()
    codes = {"tar": tar.wait(), "zstd": zst.wait(), "rclone": rc.wait()}
    rec = {"path": path, "drive": dest, "files": n, "bytes": size, "md5": md5.hexdigest(), "sha256": sha.hexdigest(),
           "exit_codes": codes, "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (d / "archive.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(json.dumps(rec), flush=True)
    return rec


def verify(m: dict, path: str) -> dict:
    d = OUT / name_of(path)
    rec = json.loads((d / "archive.json").read_text())
    got = subprocess.run(["rclone", "md5sum", rec["drive"]], capture_output=True, text=True).stdout.split()
    rec["drive_md5"] = got[0] if got else None
    rec["match"] = rec["drive_md5"] == rec["md5"] and not any(rec["exit_codes"].values())
    rec["verified_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (d / "archive.json").write_text(json.dumps(rec, indent=1) + "\n")
    print(path, "MATCH" if rec["match"] else "MISMATCH", rec["md5"], rec["drive_md5"], flush=True)
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["upload", "verify"])
    ap.add_argument("paths", nargs="*")
    a = ap.parse_args()
    m = load()
    paths = a.paths or [e["path"] for e in m["entries"] if e.get("archive")]
    for p in paths:
        if a.cmd == "upload":
            upload(m, p)
        verify(m, p)
    lines = [f"{r['md5']}  {r['sha256']}  {r['bytes']}  {r['drive']}" for r in
             (json.loads(f.read_text()) for f in sorted(OUT.glob("*/archive.json")))]
    (OUT / "SUMS.txt").write_text("# md5  sha256  bytes  drive path\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
