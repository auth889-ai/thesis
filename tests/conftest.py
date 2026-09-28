"""Cross-cutting test configuration."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# subprocesses (python -m app....) must see backend/ like the in-process tests do
os.environ["PYTHONPATH"] = os.pathsep.join(x for x in (str(REPO / "backend"), str(REPO), os.environ.get("PYTHONPATH", "")) if x)
