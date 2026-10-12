"""Server-side settings of the web application. Credentials are loaded by core.common.credentials (shared with the research code)."""
from core.common.credentials import ENV_FILE, LEGACY_ENV_FILES, load_credential  # noqa: F401 - re-exported for the app's modules


# ---- application settings (used by main.py)
import os as _os
from core.common.evidence_paths import FRONTEND, MAP_APP, REPO as _REPO      # noqa: E402
MEDIA = _REPO / "docs/media"
API_DOCS_URL = "/api/docs"
OBSERVATORY_ENABLED = not _os.environ.get("DHAKAFLOW_NO_OBSERVATORY")     # live corridor sampling off in tests
from core.common.settings import DEFAULT_CITY, DEFAULT_TZ  # noqa: E402,F401
