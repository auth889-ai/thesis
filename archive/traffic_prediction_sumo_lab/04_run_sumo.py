from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CFG = ROOT / "sumo" / "experiment.sumocfg"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Open sumo-gui instead of command-line sumo.",
    )
    args = parser.parse_args()

    binary_name = "sumo-gui" if args.gui else "sumo"
    binary = shutil.which(binary_name)
    if binary is None:
        raise SystemExit(
            f"{binary_name!r} was not found. Install Eclipse SUMO, "
            "restart Terminal, and run again."
        )

    if not CFG.exists():
        raise SystemExit(
            "SUMO config not found. Run scripts 02 and 03 first."
        )

    cmd = [binary, "-c", str(CFG)]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=CFG.parent)

    print("=== SUMO EXPERIMENT COMPLETE ===")
    print("Created:")
    print(" - outputs/edge_output.xml")
    print(" - outputs/tripinfo.xml")


if __name__ == "__main__":
    main()
