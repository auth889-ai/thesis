#!/usr/bin/env python3
"""CLI adapter for a fresh, protocol-fixed execution."""
from pathlib import Path
import sys
REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "src")]
from traffictwin.orchestration.execution import main

if __name__ == "__main__":
    main()
