"""THE AUDIT LOG — append-only JSONL per user, one line per decision, result, question, answer, approval or
refusal, each chained to the previous line by hash so a gap or an edit is detectable. Written before a call
executes and again after. Read by the app's Audit view and by the tests.

Signed checkpoints (the design of OpenMuse's verifiable audit, tahodev/openmuse @ e39abd6): after every approval,
summary or error the server signs (entries, last hash) with a key only the server holds (AUDIT_SIGNING_KEY, or a
key file it generates once); `verify` recomputes the chain and checks the latest signature, so a rewritten log
that re-chains itself is still caught."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from dataclasses import asdict
from pathlib import Path

from app.agent.models import AuditEntry
from app.paths import REPO

AUDIT_DIR = REPO / "results/live/agent/audit"
_LOCK = threading.Lock()
CHECKPOINT_KINDS = ("approval", "summary", "error")


def _key() -> bytes:
    from app.credentials import load
    k = load("AUDIT_SIGNING_KEY")
    if k:
        return k.encode()
    f = AUDIT_DIR / ".signing_key"
    if not f.exists():
        AUDIT_DIR.mkdir(parents=True, exist_ok=True); f.write_text(secrets.token_hex(32)); f.chmod(0o600)
    return f.read_text().strip().encode()


def _sign(entries: int, last_hash: str, at_utc: str) -> str:
    return hmac.new(_key(), f"{entries}|{last_hash}|{at_utc}".encode(), hashlib.sha256).hexdigest()[:32]


def _file(user_id: str) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in user_id)[:64]
    return AUDIT_DIR / f"{safe}.jsonl"


def _last_hash(path: Path) -> str:
    if not path.exists():
        return "genesis"
    last = None
    with open(path, "rb") as f:
        for line in f:
            if line.strip():
                last = line
    return json.loads(last)["hash"] if last else "genesis"


def write(entry: AuditEntry) -> dict:
    with _LOCK:
        path = _file(entry.user_id)
        rec = asdict(entry); rec["prev"] = _last_hash(path)
        rec["hash"] = hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest()[:16]
        with open(path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        if entry.kind in CHECKPOINT_KINDS:
            _checkpoint(entry.user_id, path, rec["hash"])
        return rec


def _checkpoint(user_id: str, path: Path, last_hash: str) -> dict:
    n = sum(1 for l in open(path, "rb") if l.strip()); at = __import__("app.agent.models", fromlist=["now_iso"]).now_iso()
    cp = {"entries": n, "hash": last_hash, "at_utc": at, "sig": _sign(n, last_hash, at)}
    with open(path.with_suffix(".checkpoints.jsonl"), "a") as f:
        f.write(json.dumps(cp) + "\n")
    return cp


def _last_checkpoint(user_id: str) -> dict | None:
    f = _file(user_id).with_suffix(".checkpoints.jsonl")
    if not f.exists():
        return None
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    return json.loads(lines[-1]) if lines else None


def read(user_id: str, goal_id: str | None = None, limit: int = 200) -> list[dict]:
    path = _file(user_id)
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if goal_id:
        rows = [r for r in rows if r.get("goal_id") == goal_id]
    return rows[-limit:]


def verify(user_id: str) -> dict:
    """Recompute the chain (any edited or removed line breaks it), then check the latest signed checkpoint: its
    signature must verify and its hash must be the chain's hash at that many entries."""
    rows = read(user_id, limit=10**9); prev = "genesis"; hashes = []
    for i, r in enumerate(rows):
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16] != r.get("hash"):
            return {"ok": False, "broken_at": i, "entries": len(rows), "checkpoint": None}
        prev = r["hash"]; hashes.append(prev)
    cp = _last_checkpoint(user_id)
    if cp:
        sig_ok = hmac.compare_digest(cp.get("sig", ""), _sign(cp["entries"], cp["hash"], cp["at_utc"]))
        chain_ok = cp["entries"] <= len(hashes) and hashes[cp["entries"] - 1] == cp["hash"]
        cp = {"entries": cp["entries"], "at_utc": cp["at_utc"], "signed_ok": sig_ok, "matches_chain": chain_ok}
        if not (sig_ok and chain_ok):
            return {"ok": False, "broken_at": cp["entries"], "entries": len(rows), "checkpoint": cp}
    return {"ok": True, "entries": len(rows), "checkpoint": cp}


def erase_user(user_id: str) -> int:
    """Remove the person's log and its checkpoints (their data, on their request); the chain of other users is untouched."""
    n = 0
    with _LOCK:
        for f in (_file(user_id), _file(user_id).with_suffix(".checkpoints.jsonl")):
            if f.exists():
                f.unlink(); n += 1
    return n
