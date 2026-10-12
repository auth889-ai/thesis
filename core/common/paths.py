"""Workspace locations shared by research code, independent of the web application."""
import os
from pathlib import Path

REPO = Path(os.environ.get("TRAFFICTWIN_ROOT", Path(__file__).resolve().parents[2])).resolve()
