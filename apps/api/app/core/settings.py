"""Application settings: where the browser app and media live, and which background services start."""
from __future__ import annotations

import os

from traffictwin.common import evidence_paths

FRONTEND = evidence_paths.FRONTEND                       # apps/web
MEDIA = evidence_paths.REPO / "docs/media"
API_DOCS_URL = "/api/docs"
OBSERVATORY_ENABLED = not os.environ.get("DHAKAFLOW_NO_OBSERVATORY")   # live corridor sampling off in tests
