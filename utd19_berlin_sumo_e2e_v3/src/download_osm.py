from __future__ import annotations

import argparse
import time
from pathlib import Path

from .http_utils import download, head_metadata
from .utils import sha256_file, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    meta = head_metadata(args.url)
    path = download(args.url, output, expected_size=meta.get("size") or None)
    write_json(path.with_suffix(path.suffix + ".manifest.json"), {
        **meta,
        "downloaded_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sha256": sha256_file(path),
        "note": "The paper's exact OSM snapshot was not published.",
    })
    print(path)


if __name__ == "__main__":
    main()
