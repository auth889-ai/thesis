"""Keep this Mac code-only: copy the folders listed in data/MANIFEST.yaml to Google Drive, check every file, and bring them back.

    python scripts/storage/offload.py upload            # rclone copy each entry to Drive (resumable; skips files already there)
    python scripts/storage/offload.py verify            # rclone check, file by file (Drive md5 against local) -> evidence/storage/verify.json
    python scripts/storage/offload.py plan              # what removal would delete and free; refuses unless verify passed for that entry
    python scripts/storage/offload.py aside | back      # move the large files to <path>.aside and back, to test with only the local part
    python scripts/storage/offload.py remove --yes      # delete the large files of verified entries (owner's yes required)
    python scripts/storage/offload.py fetch             # restore: public data from its source, the rest from Drive (make fetch-data)

Only files of keep_local_bytes or more are removed; summaries, hashes and notes stay local. Nothing is removed without a verify
that found 0 differing and 0 missing files for that entry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "data/MANIFEST.yaml"
EVID = REPO / "evidence/storage"
VERIFY = EVID / "verify.json"


def load() -> dict:
    return yaml.safe_load(MANIFEST.read_text())


def local(path: str) -> Path:
    return Path(path).expanduser() if path.startswith("~") else REPO / path


def remote(m: dict, path: str) -> str:
    """Drive path of an entry: repository paths under thesis/, home paths under home/. Pure."""
    key = "home/" + path[2:] if path.startswith("~/") else "thesis/" + path
    return f"{m['drive_remote']}:{m['drive_root']}/{key}"


def large_files(folder: Path, limit: int) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.is_file() and not p.is_symlink() and p.stat().st_size >= limit)


def rclone(*args: str) -> int:
    cmd = ["rclone", *args]
    print("+", shlex.join(cmd), flush=True)
    return subprocess.call(cmd)


def upload(m: dict) -> None:
    EVID.mkdir(parents=True, exist_ok=True)
    for e in m["entries"]:
        src = local(e["path"])
        if not src.exists():
            print("missing locally, skipped:", e["path"])
            continue
        rclone("copy", str(src), remote(m, e["path"]), "--checksum", "--transfers", "8", "--checkers", "16", "--skip-links",
               "--log-file", str(EVID / "upload.log"), "--log-level", "INFO", "--stats", "60s", "--stats-one-line")


def verify(m: dict) -> dict:
    EVID.mkdir(parents=True, exist_ok=True)
    out = {"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "method": "rclone check --one-way (md5)", "entries": {}}
    for e in m["entries"]:
        src = local(e["path"])
        if not src.exists():
            out["entries"][e["path"]] = {"ok": False, "reason": "missing locally"}
            continue
        r = subprocess.run(["rclone", "check", str(src), remote(m, e["path"]), "--one-way", "--skip-links", "--combined", "-",
                            "--checkers", "16"], capture_output=True, text=True)
        lines = [l for l in r.stdout.splitlines() if l[:2] in ("= ", "* ", "+ ", "- ", "! ")]
        tally = {k: sum(l.startswith(k) for l in lines) for k in ("= ", "* ", "+ ", "! ")}
        out["entries"][e["path"]] = {"same": tally["= "], "differ": tally["* "], "missing_on_drive": tally["+ "], "error": tally["! "],
                                     "ok": r.returncode == 0 and tally["* "] == tally["+ "] == tally["! "] == 0 and tally["= "] > 0}
        print(e["path"], out["entries"][e["path"]], flush=True)
    VERIFY.write_text(json.dumps(out, indent=1) + "\n")
    (EVID / "verify.json.sha256").write_text(hashlib.sha256(VERIFY.read_bytes()).hexdigest() + "  verify.json\n")
    return out


def verified() -> dict:
    return {k: v for k, v in json.loads(VERIFY.read_text())["entries"].items() if v.get("ok")} if VERIFY.exists() else {}


def plan(m: dict) -> list[tuple[str, int, int]]:
    ok, rows = verified(), []
    for e in m["entries"]:
        src = local(e["path"])
        files = large_files(src, m["keep_local_bytes"]) if src.exists() else []
        size = sum(p.stat().st_size for p in files)
        state = "verified" if e["path"] in ok else "NOT VERIFIED (kept)"
        print(f"{e['path']:45s} {len(files):6d} files  {size / 2**30:7.2f} GiB  {state}")
        if e["path"] in ok:
            rows.append((e["path"], len(files), size))
    print(f"would free {sum(r[2] for r in rows) / 2**30:.2f} GiB from {sum(r[1] for r in rows)} files")
    return rows


def aside(m: dict, back: bool) -> None:
    """Move large files to a sibling tree <path>.aside (same disk: a rename, nothing copied or deleted), or back."""
    for e in m["entries"]:
        src = local(e["path"])
        side = src.with_name(src.name + ".aside")
        frm, to = (side, src) if back else (src, side)
        if not frm.exists():
            continue
        files = sorted(p for p in frm.rglob("*") if p.is_file()) if back else large_files(frm, m["keep_local_bytes"])
        for p in files:
            dst = to / p.relative_to(frm)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.rename(p, dst)
        if back:
            for d in sorted(frm.rglob("*"), key=lambda x: -len(x.parts)):
                d.rmdir() if d.is_dir() else None
            frm.rmdir()
        print(("back" if back else "aside"), e["path"], len(files), "files")


def remove(m: dict) -> None:
    ok = verified()
    for e in m["entries"]:
        if e["path"] not in ok:
            continue
        for p in large_files(local(e["path"]), m["keep_local_bytes"]):
            p.unlink()
        print("removed large files of", e["path"])


def fetch(m: dict) -> None:
    """Restore every entry: public data with a refetch command from its source, then anything still absent from Drive."""
    for e in m["entries"]:
        if e["class"] == "document":
            continue
        if e.get("refetch"):
            print("+", e["refetch"], flush=True)
            if subprocess.call(e["refetch"], shell=True, cwd=REPO, env={**os.environ, "PYTHONPATH": f"{REPO}:{REPO / 'backend'}"}) == 0:
                continue
            print("source fetch failed; restoring our Drive copy of", e["path"])
        rclone("copy", remote(m, e["path"]), str(local(e["path"])), "--checksum", "--transfers", "8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["upload", "verify", "plan", "aside", "back", "remove", "fetch"])
    ap.add_argument("--yes", action="store_true", help="the owner's yes, required by remove")
    a = ap.parse_args()
    man = load()
    if a.action == "remove" and not a.yes:
        sys.exit("remove needs --yes: the owner approves the list from `plan` first")
    {"upload": upload, "verify": verify, "plan": plan, "remove": remove, "fetch": fetch,
     "aside": lambda m: aside(m, False), "back": lambda m: aside(m, True)}[a.action](man)
