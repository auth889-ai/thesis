from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--destination", required=True,
                        help="Path without .zip, often under /content/drive/MyDrive")
    args = parser.parse_args()
    workspace = Path(args.workspace)
    destination = Path(args.destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(destination), "zip", root_dir=workspace.parent, base_dir=workspace.name)
    print(archive)


if __name__ == "__main__":
    main()
