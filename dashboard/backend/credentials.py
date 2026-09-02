"""Credential loading for the dashboard. Keys are read here and never leave the server.

(Named `credentials`, not `secrets`: a module called `secrets.py` on the path shadows the standard
library module of that name, which Starlette imports — the server would not start.)

Lookup order, matching the convention the rest of the repo already uses
(`pipeline/core/live/road511_provider.py`):

    1. the process environment
    2. `pipeline/core/.env`  — gitignored, never committed

Three rules this module exists to enforce:

  * A key is returned only to server-side callers. No endpoint, schema, log line or error message
    in this application ever includes a key value; `status()` reports presence and a fingerprint,
    never the secret.
  * A missing key is reported, never worked around. The live endpoints return
    `request_status: "NO_CREDENTIALS"` so the interface can say so plainly instead of quietly
    falling back to recorded data and labelling it live.
  * The fingerprint is a truncated SHA-256, so two operators can confirm they are using the same
    key without either of them seeing it.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV_FILE = REPO / "pipeline/core/.env"

GOOGLE_VAR = "GOOGLE_MAPS_API_KEY"
HERE_VARS = ("HERE_API_KEY", "HERE_APIKEY")


def _from_env_file(var: str) -> str:
    if not ENV_FILE.exists():
        return ""
    try:
        for line in ENV_FILE.read_text().splitlines():
            m = re.match(rf'\s*(?:export\s+)?{re.escape(var)}\s*=\s*["\']?([^"\'\s]+)', line)
            if m:
                return m.group(1)
    except OSError:
        return ""
    return ""


def load(var: str) -> str:
    """Environment first, then the gitignored .env. Empty string when absent — never raises."""
    return os.environ.get(var, "") or _from_env_file(var)


def google_key() -> str:
    return load(GOOGLE_VAR)


def here_key() -> str:
    for v in HERE_VARS:
        k = load(v)
        if k:
            return k
    return ""


def fingerprint(key: str) -> str:
    """Identify a key without revealing it."""
    return hashlib.sha256(key.encode()).hexdigest()[:8] if key else ""


def status() -> dict:
    """Safe to serve to the browser: presence and fingerprint only, never a key."""
    g, h = google_key(), here_key()
    return {
        "google_routes": {"configured": bool(g), "fingerprint": fingerprint(g),
                          "variable": GOOGLE_VAR},
        "here_traffic": {"configured": bool(h), "fingerprint": fingerprint(h),
                         "variable": HERE_VARS[0]},
        "source": "process environment, else pipeline/core/.env (gitignored)",
    }
