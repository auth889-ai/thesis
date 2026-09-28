"""Shared evidence files for HTTP adapters."""
from __future__ import annotations

import json
from pathlib import Path


def _read_json(path) -> dict | None:
    """A status file is rewritten after every arm; a reader may catch it half-written."""
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return None
