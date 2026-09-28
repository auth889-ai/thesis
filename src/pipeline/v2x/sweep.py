"""Compatibility import for experiments.networking.channel_sweep; implementation moved, not copied."""
from importlib import import_module
from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[3]
for _path in (str(_REPO), str(_REPO / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)
_implementation = import_module("experiments.networking.channel_sweep")
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation
