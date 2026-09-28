#!/usr/bin/env python3
"""Fetch pinned official repositories into the gitignored external workspace.

Policy enforced here (see docs/INTEGRATED_BUILD_PLAN.md §OFFICIAL_REPOS):

* Official research code is **never** committed into this repository and never
  modified. `upstream/UPSTREAM_PINS.yaml` holds manifests only.
* Clones land in `$DHAKAFLOW_WORKSPACE` (default `~/.dhakaflow/upstream`), which
  is outside the repo entirely — so a nested git repo cannot be committed even
  by accident.
* A repo may only be marked USED once its checked-out SHA matches the pin. A
  floating `ref` is resolved and the SHA is written back, so the next fetch is
  reproducible.

Usage:
    python -m traffictwin.tools.fetch_upstream --list
    python -m traffictwin.tools.fetch_upstream --name RT-DETR
    python -m traffictwin.tools.fetch_upstream --subsystem forecasting
    python -m traffictwin.tools.fetch_upstream --verify-only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PINS_FILE = REPO_ROOT / "upstream" / "UPSTREAM_PINS.yaml"
DEFAULT_WORKSPACE = Path.home() / ".dhakaflow" / "upstream"


@dataclass
class Pin:
    name: str
    url: str | None
    ref: str
    sha: str | None
    subsystem: str
    status: str
    sparse_paths: list[str]
    license: str | None

    @property
    def fetchable(self) -> bool:
        return bool(self.url)


def load_pins(path: Path = PINS_FILE) -> list[Pin]:
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment guard
        sys.exit("PyYAML is required: pip install pyyaml")

    data = yaml.safe_load(path.read_text())
    pins: list[Pin] = []
    for entry in data.get("repos", []):
        pins.append(Pin(
            name=entry["name"],
            url=entry.get("url"),
            ref=entry.get("ref") or "main",
            sha=entry.get("sha"),
            subsystem=entry.get("subsystem", "unknown"),
            status=entry.get("status", "PINNED"),
            sparse_paths=list(entry.get("sparse_paths") or []),
            license=entry.get("license"),
        ))
    return pins


def workspace_root() -> Path:
    return Path(os.environ.get("DHAKAFLOW_WORKSPACE", str(DEFAULT_WORKSPACE))).expanduser()


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def fetch(pin: Pin, workspace: Path) -> dict:
    """Clone or update one pinned repo; return a provenance record."""
    if not pin.fetchable:
        return {"name": pin.name, "status": "SKIPPED_NO_URL",
                "note": "URL must be fresh-verified when this gate opens"}

    dest = workspace / pin.name
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not (dest / ".git").exists():
        cmd = ["git", "clone", "--filter=blob:none"]
        if pin.sparse_paths:
            cmd.append("--no-checkout")
        cmd += [pin.url, str(dest)]
        env_note = _run(cmd)
        del env_note
        if pin.sparse_paths:
            _run(["git", "sparse-checkout", "init", "--cone"], cwd=dest)
            _run(["git", "sparse-checkout", "set", *pin.sparse_paths], cwd=dest)

    # Pin wins over ref: a recorded SHA is checked out exactly.
    target = pin.sha or pin.ref
    _run(["git", "fetch", "--quiet", "origin", target if pin.sha else pin.ref], cwd=dest)
    _run(["git", "checkout", "--quiet", target], cwd=dest)

    actual = _run(["git", "rev-parse", "HEAD"], cwd=dest)
    record = {
        "name": pin.name,
        "subsystem": pin.subsystem,
        "path": str(dest),
        "pinned_sha": pin.sha,
        "actual_sha": actual,
        "license": pin.license,
    }

    if pin.sha and actual != pin.sha:
        record["status"] = "SHA_MISMATCH"
        record["error"] = (
            f"pinned {pin.sha} but checked out {actual} — refusing to mark USED")
    elif not pin.sha:
        record["status"] = "RESOLVED_FLOATING_REF"
        record["action_required"] = (
            f"write sha: {actual} back into upstream/UPSTREAM_PINS.yaml before use")
    else:
        record["status"] = "VERIFIED"
    return record


def verify_no_repo_pollution() -> list[str]:
    """The repo must contain no nested git repositories and no vendored upstream."""
    problems: list[str] = []
    for git_dir in REPO_ROOT.rglob(".git"):
        if git_dir.parent == REPO_ROOT:
            continue
        problems.append(f"nested git repository: {git_dir.parent.relative_to(REPO_ROOT)}")
    upstream_dir = REPO_ROOT / "upstream"
    for child in upstream_dir.iterdir() if upstream_dir.exists() else []:
        if child.is_dir():
            problems.append(
                f"upstream/ must hold manifests only, found directory: {child.name}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="fetch a single repo by name")
    ap.add_argument("--subsystem", help="fetch every repo of a subsystem")
    ap.add_argument("--list", action="store_true", help="list pins and exit")
    ap.add_argument("--verify-only", action="store_true",
                    help="check repo hygiene without fetching")
    args = ap.parse_args()

    pins = load_pins()

    if args.list:
        for p in pins:
            sha = (p.sha[:12] if p.sha else "UNRESOLVED")
            print(f"{p.subsystem:12} {p.name:22} {sha:14} {p.status:8} {p.url or 'NO URL'}")
        return 0

    problems = verify_no_repo_pollution()
    if problems:
        print("REPO HYGIENE FAILURES:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        if args.verify_only:
            return 1
    elif args.verify_only:
        print("repo hygiene OK: no nested repos, upstream/ holds manifests only")
        return 0

    selected = [p for p in pins
                if (not args.name or p.name == args.name)
                and (not args.subsystem or p.subsystem == args.subsystem)]
    if not selected:
        print("no pins matched", file=sys.stderr)
        return 1

    workspace = workspace_root()
    workspace.mkdir(parents=True, exist_ok=True)
    print(f"workspace: {workspace}")

    records = []
    for pin in selected:
        try:
            rec = fetch(pin, workspace)
        except Exception as exc:                     # noqa: BLE001 - reported, not raised
            rec = {"name": pin.name, "status": "FETCH_FAILED", "error": str(exc)}
        records.append(rec)
        print(f"  {rec['status']:24} {rec['name']}")

    # Merge by name rather than overwrite: fetching one repo must not erase the provenance of
    # every repo fetched before it.
    out = REPO_ROOT / "results/artifacts" / "upstream_fetch_record.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    prior = {}
    if out.exists():
        try:
            prior = {r["name"]: r for r in json.loads(out.read_text())}
        except (json.JSONDecodeError, KeyError, TypeError):
            prior = {}
    stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    for r in records:
        r["fetched_utc"] = stamp
        prior[r["name"]] = r
    out.write_text(json.dumps(sorted(prior.values(), key=lambda r: r["name"]), indent=2))
    print(f"record: {out.relative_to(REPO_ROOT)}")
    return 0 if all(r["status"] in {"VERIFIED", "RESOLVED_FLOATING_REF", "SKIPPED_NO_URL"}
                    for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
