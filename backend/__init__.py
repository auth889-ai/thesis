"""TrafficTwin web backend."""
from pathlib import Path
import sys

# Repository-root launch commands can use the shared scientific package without a wheel build.
_SOURCE = str(Path(__file__).resolve().parents[1] / "src")
if _SOURCE not in sys.path:
    sys.path.insert(0, _SOURCE)
