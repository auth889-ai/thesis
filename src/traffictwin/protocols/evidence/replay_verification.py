"""Verify recorded execution artifacts before labelling a replay verified."""
import hashlib
import json
from pathlib import Path
import re


def verify(root: Path):
    manifest = root / "manifest.json"
    if not manifest.is_file():
        return {"mode": "RECORDED_REPLAY", "verified": False, "reason": "No completion manifest; legacy evidence is unverified."}
    hashes = json.loads(manifest.read_text())
    if not hashes or "report.json" not in hashes or "PROTOCOL.json" not in hashes:
        raise ValueError("Incomplete replay manifest")
    for name, expected in hashes.items():
        path = root / name
        if Path(name).is_absolute() or ".." in Path(name).parts or not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError("Replay manifest contains an external artifact")
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid artifact digest")
        if not path.is_file():
            raise ValueError(f"Replay artifact missing: {name}")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Replay artifact changed: {name}")
    return {"mode": "VERIFIED_REPLAY", "verified": True, "files_verified": len(hashes),
            "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "scope": "Artifact integrity against the local completion manifest, not independent scientific validation."}
