"""Compatibility entry point; implementation lives in traffictwin.control.signal_baselines."""
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[3]
for _path in (str(_REPO), str(_REPO / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
from traffictwin.control import signal_baselines as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation
