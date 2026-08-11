from __future__ import annotations

import os
from pathlib import Path


def configure_sumo_env() -> dict[str, str]:
    """Configure a pip-installed eclipse-sumo runtime in the current Python process."""
    import sumo

    home = Path(sumo.SUMO_HOME).resolve()
    bin_dir = home / "bin"
    tools_dir = home / "tools"
    if not (bin_dir / "sumo").exists():
        raise RuntimeError(f"SUMO binary not found under {bin_dir}")
    if not (bin_dir / "netconvert").exists():
        raise RuntimeError(f"netconvert binary not found under {bin_dir}")

    os.environ["SUMO_HOME"] = str(home)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if str(bin_dir) not in path_parts:
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    py_parts = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    if tools_dir.exists() and str(tools_dir) not in py_parts:
        os.environ["PYTHONPATH"] = str(tools_dir) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")

    return {
        "SUMO_HOME": str(home),
        "SUMO_BIN": str(bin_dir / "sumo"),
        "NETCONVERT_BIN": str(bin_dir / "netconvert"),
        "SUMO_TOOLS": str(tools_dir),
    }
