"""Compatibility entry point; implementation lives in traffictwin.protocols.stress_experiment."""
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[3]
for _path in (str(_REPO), str(_REPO / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
from traffictwin.protocols import stress_experiment as _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation
globals().update({_k: _v for _k, _v in vars(_implementation).items() if not _k.startswith("__")})   # loaders that bypass sys.modules still see the implementation
