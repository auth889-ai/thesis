"""Server-side credentials shared by the API and command-line adapters."""
import os
from pathlib import Path

from dotenv import dotenv_values

from traffictwin.paths import REPO

ENV_FILE = REPO / ".env"
LEGACY_ENV_FILES = (REPO / "src/pipeline/core/.env", REPO / "dhakaflow/.env")


def load_credential(name: str, *, files: tuple[Path, ...] | None = None) -> str:
    """Process environment wins; parse files without expansion or global mutation."""
    value = os.environ.get(name)
    if value:
        return value
    for path in files if files is not None else (ENV_FILE, *LEGACY_ENV_FILES):
        try:
            value = dotenv_values(path, interpolate=False).get(name)
        except OSError:
            continue
        if value:
            return value
    return ""
