"""Compatibility entry point; implementation lives in traffictwin.networking.channel."""
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[3]
for _path in (str(_REPO), str(_REPO / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
from traffictwin.networking import channel as _implementation

sys.modules[__name__] = _implementation
