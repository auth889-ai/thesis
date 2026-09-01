from __future__ import annotations

import argparse
from pathlib import Path

from .utils import run, which_or_fail, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args()

    config = Path(args.config).resolve()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    binary = which_or_fail("sumo-gui" if args.gui else "sumo")
    cmd = [binary, "-c", config.name]
    if args.gui:
        cmd += ["--start"]
    result = run(cmd, cwd=config.parent, log=out / ("sumo_gui.log" if args.gui else "sumo_headless.log"))
    write_json(out / "simulation_run.json", {
        "config": str(config), "gui": args.gui, "returncode": result.returncode,
        "note": "Interactive GUI requires a local desktop/X server; Colab is intended for the headless run.",
    })


if __name__ == "__main__":
    main()
