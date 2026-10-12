"""Provenance records — every scientific artifact must be traceable to a run.

Enforces the traceability rule: a result identifies its git SHA, upstream SHA,
dataset version, config, seed, environment, hardware and artifact path. Labs 00
and 01 already produce this information; this type gives it one shape.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def git_sha(repo_root: str | Path = ".") -> str:
    """Current commit of the working repo, or 'unknown' outside a checkout."""
    try:
        out = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


class ResultKind(str):
    """Result provenance classes that must never be mixed in a report."""

    PUBLISHED = "PUBLISHED_RESULT"
    REPRODUCED = "REPRODUCED_RESULT"
    DHAKA = "DHAKA_RESULT"
    FOUNDATION = "DHAKAFLOW_FOUNDATION_EXPERIMENT"


@dataclass(frozen=True)
class RunProvenance:
    """Everything needed to re-run and to cite a single experiment."""

    lab: str                                  # "01_sumo_foundation"
    experiment: str                           # "unit_full"
    result_kind: str = ResultKind.FOUNDATION
    git_sha: str = "unknown"
    upstream_shas: Mapping[str, str] = field(default_factory=dict)   # {"sumo": "...", ...}
    dataset_version: str | None = None
    dataset_scope: str = "SMOKE"              # SMOKE | OFFICIAL_REPRODUCTION | DHAKA
    config_path: str | None = None
    config_sha256: str | None = None
    seeds: tuple[int, ...] = ()
    environment: Mapping[str, str] = field(default_factory=dict)
    hardware: str = platform.platform()
    artifact_paths: Mapping[str, str] = field(default_factory=dict)
    created_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    def to_json(self, path: str | Path | None = None, indent: int = 2) -> str:
        payload = json.dumps(asdict(self), indent=indent, default=str)
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(payload)
        return payload

    def require_complete(self) -> None:
        """Fail loudly when a result is about to be reported without provenance."""
        missing = [f for f in ("lab", "experiment") if not getattr(self, f)]
        if self.git_sha in ("", "unknown"):
            missing.append("git_sha")
        if not self.seeds:
            missing.append("seeds")
        if missing:
            raise ValueError(f"incomplete provenance, refusing to publish: {missing}")
