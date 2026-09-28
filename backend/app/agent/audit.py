"""THE AUDIT LOG — append-only JSONL per user, one line per decision, result, question, answer, approval or
refusal, each chained to the previous line by hash so a gap or an edit is detectable. Written before a call
executes and again after. Read by the app's Audit view and by the tests."""
from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import asdict
from pathlib import Path

from app.agent.models import AuditEntry
from app.paths import REPO

AUDIT_DIR = REPO / "results/live/agent/audit"
_LOCK = threading.Lock()


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
        return rec


def read(user_id: str, goal_id: str | None = None, limit: int = 200) -> list[dict]:
    path = _file(user_id)
    if not path.exists():
        return []
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if goal_id:
        rows = [r for r in rows if r.get("goal_id") == goal_id]
    return rows[-limit:]


def verify(user_id: str) -> dict:
    """Recompute the chain; any edited or removed line breaks it."""
    rows = read(user_id, limit=10**9); prev = "genesis"
    for i, r in enumerate(rows):
        body = {k: v for k, v in r.items() if k != "hash"}
        if r.get("prev") != prev or hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:16] != r.get("hash"):
            return {"ok": False, "broken_at": i, "entries": len(rows)}
        prev = r["hash"]
    return {"ok": True, "entries": len(rows)}
