from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from .utils import write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--simulation-dir", required=True)
    parser.add_argument("--reports-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    simulation = Path(args.simulation_dir)
    reports = Path(args.reports_dir)
    out = Path(args.output_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for name in [
        "berlin.net.xml", "calibrated.rou.xml", "detectors.add.xml", "berlin.sumocfg",
        "viewsettings.xml", "run_headless.sh", "run_gui.sh", "summary.xml",
        "statistics.xml", "simulated_edge_counts.xml",
    ]:
        source = simulation / name
        if source.exists():
            shutil.copy2(source, out / name)
    if reports.exists():
        shutil.copytree(reports, out / "reports", dirs_exist_ok=True)
    readme = """# SUMO GUI bundle\n\nOn macOS/Linux with SUMO installed:\n\n```bash\ncd gui_bundle\n./run_gui.sh\n```\n\nThe live GUI is local. Colab is used for the headless run and file generation.\n"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    archive = shutil.make_archive(str(out), "zip", root_dir=out.parent, base_dir=out.name)
    write_json(out / "bundle_manifest.json", {"bundle": str(out), "zip": archive})
    print(archive)


if __name__ == "__main__":
    main()
